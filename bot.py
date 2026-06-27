import os
import sqlite3
import logging
from datetime import datetime, timedelta, date
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)

TOKEN = os.environ.get("8848510567: AAHjxbqFWbFXYTsVXYkom 6e8AuhZ6aXdkeY")
DB = "work.db"
BREAK_MINUTES = 30

def init_db():
    with sqlite3.connect(DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                start_time TEXT,
                end_time TEXT,
                duration_minutes REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS active (
                user_id INTEGER PRIMARY KEY,
                start_time TEXT
            )
        """)

def get_active(user_id):
    with sqlite3.connect(DB) as conn:
        row = conn.execute(
            "SELECT start_time FROM active WHERE user_id=?", (user_id,)
        ).fetchone()
        return row[0] if row else None

def set_active(user_id, start_time):
    with sqlite3.connect(DB) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO active VALUES (?,?)", (user_id, start_time)
        )

def clear_active(user_id):
    with sqlite3.connect(DB) as conn:
        conn.execute("DELETE FROM active WHERE user_id=?", (user_id,))

def save_session(user_id, start, end, minutes):
    with sqlite3.connect(DB) as conn:
        conn.execute(
            "INSERT INTO sessions VALUES (NULL,?,?,?,?)",
            (user_id, start, end, minutes)
        )

def get_stats(user_id, from_date, to_date):
    with sqlite3.connect(DB) as conn:
        rows = conn.execute("""
            SELECT duration_minutes FROM sessions
            WHERE user_id=?
              AND DATE(start_time) >= ?
              AND DATE(start_time) <= ?
        """, (user_id, from_date.isoformat(), to_date.isoformat())).fetchall()
    return sum(r[0] for r in rows)

def fmt(minutes):
    h = int(minutes // 60)
    m = int(minutes % 60)
    return f"{h} ч {m} мин"

KEYBOARD = ReplyKeyboardMarkup(
    [["▶️ Старт", "⏹ Стоп"],
     ["📅 День", "📆 Неделя", "🗓 Месяц"]],
    resize_keyboard=True
)

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Трекер рабочего времени*\n\nНажми ▶️ Старт когда начинаешь работать.",
        parse_mode="Markdown",
        reply_markup=KEYBOARD
    )

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    user_id = update.effective_user.id
    now = datetime.now()

    if any(w in text for w in ["старт", "start", "начало"]):
        if get_active(user_id):
            await update.message.reply_text("⚠️ Сессия уже идёт. Сначала нажми ⏹ Стоп.", reply_markup=KEYBOARD)
            return
        set_active(user_id, now.isoformat())
        await update.message.reply_text(
            f"✅ Начало работы: *{now.strftime('%H:%M')}*",
            parse_mode="Markdown", reply_markup=KEYBOARD
        )

    elif any(w in text for w in ["стоп", "stop", "конец"]):
        start_str = get_active(user_id)
        if not start_str:
            await update.message.reply_text("⚠️ Сессия не начата. Нажми ▶️ Старт.", reply_markup=KEYBOARD)
            return
        start_dt = datetime.fromisoformat(start_str)
        raw = (now - start_dt).total_seconds() / 60
        work = max(0, raw - BREAK_MINUTES)
        save_session(user_id, start_str, now.isoformat(), work)
        clear_active(user_id)
        await update.message.reply_text(
            f"⏹ Конец: *{now.strftime('%H:%M')}*\n"
            f"🕐 Всего времени: {fmt(raw)}\n"
            f"☕ Перерыв: 30 мин\n"
            f"✅ Чистое время: *{fmt(work)}*",
            parse_mode="Markdown", reply_markup=KEYBOARD
        )

    elif "день" in text:
        today = date.today()
        mins = get_stats(user_id, today, today)
        await update.message.reply_text(
            f"📅 Сегодня ({today.strftime('%d.%m')}): *{fmt(mins)}*",
            parse_mode="Markdown", reply_markup=KEYBOARD
        )

    elif "неделя" in text:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        mins = get_stats(user_id, week_start, today)
        await update.message.reply_text(
            f"📆 Неделя ({week_start.strftime('%d.%m')} – {today.strftime('%d.%m')}): *{fmt(mins)}*",
            parse_mode="Markdown", reply_markup=KEYBOARD
        )

    elif "месяц" in text:
        today = date.today()
        month_start = today.replace(day=1)
        mins = get_stats(user_id, month_start, today)
        await update.message.reply_text(
            f"🗓 Месяц ({today.strftime('%B')}): *{fmt(mins)}*",
            parse_mode="Markdown", reply_markup=KEYBOARD
        )

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Бот запущен...")
    app.run_polling()
