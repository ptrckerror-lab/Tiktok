import os
import sys
import asyncio
import aiohttp
import tempfile
import threading
import traceback
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import FSInputFile
import re
from flask import Flask

# --- ТВОЙ ТОКЕН ВСТАВЛЕН СЮДА ---
BOT_TOKEN = "8565628767:AAGXVQBFwwDqRcDG4QTa45oSnOyj1B9Wbq8"
# --------------------------------

TIKTOK_API = "https://www.tikwm.com/api/"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = Flask(__name__)

# --- ЛОГИРОВАНИЕ ---
def log(msg_type, user=None, action="", details=""):
    time = datetime.now().strftime("%H:%M:%S")
    prefix = {"INFO": "ℹ️", "ERROR": "❌", "SUCCESS": "✅", "BOT": "🤖"}.get(msg_type, "•")
    line = f"[{time}] {prefix} [{msg_type}]"
    if user: line += f" @{user}"
    if action: line += f" | {action}"
    print(line)
    if details: print(f"     └─ {details}")

# --- ПРОВЕРКА ССЫЛКИ ---
def is_tiktok_url(text):
    if not text: return False
    return re.match(r'https?://([a-z0-9-]+\.)?tiktok\.com/.+', text, re.I) is not None

# --- ЗАПРОС К API ---
async def get_video(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(TIKTOK_API, params={'url': url}, timeout=30) as r:
                if r.status == 200:
                    data = await r.json()
                    if data.get('code') == 0 and data.get('data'):
                        return data['data']
                log("ERROR", action=f"API status: {r.status}")
    except Exception as e:
        log("ERROR", action="API request failed", details=str(e))
    return None

# --- КОМАНДА /start ---
@dp.message(Command("start"))
async def start(msg: types.Message):
    user = msg.from_user.username or msg.from_user.id
    log("INFO", user, "Команда /start")
    try:
        await msg.answer(
            "🤖 SAVE TIKTOK BOT\n\n"
            "📥 Отправь ссылку на TikTok\n"
        )
        log("SUCCESS", user, "Ответ отправлен")
    except Exception as e:
        log("ERROR", user, "Не удалось отправить сообщение", str(e))

# --- ОБРАБОТКА ССЫЛОК ---
@dp.message()
async def handle(msg: types.Message):
    text = msg.text
    if not text or not is_tiktok_url(text): return
    
    user = msg.from_user.username or msg.from_user.id
    log("INFO", user, "Получена ссылка", text[:50])
    
    status = await msg.answer("⏳ Обрабатываю...")
    
    try:
        data = await get_video(text)
        if not data:
            await status.edit_text("❌ Ошибка. Проверь ссылку.")
            log("ERROR", user, "Не удалось получить данные")
            return
        
        author = data.get('author', {}).get('unique_id', 'unknown')
        title = data.get('title', 'TikTok')[:100]
        
        v_url = data.get('play')
        a_url = data.get('music')
        if v_url and not v_url.startswith('http'): v_url = f"https://www.tikwm.com{v_url}"
        if a_url and not a_url.startswith('http'): a_url = f"https://www.tikwm.com{a_url}"
        
        if not v_url:
            await status.edit_text("❌ Нет ссылки на видео")
            return
        
        tmp = tempfile.gettempdir()
        vid_path = os.path.join(tmp, f"v_{msg.message_id}.mp4")
        
        log("INFO", user, "Скачиваю видео...")
        await status.edit_text("📥 Скачиваю...")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(v_url, timeout=60) as r:
                if r.status == 200:
                    with open(vid_path, 'wb') as f: f.write(await r.read())
                else: raise Exception(f"HTTP {r.status}")
        
        log("INFO", user, "Отправляю видео...")
        await status.edit_text("📤 Отправляю...")
        await msg.answer_video(FSInputFile(vid_path), caption=f"🎬 {title}\n👤 @{author}")
        
        if a_url:
            aud_path = os.path.join(tmp, f"a_{msg.message_id}.mp3")
            async with aiohttp.ClientSession() as session:
                async with session.get(a_url, timeout=60) as r:
                    if r.status == 200:
                        with open(aud_path, 'wb') as f: f.write(await r.read())
            await msg.answer_audio(FSInputFile(aud_path), caption="🎵 Аудио")
            if os.path.exists(aud_path): os.remove(aud_path)
        
        if os.path.exists(vid_path): os.remove(vid_path)
        await status.delete()
        log("SUCCESS", user, "Готово", title[:30])
        
    except Exception as e:
        log("ERROR", user, "Критическая ошибка", str(e))
        traceback.print_exc()
        await status.edit_text("❌ Ошибка. Попробуй позже.")

# --- ЗАПУСК БОТА ---
def run_bot():
    try:
        log("BOT", action="Запуск polling...")
        asyncio.run(dp.start_polling(bot))
    except Exception as e:
        log("ERROR", action="Bot crashed!", details=str(e))
        traceback.print_exc()

# --- FLASK ДЛЯ RENDER ---
@app.route("/")
def home(): return "✅ Borman Bot is running"

@app.route("/health")
def health(): return {"status": "ok", "bot": "running"}

# --- ГЛАВНЫЙ ЗАПУСК ---
if __name__ == "__main__":
    log("BOT", action="=== BORMAN BOT STARTING ===")
    log("INFO", action=f"Python: {sys.version}")
    log("INFO", action=f"Token loaded: {'Yes' if BOT_TOKEN else 'No'}")
    
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    port = int(os.environ.get("PORT", 5000))
    log("BOT", action=f"Starting Flask on port {port}")
    app.run(host="0.0.0.0", port=port)