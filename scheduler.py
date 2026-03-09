"""
排程管理器 - 使用 schedule 庫管理定時任務
v2：新增每兩小時即時推播（直播中熱門賽事）
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
    task_group_video_promo,
    log,
)
# from modules.live_broadcast import task_live_broadcast
from telegram_sender import test_connection

tz = pytz.timezone(TIMEZONE)

# 每兩小時推播的時間點（台灣時間）
# 與每日分析（10:00 / 14:00 / 18:00）重疊時兩者獨立執行，不衝突
LIVE_BROADCAST_TIMES = [
    "10:00", "12:00", "14:00", "16:00",
    "18:00", "20:00", "22:00", "00:00",
]


def setup_schedule():
    """設定排程"""
    schedule.clear()  # 避免重複呼叫時產生重複排程

    # ── 每日分析推播（已停用，僅保留任務定義供手動觸發） ──
    # schedule.every().day.at(SCHEDULE["morning_preview"]).do(task_morning_preview)
    # schedule.every().day.at(SCHEDULE["afternoon_analysis"]).do(task_afternoon_analysis)
    # schedule.every().day.at(SCHEDULE["evening_focus"]).do(task_evening_focus)
    # schedule.every().day.at(SCHEDULE["night_review"]).do(task_night_review)

    # ── 每4小時影片推播（V19.7 新增） ──
    schedule.every(4).hours.do(task_group_video_promo)

    # 每週一排名
    schedule.every().monday.at("09:00").do(task_weekly_standings)

    # ── 每兩小時即時推播（已停用） ──
    # for t in LIVE_BROADCAST_TIMES:
    #     schedule.every().day.at(t).do(task_live_broadcast)

    log("📅 排程已設定：")
    log("  ── 群組推播 ──")
    log("  每 4 小時 - 影片 + 7個按鈕")
    log("  每週一 09:00 - 聯賽排名")
    log("  ── 已停用 ──")
    log("  每日分析推播 (10:00, 14:00, 18:00, 23:00)")
    log("  每兩小時即時推播")


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
