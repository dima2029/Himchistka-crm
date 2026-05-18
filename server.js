const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;
const MONGO_URI = process.env.MONGO_URI;
const APP_PASSWORD = process.env.APP_PASSWORD || '1234';

// ── MIDDLEWARE ────────────────────────────────────────────────
app.use(cors());
app.use(express.json({ limit: '50mb' }));
app.use(express.static(path.join(__dirname, 'public')));

// ── MONGOOSE SCHEMA ───────────────────────────────────────────
const orderSchema = new mongoose.Schema({
  t: String,   // телефон
  a: String,   // адрес
  d: String,   // дата
  km: Number,  // ковёр м²
  os: Number,  // одеяло шт
  sk: Number,  // шторы кг
  ps: Number,  // плед шт
  i:  Number,  // итого
  c:  String,  // комментарий
}, { timestamps: true });

const Order = mongoose.model('Order', orderSchema);

const settingsSchema = new mongoose.Schema({
  key: { type: String, unique: true },
  value: String,
});
const Setting = mongoose.model('Setting', settingsSchema);

// ── AUTH MIDDLEWARE ───────────────────────────────────────────
function auth(req, res, next) {
  const pwd = req.headers['x-password'];
  if (pwd !== APP_PASSWORD) return res.status(403).json({ error: 'Неверный пароль' });
  next();
}

// ── API: ПРОВЕРИТЬ ПАРОЛЬ ─────────────────────────────────────
app.post('/api/auth', (req, res) => {
  const { password } = req.body;
  if (password === APP_PASSWORD) res.json({ ok: true });
  else res.status(403).json({ error: 'Неверный пароль' });
});

// ── API: ПОЛУЧИТЬ ВСЕ ЗАКАЗЫ ──────────────────────────────────
app.get('/api/orders', auth, async (req, res) => {
  try {
    const orders = await Order.find().sort({ createdAt: 1 }).lean();
    res.json(orders);
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ── API: ДОБАВИТЬ ЗАКАЗ ───────────────────────────────────────
app.post('/api/orders', auth, async (req, res) => {
  try {
    const order = await Order.create(req.body);
    res.json({ ok: true, _id: order._id });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ── API: МАССОВЫЙ ИМПОРТ ──────────────────────────────────────
app.post('/api/orders/bulk', auth, async (req, res) => {
  try {
    const records = req.body;
    if (!Array.isArray(records) || !records.length)
      return res.status(400).json({ error: 'Пустой массив' });
    const result = await Order.insertMany(records, { ordered: false });
    res.json({ ok: true, inserted: result.length });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ── API: РЕДАКТИРОВАТЬ ЗАКАЗ ──────────────────────────────────
app.put('/api/orders/:id', auth, async (req, res) => {
  try {
    await Order.findByIdAndUpdate(req.params.id, req.body);
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ── API: УДАЛИТЬ ЗАКАЗ ────────────────────────────────────────
app.delete('/api/orders/:id', auth, async (req, res) => {
  try {
    await Order.findByIdAndDelete(req.params.id);
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ── SERVE SPA ─────────────────────────────────────────────────
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// ── START ─────────────────────────────────────────────────────
mongoose.connect(MONGO_URI)
  .then(() => {
    console.log('✅ MongoDB подключена');
    app.listen(PORT, () => console.log(`🚀 Сервер запущен на порту ${PORT}`));
  })
  .catch(err => {
    console.error('❌ Ошибка MongoDB:', err.message);
    process.exit(1);
  });
