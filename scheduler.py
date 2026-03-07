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
    """設定排程"""
    # 每日排程
    schedule.every().day.at(SCHEDULE["morning_preview"]).do(task_morning_preview)
    schedule.every().day.at(SCHEDULE["afternoon_analysis"]).do(task_afternoon_analysis)
    schedule.every().day.at(SCHEDULE["evening_focus"]).do(task_evening_focus)
    schedule.every().day.at(SCHEDULE["night_review"]).do(task_night_review)
    
    # 每週一排名
    schedule.every().monday.at("09:00").do(task_weekly_standings)
    
    log("📅 排程已設定：")
    log(f"  10:00 - 今日賽程預覽")
    log(f"  14:00 - 深度分析")
    log(f"  18:00 - 傍晚焦點戰")
    log(f"  23:00 - 賽後復盤")
    log(f"  每週一 09:00 - 聯賽排名")


def run():
    """啟動排程"""
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
