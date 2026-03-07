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
    """執行排程器（在背景 daemon thread 中執行）"""
    try:
        from bot import log
        setup_schedule()
        log("⏳ 排程器等待執行...")
        while True:
            schedule.run_pending()
            time.sleep(30)
    except Exception as e:
        print(f"[排程器] 發生錯誤: {e}", flush=True)
        import traceback
        traceback.print_exc()


def run_interactive_bot():
    """執行互動式 Bot（在主執行緒執行，供 asyncio event loop 使用）"""
    print("✅ 啟動互動式 Bot...", flush=True)
    interactive_bot.main()


if __name__ == "__main__":
    print("🤖 世界體育數據室 Bot 啟動中...", flush=True)

    # 確認必要環境變數
    bot_token = os.environ.get("BOT_TOKEN", "")
    if not bot_token:
        print("❌ 錯誤：BOT_TOKEN 環境變數未設定！", flush=True)
        sys.exit(1)

    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key:
        print("⚠️  警告：OPENAI_API_KEY 未設定，AI 分析功能將無法使用", flush=True)

    # 測試 Telegram Bot 連接（只測試一次）
    print("🔌 測試 Telegram Bot 連接...", flush=True)
    if not test_connection():
        print("❌ Bot 連接失敗！請確認 BOT_TOKEN 是否正確。", flush=True)
        sys.exit(1)

    print("✅ Bot 連接成功", flush=True)

    # 排程器在背景 daemon thread 執行
    scheduler_thread = threading.Thread(target=run_scheduler, name="scheduler", daemon=True)
    scheduler_thread.start()
    print("✅ 排程器已啟動（背景執行緒）", flush=True)

    # 互動式 Bot 在主執行緒執行
    # python-telegram-bot v20+ 使用 asyncio，必須在主執行緒建立 event loop
    run_interactive_bot()
