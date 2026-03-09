import threading
import time
import schedule
from telegram_sender import send_message
from config import GAME_URL_TW, HUMAN_SUPPORT, BUSINESS_CONTACT
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram_sender import send_photo

DEFAULT_PHOTO = "https://i.imgur.com/8yKQF3K.png"

def promo_post():
    text = f"🔥 LA1 限時活動\n\n首儲1000送1000\n\n立即開始：\n{GAME_URL_TW}"
    send_message(text)

def agent_post():
    text = f"🤝 代理招募中\n\n高額分潤 / 專屬後台 / 長期合作\n\n商務合作：{BUSINESS_CONTACT}"
    send_message(text)

def game_recommend_post():
    caption = """
🎰 今日遊戲推薦

🔥 熱門電子
🎲 真人娛樂
⚽ 體育投注

👇 立即體驗
"""
    keyboard = {
        "inline_keyboard": [
            [{"text":"🎮 立即進入台站","url": GAME_URL_TW}],
            [{"text":"👑 聯繫客服","url": f"https://t.me/{HUMAN_SUPPORT.lstrip('@')}"}]
        ]
    }
    send_photo(DEFAULT_PHOTO, caption, keyboard)

def run_scheduler():
    schedule.every().day.at("12:00").do(promo_post)
    schedule.every().day.at("18:00").do(game_recommend_post)
    schedule.every().day.at("21:00").do(agent_post)

    while True:
        schedule.run_pending()
        time.sleep(30)

def start_scheduler():
    t = threading.Thread(target=run_scheduler, daemon=True)
    t.start()
