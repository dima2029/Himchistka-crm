"""
Бэкенд для Химчистка CRM
Эндпоинты под существующий фронтенд:
  POST   /api/auth            — проверка пароля
  GET    /api/orders          — все заказы
  POST   /api/orders          — добавить один
  POST   /api/orders/bulk     — добавить много
  PUT    /api/orders/{id}     — изменить
  DELETE /api/orders/{id}     — удалить
Заголовок x-password для авторизации.
"""
import os
import json
import sqlite3
import uuid
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List

# ── Настройки ────────────────────────────────────────────────
APP_PASSWORD = os.environ.get("APP_PASSWORD", "1234")  # пароль входа
# На Render с диском данные лежат на /var/data, локально — рядом
DATA_DIR = os.environ.get("DATA_DIR", ".")
DB_PATH = os.path.join(DATA_DIR, "zakazy.db")
SEED_PATH = "seed_data.json"

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── База данных ──────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS zakazy (
            id TEXT PRIMARY KEY,
            t TEXT DEFAULT '',
            a TEXT DEFAULT '',
            d TEXT DEFAULT '',
            km REAL DEFAULT 0,
            os INTEGER DEFAULT 0,
            sk REAL DEFAULT 0,
            ps INTEGER DEFAULT 0,
            i REAL DEFAULT 0,
            c TEXT DEFAULT ''
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_t ON zakazy(t)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_a ON zakazy(a)")
    conn.commit()

    # Если база пустая — загрузить начальные данные
    count = c.execute("SELECT COUNT(*) FROM zakazy").fetchone()[0]
    if count == 0 and os.path.exists(SEED_PATH):
        print("Загрузка начальных данных...")
        with open(SEED_PATH, encoding="utf-8") as f:
            seed = json.load(f)
        for r in seed:
            c.execute(
                "INSERT INTO zakazy (id,t,a,d,km,os,sk,ps,i,c) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), r.get("t",""), r.get("a",""), r.get("d",""),
                 r.get("km",0) or 0, r.get("os",0) or 0, r.get("sk",0) or 0,
                 r.get("ps",0) or 0, r.get("i",0) or 0, r.get("c","") or "")
            )
        conn.commit()
        print(f"Загружено {len(seed)} записей")
    conn.close()

@app.on_event("startup")
def startup():
    init_db()

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

# ── Эндпоинты ────────────────────────────────────────────────
@app.post("/api/auth")
def auth(body: AuthBody):
    if body.password != APP_PASSWORD:
        raise HTTPException(status_code=401, detail="Неверный пароль")
    return {"ok": True}

@app.get("/api/orders")
def get_orders(x_password: Optional[str] = Header(None)):
    check_auth(x_password)
    conn = get_db()
    rows = conn.execute("SELECT * FROM zakazy").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["_id"] = d.pop("id")
        result.append(d)
    return result

@app.post("/api/orders")
def add_order(order: Order, x_password: Optional[str] = Header(None)):
    check_auth(x_password)
    new_id = str(uuid.uuid4())
    conn = get_db()
    conn.execute(
        "INSERT INTO zakazy (id,t,a,d,km,os,sk,ps,i,c) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (new_id, order.t, order.a, order.d, order.km, order.os, order.sk, order.ps, order.i, order.c)
    )
    conn.commit()
    conn.close()
    return {"_id": new_id, "ok": True}

@app.post("/api/orders/bulk")
def add_bulk(orders: List[Order], x_password: Optional[str] = Header(None)):
    check_auth(x_password)
    conn = get_db()
    inserted = 0
    for order in orders:
        conn.execute(
            "INSERT INTO zakazy (id,t,a,d,km,os,sk,ps,i,c) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), order.t, order.a, order.d, order.km, order.os, order.sk, order.ps, order.i, order.c)
        )
        inserted += 1
    conn.commit()
    conn.close()
    return {"inserted": inserted, "ok": True}

@app.put("/api/orders/{order_id}")
def update_order(order_id: str, order: Order, x_password: Optional[str] = Header(None)):
    check_auth(x_password)
    conn = get_db()
    conn.execute(
        "UPDATE zakazy SET t=?,a=?,d=?,km=?,os=?,sk=?,ps=?,i=?,c=? WHERE id=?",
        (order.t, order.a, order.d, order.km, order.os, order.sk, order.ps, order.i, order.c, order_id)
    )
    conn.commit()
    conn.close()
    return {"ok": True}

@app.delete("/api/orders/{order_id}")
def delete_order(order_id: str, x_password: Optional[str] = Header(None)):
    check_auth(x_password)
    conn = get_db()
    conn.execute("DELETE FROM zakazy WHERE id=?", (order_id,))
    conn.commit()
    conn.close()
    return {"ok": True}

# ── Фронтенд ─────────────────────────────────────────────────
@app.get("/")
def root():
    return FileResponse("index.html")

# статика если будут доп. файлы
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")
