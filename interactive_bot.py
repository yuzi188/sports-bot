"""
互動式 Telegram Bot V5.3 - 全功能智能體育查詢 + AI 客服聊天
全部使用免費 API（ESPN + OpenAI 已有 key）
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


# ===== 查詢判斷 =====

EXTRA_KEYWORDS = [
    "即時", "比分", "比數", "戰況", "結果", "怎麼樣",
    "score", "live", "查", "知道", "vs", "VS", "對",
    "wbc", "WBC", "經典賽", "世界棒球",
    "排行", "射手", "全壘打", "得分王",
    "熱門", "焦點", "推薦",
    "分析", "預測",
]


def is_query(text: str) -> bool:
    """判斷訊息是否為比分查詢"""
    if not text or len(text) < 2 or len(text) > 100:
        return False

    text_lower = text.lower().strip()

    # 運動類型關鍵字
    for sport_kw in SPORT_KEYWORDS:
        if sport_kw.lower() == text_lower or sport_kw in text:
            return True

    # 查詢指示詞
    if any(ind in text for ind in EXTRA_KEYWORDS):
        return True

    # 已知隊名別名
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


# ===== AI 客服聊天 =====

async def handle_ai_chat(update: Update, text: str):
    """當訊息不是比分查詢時，交由 AI 客服回應"""
    try:
        from modules.ai_chat import get_ai_response

        # 取得用戶 ID（私訊用 user.id，群組也用 user.id）
        user_id = 0
        if update.message and update.message.from_user:
            user_id = update.message.from_user.id

        logger.info(f"[AI 客服] 用戶 {user_id}: {text}")
        ai_reply = get_ai_response(user_id, text)
        await reply(update, ai_reply)

    except Exception as e:
        logger.error(f"AI 客服錯誤: {e}", exc_info=True)
        await reply(update, "😅 抱歉，AI 助理暫時無法回應，請稍後再試！\n\n💡 你可以直接輸入隊名查詢比分，例如：洋基、NBA、英超")


# ===== 指令 =====

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("收到 /start")
    await reply(update, """🏟 歡迎來到【世界體育數據室】V5.3

直接輸入隊名或運動類型即可查詢。

💡 查詢範例：
• 中華台北
• 洋基 紅襪
• WBC / NBA / 足球

📊 指令：
• /score 隊名 → 即時比分
• /today → 今日所有賽事
• /live → 進行中的比賽
• /hot → 今日熱門賽事
• /leaders → 排行榜
• /analyze 隊名 → AI 分析預測
• /help → 使用說明

🤖 有任何問題都可以直接問我！
📡 t.me/LA11118""")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("收到 /help")
    await reply(update, """📖 使用說明 V5.3

🔍 查詢方式：
• 直接輸入隊名：利物浦 曼城
• 輸入運動類型：棒球、NBA、足球
• WBC 經典賽：WBC、經典賽

📊 指令列表：
• /score 隊名 → 即時比分 + 近3場戰績
• /today → 今日所有賽事總覽
• /live → 目前進行中的比賽
• /hot → 今日熱門焦點賽事
• /leaders → MLB全壘打/NBA得分/足球射手榜
• /analyze 隊名 → AI 賽事分析預測
• /odds 隊名 → 盤口資訊

🧠 智能功能：
• 打錯字也能查（洋機→洋基）
• 自動判斷聯盟（不會混搭）
• 每次查詢附帶近3場戰績
• AI 專業分析預測
• 🤖 AI 客服聊天（直接問問題！）

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
    await reply(update, "⏳ 查詢今日所有賽事中...")
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


async def cmd_live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查詢目前進行中的比賽"""
    logger.info("收到 /live")
    await reply(update, "⏳ 查詢進行中的比賽...")
    try:
        from modules.live_scores import get_live_scores
        scores = get_live_scores()
        if scores:
            sep = "═" * 24
            lines = [sep, "🔴 目前進行中的比賽", sep, ""]
            lines.extend(scores)
            lines.extend(["", f"📊 共 {len(scores)} 場進行中", "📡 世界體育數據室"])
            await reply_split(update, "\n".join(lines))
        else:
            await reply(update, "😴 目前沒有進行中的比賽")
    except Exception as e:
        logger.error(f"Live error: {e}")
        await reply(update, "❌ 查詢失敗，請稍後再試")


async def cmd_hot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """今日熱門賽事"""
    logger.info("收到 /hot")
    await reply(update, "⏳ 查詢今日熱門賽事...")
    try:
        from modules.hot_matches import get_hot_matches
        matches = get_hot_matches(10)
        if matches:
            sep = "═" * 24
            lines = [sep, "🔥 今日熱門賽事", sep, ""]
            lines.extend(matches)
            lines.extend(["", "📡 世界體育數據室"])
            await reply_split(update, "\n".join(lines))
        else:
            await reply(update, "😴 今日暫無熱門賽事")
    except Exception as e:
        logger.error(f"Hot error: {e}")
        await reply(update, "❌ 查詢失敗，請稍後再試")


async def cmd_leaders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """排行榜"""
    logger.info("收到 /leaders")
    args = " ".join(context.args).lower() if context.args else ""

    await reply(update, "⏳ 查詢排行榜...")
    try:
        from modules.leaders import (
            get_mlb_hr_leaders,
            get_nba_scoring_leaders,
            get_football_scorers,
        )

        if "mlb" in args or "棒球" in args or "全壘打" in args:
            result = get_mlb_hr_leaders()
        elif "nba" in args or "籃球" in args or "得分" in args:
            result = get_nba_scoring_leaders()
        elif "足球" in args or "英超" in args or "射手" in args:
            result = get_football_scorers()
        else:
            # 預設顯示全部
            parts = []
            parts.append(get_mlb_hr_leaders(5))
            parts.append(get_nba_scoring_leaders(5))
            parts.append(get_football_scorers("eng.1", 5))
            result = "\n\n".join(parts)

        sep = "═" * 24
        msg = f"{sep}\n🏆 排行榜\n{sep}\n\n{result}\n\n{sep}\n📡 世界體育數據室"
        await reply_split(update, msg)
    except Exception as e:
        logger.error(f"Leaders error: {e}")
        await reply(update, "❌ 查詢失敗，請稍後再試")


async def cmd_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """AI 分析預測"""
    query = " ".join(context.args) if context.args else ""
    logger.info(f"收到 /analyze: {query}")
    if not query:
        await reply(update, "⚠️ 請輸入隊名\n範例：/analyze 洋基 紅襪")
        return

    await reply(update, "🤖 AI 分析中...")
    try:
        result = search_live_scores(query)
        events = result["events"]
        recent = result.get("recent_history", {})

        if not events and not recent:
            await reply(update, f"😴 找不到「{query}」的相關比賽")
            return

        # 組合比賽資訊
        info_parts = []
        for e in events[:5]:
            home = e["home"]
            away = e["away"]
            if e["state"] == "post":
                info_parts.append(f"{away['name']} {away['score']} - {home['score']} {home['name']} (已結束)")
            elif e["state"] == "in":
                info_parts.append(f"{away['name']} {away['score']} - {home['score']} {home['name']} (進行中 {e['status_detail']})")
            else:
                info_parts.append(f"{away['name']} vs {home['name']} (未開始)")

        # 加入近期戰績
        for team_cn, matches in recent.items():
            if matches:
                info_parts.append(f"\n{team_cn} 近期戰績：")
                for m in matches:
                    info_parts.append(f"  {m['date']} {m['away']} {m['away_score']} - {m['home_score']} {m['home']}")

        match_info = "\n".join(info_parts)

        from modules.ai_predict import generate_match_analysis
        analysis = generate_match_analysis(match_info)

        # 格式化回覆
        sep = "═" * 24
        dash = "─" * 20
        parsed = result["parsed"]
        team_names = " / ".join(t["cn_name"] for t in parsed["teams"]) if parsed["teams"] else query

        lines = [sep, f"🤖 AI 分析：{team_names}", sep, ""]

        for e in events[:3]:
            home = e["home"]
            away = e["away"]
            emoji = e["emoji"]
            if e["state"] == "post":
                lines.append(f"{emoji} {away['name']} {away['score']} - {home['score']} {home['name']} ✅")
            elif e["state"] == "in":
                lines.append(f"{emoji} {away['name']} {away['score']} - {home['score']} {home['name']} 🔴")
            else:
                lines.append(f"{emoji} {away['name']} vs {home['name']} ⏰")

        lines.extend(["", dash, "🧠 AI 專業分析", dash, "", analysis, ""])

        # 近期戰績
        for team_cn, matches in recent.items():
            if matches:
                lines.append(f"📋 {team_cn} 近期戰績：")
                for m in matches:
                    lines.append(f"  {m['emoji']} {m['date']} {m['away']} {m['away_score']} - {m['home_score']} {m['home']}")
                lines.append("")

        lines.extend([sep, "📡 世界體育數據室", "⚠️ AI 分析僅供參考"])
        await reply_split(update, "\n".join(lines))

    except Exception as e:
        logger.error(f"Analyze error: {e}", exc_info=True)
        await reply(update, "❌ 分析失敗，請稍後再試")


async def cmd_odds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """盤口資訊"""
    query = " ".join(context.args) if context.args else ""
    logger.info(f"收到 /odds: {query}")
    if not query:
        await reply(update, "⚠️ 請輸入隊名\n範例：/odds 洋基")
        return

    await reply(update, "⏳ 查詢盤口中...")
    try:
        from smart_search import smart_parse, match_event_smart, translate_name
        from modules.odds_info import get_odds_for_event, format_odds
        import requests
        from config import ESPN_BASE

        parsed = smart_parse(query)
        teams = parsed["teams"]
        endpoints = parsed["endpoints"]

        if not teams:
            await reply(update, f"😴 找不到「{query}」的相關隊伍")
            return

        lines = ["═" * 24, f"💰 盤口資訊：{' / '.join(t['cn_name'] for t in teams)}", "═" * 24, ""]

        found = 0
        for sport, league, emoji in endpoints:
            try:
                url = f"{ESPN_BASE}/{sport}/{league}/scoreboard"
                resp = requests.get(url, timeout=10)
                if resp.status_code != 200:
                    continue
                data = resp.json()

                for event in data.get("events", []):
                    if not match_event_smart(event, teams):
                        continue

                    comp = event.get("competitions", [{}])[0]
                    competitors = comp.get("competitors", [])
                    home = away = None
                    for c in competitors:
                        team = c.get("team", {})
                        td = {"name": translate_name(team.get("displayName", ""))}
                        if c.get("homeAway") == "home":
                            home = td
                        else:
                            away = td

                    if home and away:
                        lines.append(f"{emoji} {away['name']} vs {home['name']}")
                        odds = get_odds_for_event(event)
                        if odds:
                            lines.append(format_odds(odds))
                        else:
                            lines.append("📊 暫無盤口資訊")
                        lines.append("")
                        found += 1
            except:
                continue

        if found == 0:
            await reply(update, f"😴 找不到「{query}」的盤口資訊")
            return

        lines.extend(["═" * 24, "📡 世界體育數據室", "⚠️ 盤口僅供參考"])
        await reply_split(update, "\n".join(lines))

    except Exception as e:
        logger.error(f"Odds error: {e}", exc_info=True)
        await reply(update, "❌ 查詢失敗，請稍後再試")


# ===== 訊息處理 =====

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理私訊：比分查詢優先，其餘交由 AI 客服回應"""
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    logger.info(f"[私訊] {text}")

    text_lower = text.lower()

    # 特殊關鍵字優先路由
    if any(kw in text_lower for kw in ["即時", "live", "進行中"]):
        await cmd_live(update, context)
    elif any(kw in text_lower for kw in ["熱門", "焦點", "推薦"]):
        await cmd_hot(update, context)
    elif any(kw in text_lower for kw in ["排行", "射手", "全壘打", "得分王"]):
        context.args = text.split()[1:] if len(text.split()) > 1 else []
        await cmd_leaders(update, context)
    elif any(kw in text_lower for kw in ["分析", "預測", "analyze"]):
        # 移除關鍵字取得隊名
        clean_text = text
        for kw in ["分析", "預測", "analyze"]:
            clean_text = clean_text.replace(kw, "").strip()
        if clean_text:
            context.args = clean_text.split()
            await cmd_analyze(update, context)
        else:
            await reply(update, "⚠️ 請輸入隊名\n範例：洋基 分析")
    elif is_query(text):
        # 識別為比分查詢
        await handle_score_query(update, text)
    else:
        # 非比分查詢 → 交由 AI 客服回應
        await handle_ai_chat(update, text)


async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理群組訊息：比分查詢優先，其餘交由 AI 客服回應"""
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    logger.info(f"[群組] {text}")

    text_lower = text.lower()

    if any(kw in text_lower for kw in ["即時", "live", "進行中"]):
        await cmd_live(update, context)
    elif any(kw in text_lower for kw in ["熱門", "焦點", "推薦"]):
        await cmd_hot(update, context)
    elif any(kw in text_lower for kw in ["排行", "射手", "全壘打", "得分王"]):
        context.args = text.split()[1:] if len(text.split()) > 1 else []
        await cmd_leaders(update, context)
    elif any(kw in text_lower for kw in ["分析", "預測", "analyze"]):
        clean_text = text
        for kw in ["分析", "預測", "analyze"]:
            clean_text = clean_text.replace(kw, "").strip()
        if clean_text:
            context.args = clean_text.split()
            await cmd_analyze(update, context)
    elif is_query(text):
        await handle_score_query(update, text)
    else:
        # 群組中非查詢訊息也交由 AI 客服回應
        await handle_ai_chat(update, text)


async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理頻道訊息（頻道不做 AI 聊天，只處理查詢）"""
    if not update.channel_post or not update.channel_post.text:
        return
    text = update.channel_post.text.strip()
    logger.info(f"[頻道] {text}")

    text_lower = text.lower()
    if any(kw in text_lower for kw in ["即時", "live", "進行中"]):
        await cmd_live(update, context)
    elif any(kw in text_lower for kw in ["熱門", "焦點", "推薦"]):
        await cmd_hot(update, context)
    elif is_query(text):
        await handle_score_query(update, text)


async def handle_score_query(update: Update, query: str):
    """處理比分查詢"""
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
        BotCommand("live", "進行中的比賽"),
        BotCommand("hot", "今日熱門賽事"),
        BotCommand("leaders", "排行榜"),
        BotCommand("analyze", "AI 分析預測"),
        BotCommand("odds", "盤口資訊"),
        BotCommand("help", "使用說明"),
    ]
    await app.bot.set_my_commands(commands)


def main():
    logger.info("🤖 啟動智能查詢 Bot V5.3（含 AI 客服）...")

    app = Application.builder().token(BOT_TOKEN).build()

    # 指令
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("score", cmd_score))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("live", cmd_live))
    app.add_handler(CommandHandler("hot", cmd_hot))
    app.add_handler(CommandHandler("leaders", cmd_leaders))
    app.add_handler(CommandHandler("analyze", cmd_analyze))
    app.add_handler(CommandHandler("odds", cmd_odds))

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

    logger.info("✅ Bot V5.3 已啟動，等待查詢...")
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=["message", "channel_post", "my_chat_member"],
    )


if __name__ == "__main__":
    main()
