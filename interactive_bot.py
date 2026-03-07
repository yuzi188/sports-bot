"""
互動式 Telegram Bot v3 - 智能搜尋引擎
"""

import sys
import os
import logging
from datetime import datetime
import pytz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from config import BOT_TOKEN, TIMEZONE
from live_query import search_live_scores, format_response
from smart_search import SPORT_KEYWORDS
from team_db import ALIAS_INDEX

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

tz = pytz.timezone(TIMEZONE)


def is_query(text: str) -> bool:
    """判斷訊息是否為比分查詢"""
    if not text or len(text) < 2 or len(text) > 100:
        return False

    text_lower = text.lower().strip()

    # 1. 運動類型關鍵字
    for sport_kw in SPORT_KEYWORDS:
        if sport_kw.lower() == text_lower or sport_kw in text:
            return True

    # 2. 查詢指示詞
    indicators = [
        "比分", "比數", "戰況", "結果", "怎麼樣",
        "score", "live", "查", "知道", "vs", "VS", "對",
        "wbc", "WBC", "經典賽", "世界棒球",
    ]
    if any(ind in text for ind in indicators):
        return True

    # 3. 已知隊名別名（精確匹配）
    for alias in ALIAS_INDEX:
        if len(alias) >= 2 and alias in text_lower:
            return True

    return False


# ===== 通用回覆 =====

async def reply(update: Update, text: str):
    if update.message:
        await update.message.reply_text(text)
    elif update.channel_post:
        await update.channel_post.reply_text(text)


async def reply_split(update: Update, text: str):
    if len(text) > 4000:
        parts = split_message(text, 4000)
        for part in parts:
            await reply(update, part)
    else:
        await reply(update, text)


# ===== 指令 =====

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("收到 /start")
    await reply(update, """🏟 歡迎來到【世界體育數據室】！

直接輸入隊名或運動類型即可查詢即時比分。

💡 範例：
• 中華台北
• 洋基 紅襪
• WBC
• NBA
• 足球

支援模糊搜尋，打錯字也能查！

📡 t.me/LA11118""")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("收到 /help")
    await reply(update, """📖 使用說明

🔍 查詢方式：
• 輸入隊名：利物浦 曼城
• 輸入運動：棒球、NBA、足球
• WBC 經典賽：WBC、經典賽
• 指令查詢：/score 洋基 紅襪

🧠 智能功能：
• 打錯字也能查（洋機→洋基）
• 自動判斷聯盟
• 附帶近3場戰績

📡 世界體育數據室""")


async def cmd_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    logger.info(f"收到 /score: {query}")
    if not query:
        await reply(update, "⚠️ 請輸入隊名\n範例：/score 洋基 紅襪")
        return
    await handle_score_query(update, query)


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("收到 /today")
    await reply(update, "⏳ 查詢中...")
    try:
        from espn_api import get_today_events
        from formatter import format_scoreboard_message
        events = get_today_events()
        if events:
            msg = format_scoreboard_message(events)
            await reply_split(update, msg)
        else:
            await reply(update, "😴 今日暫無賽事")
    except Exception as e:
        logger.error(f"Today error: {e}")
        await reply(update, "❌ 查詢失敗，請稍後再試")


# ===== 訊息處理 =====

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    logger.info(f"[私訊] {text}")
    if is_query(text):
        await handle_score_query(update, text)


async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    logger.info(f"[群組] {text}")
    if is_query(text):
        await handle_score_query(update, text)


async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.channel_post or not update.channel_post.text:
        return
    text = update.channel_post.text.strip()
    logger.info(f"[頻道] {text}")
    if is_query(text):
        await handle_score_query(update, text)


async def handle_score_query(update: Update, query: str):
    logger.info(f"開始查詢: {query}")
    try:
        result = search_live_scores(query)
        events = result["events"]
        logger.info(f"查詢結果: {len(events)} 場")
        response = format_response(result)
        await reply_split(update, response)
    except Exception as e:
        logger.error(f"Query error: {e}", exc_info=True)
        await reply(update, "❌ 查詢失敗，請稍後再試")


def split_message(text: str, max_len: int = 4000) -> list:
    parts = []
    while text:
        if len(text) <= max_len:
            parts.append(text)
            break
        split_pos = text.rfind("\n", 0, max_len)
        if split_pos == -1:
            split_pos = max_len
        parts.append(text[:split_pos])
        text = text[split_pos:].lstrip("\n")
    return parts


# ===== 主程式 =====

async def setup_commands(app: Application):
    commands = [
        BotCommand("score", "查詢即時比分"),
        BotCommand("today", "今日所有賽事"),
        BotCommand("help", "使用說明"),
    ]
    await app.bot.set_my_commands(commands)


def main():
    logger.info("🤖 啟動智能查詢 Bot v3...")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("score", cmd_score))
    app.add_handler(CommandHandler("today", cmd_today))

    # 私訊
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        handle_message
    ))

    # 群組 / supergroup（Discussion 群組）
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP),
        handle_group_message
    ))

    # 頻道訊息
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.CHANNEL,
        handle_channel_post
    ))

    app.post_init = setup_commands

    logger.info("✅ Bot 已啟動，等待查詢...")
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=["message", "channel_post", "my_chat_member"],
    )


if __name__ == "__main__":
    main()
