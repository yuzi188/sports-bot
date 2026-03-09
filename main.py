from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from config import BOT_TOKEN, validate_config
from telegram_ui import main_menu
from ai_service import ai_reply
from scheduler import start_scheduler
from sports_service import build_sports_digest

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
🐼 LA1 智能服務平台

AI客服｜AI體育分析｜娛樂城入口

🔥 首儲1000送1000（限時活動）

👇 點擊下方選擇服務
"""
    await update.message.reply_text(text, reply_markup=main_menu())

async def sports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = await build_sports_digest()
    await update.message.reply_text(text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text or ""
    reply = await ai_reply(user_text)
    await update.message.reply_text(reply)

def main():
    validate_config()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("sports", sports))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    start_scheduler()

    print("🤖 LA1_BOT_V15_ENTERPRISE running")
    app.run_polling()

if __name__ == "__main__":
    main()
