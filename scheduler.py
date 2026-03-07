"""
排程管理器 - 使用 schedule 庫管理定時任務
"""
import sys
import os
import time
import schedule
from datetime import datetime
import pytz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import TIMEZONE, SCHEDULE
from bot import (
    task_morning_preview,
    task_afternoon_analysis,
    task_evening_focus,
    task_night_review,
    task_weekly_standings,
    log,
)
from telegram_sender import test_connection

tz = pytz.timezone(TIMEZONE)


def setup_schedule():
    """設定排程（使用台灣時間 Asia/Taipei）"""
    # 清除舊排程，避免重複
    schedule.clear()

    # 每日排程（指定 tz=tz 確保使用台灣時間，不受 Railway 伺服器時區影響）
    schedule.every().day.at(SCHEDULE["morning_preview"], tz).do(task_morning_preview)
    schedule.every().day.at(SCHEDULE["afternoon_analysis"], tz).do(task_afternoon_analysis)
    schedule.every().day.at(SCHEDULE["evening_focus"], tz).do(task_evening_focus)
    schedule.every().day.at(SCHEDULE["night_review"], tz).do(task_night_review)

    # 每週一排名（台灣時間 09:00）
    schedule.every().monday.at("09:00", tz).do(task_weekly_standings)

    log("📅 排程已設定（台灣時間）：")
    log(f"  {SCHEDULE['morning_preview']} - 今日賽程預覽")
    log(f"  {SCHEDULE['afternoon_analysis']} - 深度分析")
    log(f"  {SCHEDULE['evening_focus']} - 傍晚焦點戰")
    log(f"  {SCHEDULE['night_review']} - 賽後復盤")
    log(f"  每週一 09:00 - 聯賽排名")


def run():
    """啟動排程（standalone 模式使用）"""
    log("🤖 世界體育數據室 Bot 啟動中...")

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
