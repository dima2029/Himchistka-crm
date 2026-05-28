"""
Бэкенд Химчистка CRM — подключение к Supabase (PostgreSQL).
Данные хранятся в Supabase навсегда, работает на бесплатном Render.

Переменные окружения (задаются в Render → Environment):
  SUPABASE_URL   — https://xxxxx.supabase.co
  SUPABASE_KEY   — service_role ключ (секретный)
  APP_PASSWORD   — пароль для входа в приложение (по умолчанию 1234)
"""
import os
import json
import httpx
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List

# ── Настройки ────────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "1234")
TABLE = "zakazy"

REST = f"{SUPABASE_URL}/rest/v1/{TABLE}"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Авто-загрузка начальных данных при первом старте ─────────
@app.on_event("startup")
def seed_if_empty():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("WARNING: SUPABASE_URL / SUPABASE_KEY не заданы!")
        return
    try:
        with httpx.Client(timeout=30) as client:
            r = client.head(REST, headers={**HEADERS, "Prefer": "count=exact"},
                            params={"select": "id"})
            cnt = r.headers.get("content-range", "0/0").split("/")[-1]
            count = int(cnt) if cnt.isdigit() else 0
        if count > 0:
            print(f"База содержит {count} записей — загрузка не нужна")
            return
        if not os.path.exists("seed_data.json"):
            print("seed_data.json не найден")
            return
        print("Загрузка начальных данных в Supabase...")
        with open("seed_data.json", encoding="utf-8") as f:
            seed = json.load(f)
        rows = [{"t":x.get("t",""),"a":x.get("a",""),"d":x.get("d",""),
                 "km":x.get("km",0) or 0,"os":x.get("os",0) or 0,"sk":x.get("sk",0) or 0,
                 "ps":x.get("ps",0) or 0,"i":x.get("i",0) or 0,"c":x.get("c","") or ""} for x in seed]
        with httpx.Client(timeout=120) as client:
            for i in range(0, len(rows), 500):
                chunk = rows[i:i+500]
                resp = client.post(REST, headers={**HEADERS, "Prefer": "return=minimal"}, json=chunk)
                if resp.status_code not in (200, 201):
                    print(f"Ошибка загрузки: {resp.text[:200]}")
                    return
        print(f"OK: Загружено {len(rows)} записей в Supabase")
    except Exception as e:
        print(f"Ошибка seed: {e}")

# ── Авторизация ──────────────────────────────────────────────
def check_auth(x_password: Optional[str]):
    if x_password != APP_PASSWORD:
        raise HTTPException(status_code=401, detail="Неверный пароль")

# ── Модели ───────────────────────────────────────────────────
class Order(BaseModel):
    t: Optional[str] = ""
    a: Optional[str] = ""
    d: Optional[str] = ""
    km: Optional[float] = 0
    os: Optional[int] = 0
    sk: Optional[float] = 0
    ps: Optional[int] = 0
    i: Optional[float] = 0
    c: Optional[str] = ""

class AuthBody(BaseModel):
    password: str

def order_dict(o: Order):
    return {"t":o.t,"a":o.a,"d":o.d,"km":o.km,"os":o.os,"sk":o.sk,"ps":o.ps,"i":o.i,"c":o.c}

# ── Эндпоинты ────────────────────────────────────────────────
@app.post("/api/auth")
def auth(body: AuthBody):
    if body.password != APP_PASSWORD:
        raise HTTPException(status_code=401, detail="Неверный пароль")
    return {"ok": True}

@app.get("/api/orders")
def get_orders(x_password: Optional[str] = Header(None)):
    check_auth(x_password)
    result = []
    offset = 0
    page = 1000
    with httpx.Client(timeout=60) as client:
        while True:
            r = client.get(
                REST,
                headers={**HEADERS, "Range-Unit": "items", "Range": f"{offset}-{offset+page-1}"},
                params={"select": "*"}
            )
            if r.status_code not in (200, 206):
                raise HTTPException(status_code=500, detail=f"Supabase: {r.text}")
            batch = r.json()
            if not batch:
                break
            for row in batch:
                row["_id"] = row.pop("id")
                result.append(row)
            if len(batch) < page:
                break
            offset += page
    return result

@app.post("/api/orders")
def add_order(order: Order, x_password: Optional[str] = Header(None)):
    check_auth(x_password)
    with httpx.Client(timeout=30) as client:
        r = client.post(REST, headers={**HEADERS, "Prefer": "return=representation"},
                         json=order_dict(order))
    if r.status_code not in (200, 201):
        raise HTTPException(status_code=500, detail=f"Supabase: {r.text}")
    new = r.json()[0]
    return {"_id": new["id"], "ok": True}

@app.post("/api/orders/bulk")
def add_bulk(orders: List[Order], x_password: Optional[str] = Header(None)):
    check_auth(x_password)
    rows = [order_dict(o) for o in orders]
    inserted = 0
    with httpx.Client(timeout=120) as client:
        # вставляем кусками по 500
        for i in range(0, len(rows), 500):
            chunk = rows[i:i+500]
            r = client.post(REST, headers={**HEADERS, "Prefer": "return=minimal"}, json=chunk)
            if r.status_code not in (200, 201):
                raise HTTPException(status_code=500, detail=f"Supabase: {r.text}")
            inserted += len(chunk)
    return {"inserted": inserted, "ok": True}

@app.put("/api/orders/{order_id}")
def update_order(order_id: str, order: Order, x_password: Optional[str] = Header(None)):
    check_auth(x_password)
    with httpx.Client(timeout=30) as client:
        r = client.patch(REST, headers=HEADERS, params={"id": f"eq.{order_id}"},
                         json=order_dict(order))
    if r.status_code not in (200, 204):
        raise HTTPException(status_code=500, detail=f"Supabase: {r.text}")
    return {"ok": True}

@app.delete("/api/orders/{order_id}")
def delete_order(order_id: str, x_password: Optional[str] = Header(None)):
    check_auth(x_password)
    with httpx.Client(timeout=30) as client:
        r = client.delete(REST, headers=HEADERS, params={"id": f"eq.{order_id}"})
    if r.status_code not in (200, 204):
        raise HTTPException(status_code=500, detail=f"Supabase: {r.text}")
    return {"ok": True}

# Сколько записей в базе (для отладки)
@app.get("/api/count")
def count(x_password: Optional[str] = Header(None)):
    check_auth(x_password)
    with httpx.Client(timeout=30) as client:
        r = client.head(REST, headers={**HEADERS, "Prefer": "count=exact"},
                        params={"select": "id"})
    cnt = r.headers.get("content-range", "0/0").split("/")[-1]
    return {"count": int(cnt) if cnt.isdigit() else 0}

# ── Фронтенд ─────────────────────────────────────────────────
@app.get("/")
def root():
    return FileResponse("index.html")
