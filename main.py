"""
主程式入口 - 同時執行排程器與互動式 Bot
"""

import threading
import time
import sys
import os
import schedule

# 確保可以導入本地模組
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram_sender import test_connection
from scheduler import setup_schedule
import interactive_bot


def run_scheduler():
    """執行排程器（連接測試已在主程式完成，直接設定排程）"""
    from bot import log
    setup_schedule()
    log("⏳ 排程器等待執行...")
    while True:
        schedule.run_pending()
        time.sleep(30)


def run_interactive_bot():
    """執行互動式 Bot"""
    print("啟動互動式 Bot...")
    interactive_bot.main()


if __name__ == "__main__":
    print("🤖 世界體育數據室 Bot 啟動中...")

    # 測試 Bot 連接（只測試一次）
    if not test_connection():
        print("❌ Bot 連接失敗！請檢查 BOT_TOKEN 是否正確設定。")
        sys.exit(1)

    print("✅ Bot 連接成功")

    # 排程器執行緒（背景執行）
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    print("✅ 排程器已啟動")

    # 互動式 Bot 在主執行緒執行（python-telegram-bot 需要主執行緒的事件迴圈）
    print("✅ 啟動互動式 Bot...")
    run_interactive_bot()
