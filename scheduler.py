"""
排程管理器 V20.21
整合 LA智能完善版2 的推播任務（promo_post / agent_post / game_recommend_post）
保留原有的體育分析推播排程架構
"""

import sys
import os
import time
import threading
import schedule
from datetime import datetime
import pytz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import TIMEZONE, SCHEDULE, GAME_URL_TW, HUMAN_SUPPORT, BUSINESS_CONTACT
from bot import (
    task_morning_preview,
    task_afternoon_analysis,
    task_evening_focus,
    task_night_review,
    task_weekly_standings,
    task_group_video_promo,
    log,
)
from telegram_sender import test_connection, send_message, send_photo

tz = pytz.timezone(TIMEZONE)

# 每兩小時推播的時間點（台灣時間）
LIVE_BROADCAST_TIMES = [
    "10:00", "12:00", "14:00", "16:00",
    "18:00", "20:00", "22:00", "00:00",
]

DEFAULT_PHOTO = "https://i.imgur.com/8yKQF3K.png"


# ── 新增推播任務（LA智能完善版2）──

def promo_post():
    """推播限時優惠活動"""
    text = f"🔥 LA1 限時活動\n\n首儲1000送1000\n\n立即開始：\n{GAME_URL_TW}"
    send_message(text)
    log("✅ 優惠推播已發送")


def agent_post():
    """推播代理招募"""
    text = f"🤝 代理招募中\n\n高額分潤 / 專屬後台 / 長期合作\n\n商務合作：{BUSINESS_CONTACT}"
    send_message(text)
    log("✅ 代理推播已發送")


def game_recommend_post():
    """推播遊戲推薦（含圖片和按鈕）"""
    caption = (
        "🎰 今日遊戲推薦\n\n"
        "🔥 熱門電子\n"
        "🎲 真人娛樂\n"
        "⚽ 體育投注\n\n"
        "👇 立即體驗"
    )
    keyboard = {
        "inline_keyboard": [
            [{"text": "🎮 立即進入台站", "url": GAME_URL_TW}],
            [{"text": "👑 聯繫客服", "url": f"https://t.me/{HUMAN_SUPPORT.lstrip('@')}"}],
        ]
    }
    send_photo(DEFAULT_PHOTO, caption, keyboard)
    log("✅ 遊戲推薦推播已發送")


def setup_schedule():
    """設定排程"""
    schedule.clear()  # 避免重複呼叫時產生重複排程

    # ── 每日分析推播（已停用，僅保留任務定義供手動觸發）──
    # schedule.every().day.at(SCHEDULE["morning_preview"]).do(task_morning_preview)
    # schedule.every().day.at(SCHEDULE["afternoon_analysis"]).do(task_afternoon_analysis)
    # schedule.every().day.at(SCHEDULE["evening_focus"]).do(task_evening_focus)
    # schedule.every().day.at(SCHEDULE["night_review"]).do(task_night_review)

    # ── 每4小時影片推播（原有）──
    schedule.every(4).hours.do(task_group_video_promo)

    # ── 每日推播任務（LA智能完善版2 新增）──
    schedule.every().day.at("12:00").do(promo_post)
    schedule.every().day.at("18:00").do(game_recommend_post)
    schedule.every().day.at("21:00").do(agent_post)

    # ── 每週一排名 ──
    schedule.every().monday.at("09:00").do(task_weekly_standings)

    log("📅 排程已設定：")
    log("  ── 群組推播 ──")
    log("  每 4 小時 - 影片 + 7個按鈕")
    log("  每日 12:00 - 優惠推播")
    log("  每日 18:00 - 遊戲推薦推播")
    log("  每日 21:00 - 代理推播")
    log("  每週一 09:00 - 聯賽排名")
    log("  ── 已停用 ──")
    log("  每日分析推播 (10:00, 14:00, 18:00, 23:00)")


def start_scheduler():
    """在背景 thread 啟動排程（供 main.py 呼叫）"""
    setup_schedule()

    def _run():
        while True:
            schedule.run_pending()
            time.sleep(30)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    log("✅ 排程器已在背景啟動")


def run():
    """獨立啟動排程（直接執行 scheduler.py 時使用）"""
    log("🤖 世界體育數據室 Bot 排程器啟動中...")

    if not test_connection():
        log("❌ Bot 連接失敗！")
        sys.exit(1)

    log("✅ Bot 連接成功")
    setup_schedule()
    log("⏳ 等待排程執行...")

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    run()
