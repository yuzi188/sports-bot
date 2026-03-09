"""
主程式入口 - 啟動互動式 Bot
V20.13: 簡化啟動流程，移除排程器 thread，直接啟動 interactive_bot
"""
import sys
import os

# 確保可以導入本地模組
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import interactive_bot


if __name__ == "__main__":
    print("🤖 LA1 智能服務平台 Bot 啟動中...", flush=True)

    # 確認必要環境變數
    bot_token = os.environ.get("BOT_TOKEN", "")
    if not bot_token:
        print("❌ 錯誤：BOT_TOKEN 環境變數未設定！", flush=True)
        sys.exit(1)

    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key:
        print("⚠️  警告：OPENAI_API_KEY 未設定，AI 分析功能將無法使用", flush=True)

    print("✅ 環境變數確認完成，啟動 Bot...", flush=True)

    # 直接啟動互動式 Bot
    # interactive_bot.main() 包含完整的 handler 註冊和 run_polling
    interactive_bot.main()
