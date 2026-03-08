"""
互動式 Telegram Bot V11 - 上下文感知 + AI 全接管 + 即時詳細資料 + 娛樂城選單 + 歡迎訊息
新增：底部固定鍵盤選單、新成員歡迎訊息、/start 優化
"""

import sys
import os
import logging
from datetime import datetime
import pytz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram import Update, BotCommand, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from config import BOT_TOKEN, TIMEZONE
from live_query import (
    search_live_scores, format_response,
    get_upcoming_matches, format_upcoming_response,
)
from modules.game_details import get_live_game_details, format_game_details
from smart_search import SPORT_KEYWORDS
from team_db import ALIAS_INDEX

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

tz = pytz.timezone(TIMEZONE)


# ===== 娛樂城設定 =====

GAME_URL = "http://la1111.ofa168hk.com/"
CHANNEL_URL = "https://t.me/LA11118"
CS_URL = "https://t.me/OFA168Abe1"
TARGET_GROUP = "@G5ofa"

# 底部固定鍵盤（私訊用）
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🎮 遊戲"],
        ["💰 帳戶", "📢 官方頻道"],
        ["👥 客服列表"],
    ],
    resize_keyboard=True,
    is_persistent=True,
)

# 按鈕文字常數（方便比對）
BTN_GAME = "🎮 遊戲"
BTN_ACCOUNT = "💰 帳戶"
BTN_CHANNEL = "📢 官方頻道"
BTN_CS = "👥 客服列表"
MENU_BUTTONS = {BTN_GAME, BTN_ACCOUNT, BTN_CHANNEL, BTN_CS}


# ===== 查詢判斷（保留作為 fallback） =====

EXTRA_KEYWORDS = [
    "即時", "比分", "比數", "戰況", "結果", "怎麼樣",
    "score", "live", "查", "知道", "vs", "VS", "對",
    "wbc", "WBC", "經典賽", "世界棒球",
    "排行", "射手", "全壘打", "得分王",
    "熱門", "焦點", "推薦",
    "分析", "預測",
]

# 詳細資料關鍵字（觸發即時詳細資料查詢）
DETAIL_KEYWORDS = [
    "先發投手", "先發", "投手", "投球", "現場投手",
    "打者", "打席", "局數", "上半局", "下半局",
    "壞上", "壞包", "壞數", "壞式", "出局",
    "進球", "進球者", "助攻", "換人",
    "節次", "剩餘時間", "各節得分",
    "黃牌", "紅牌", "詳細", "現場狀況",
]


def is_query(text: str) -> bool:
    """判斷訊息是否為比分查詢（fallback 用）"""
    if not text or len(text) < 2 or len(text) > 100:
        return False

    text_lower = text.lower().strip()

    for sport_kw in SPORT_KEYWORDS:
        if sport_kw.lower() == text_lower or sport_kw in text:
            return True

    if any(ind in text for ind in EXTRA_KEYWORDS):
        return True

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
    welcome_text = (
        "🏆 歡迎來到 世界體育數據室！\n\n"
        "✅ MLB / NBA / NHL / 足球 即時比分\n"
        "✅ AI 勝率預測與比賽分析\n"
        "✅ 直接問任何體育問題，不需要指令！\n\n"
        f"🎮 合作娛樂平台：{GAME_URL}\n\n"
        "立即點擊下方【🎮 遊戲】進入！"
    )
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=MAIN_KEYBOARD)
    elif update.channel_post:
        await update.channel_post.reply_text(welcome_text)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("收到 /help")
    await reply(update, """📖 使用說明 V9

🔍 查詢方式：
• 直接輸入隊名：利物浦 曼城
• 輸入運動類型：棒球、NBA、足球
• WBC 經典賽：WBC、經典賽
• 問「日本下場對誰」→ AI 自動查未來賽程

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
• AI 理解上下文追問（「他們下場呢？」）
• 🤖 AI 客服聊天（直接問問題！）

📡 世界體育數據室""")


async def cmd_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else ""
    logger.info(f"收到 /score: {query}")
    if not query:
        await reply(update, "⚠️ 請輸入隊名\n範例：/score 洋基 紅襪")
        return
    await handle_score_query(update, query)


async def cmd_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查詢指定比賽的即時詳細資料（投手/打者/進球/換人）"""
    query = " ".join(context.args) if context.args else ""
    logger.info(f"收到 /details: {query}")
    if not query:
        await reply(update, "⚠️ 請輸入隊名\n範例：/details 洋基\n\n會自動查詢進行中比賽的詳細資料")
        return
    await handle_details_query(update, query)


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

        for team_cn, matches in recent.items():
            if matches:
                info_parts.append(f"\n{team_cn} 近期戰績：")
                for m in matches:
                    info_parts.append(f"  {m['date']} {m['away']} {m['away_score']} - {m['home_score']} {m['home']}")

        match_info = "\n".join(info_parts)

        from modules.ai_predict import generate_match_analysis, generate_win_probability
        analysis = generate_match_analysis(match_info)
        win_prob = generate_win_probability(match_info)

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

        lines.extend(["", dash, "📊 AI 勝率預測", dash, "", win_prob, ""])
        lines.extend(["", dash, "🧠 AI 專業分析", dash, "", analysis, ""])

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


# ===== 娛樂城選單按鈕處理 =====

async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    """
    處理底部固定鍵盤的按鈕點擊。
    回傳 True 表示已處理，False 表示不是選單按鈕。
    """
    if text not in MENU_BUTTONS:
        return False

    user_id = update.effective_user.id if update.effective_user else 0

    if text == BTN_GAME:
        # 遊戲按鈕：帶 tgid 參數的 InlineKeyboard
        game_link = f"{GAME_URL}?tgid={user_id}"
        inline_kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🎮 立即進入遊戲", url=game_link)]]
        )
        if update.message:
            await update.message.reply_text(
                "🎮 點擊下方按鈕進入遊戲平台！",
                reply_markup=inline_kb,
            )

    elif text == BTN_ACCOUNT:
        # 帳戶按鈕：顯示 Telegram ID
        if update.message:
            await update.message.reply_text(
                f"💰 您的 Telegram ID：`{user_id}`",
                parse_mode="Markdown",
            )

    elif text == BTN_CHANNEL:
        # 官方頻道
        if update.message:
            await update.message.reply_text(f"📢 官方頻道：{CHANNEL_URL}")

    elif text == BTN_CS:
        # 客服列表
        if update.message:
            await update.message.reply_text(f"👥 客服聯繫：{CS_URL}")

    return True


# ===== 新成員歡迎訊息 =====

async def handle_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    當有新成員加入群組時，發送歡迎訊息。
    使用 filters.StatusUpdate.NEW_CHAT_MEMBERS 觸發。
    """
    if not update.message or not update.message.new_chat_members:
        return

    bot_id = context.bot.id
    new_members = update.message.new_chat_members

    for member in new_members:
        # 跳過 Bot 本身加入的情況
        if member.id == bot_id:
            logger.info("Bot 自己加入群組，跳過歡迎訊息")
            continue

        # 取得顯示名稱，優先用 first_name，再用 username
        display_name = member.first_name or member.username or "新朋友"
        # 若有 username，加上 @mention（Markdown 格式）
        if member.username:
            mention = f"@{member.username}"
        else:
            # 用 Markdown mention（無 username 時用 tg://user?id=）
            mention = f"[{display_name}](tg://user?id={member.id})"

        welcome_msg = (
            f"👋 歡迎 {mention} 加入！\n\n"
            "🏆 世界體育數據室 提供：\n"
            "• MLB / NBA / NHL / 足球 即時比分\n"
            "• AI 勝率預測與比賽分析\n"
            "• 直接問 Bot 任何體育問題，不需要指令！\n\n"
            f"💼 合作夥伴：{CS_URL}"
        )

        try:
            await update.message.reply_text(
                welcome_msg,
                parse_mode="Markdown",
            )
            logger.info(f"已發送歡迎訊息給 {display_name} (id={member.id})")
        except Exception as e:
            logger.error(f"發送歡迎訊息失敗: {e}")


# ===== 核心：上下文感知訊息處理 =====

async def dispatch_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """
    統一的訊息分發函數（私訊和群組共用）

    流程：
    1. 呼叫 should_use_bot_function（傳入對話歷史）判斷意圖
    2. 根據意圖路由到對應功能
    3. 查詢完成後，將用戶訊息和 Bot 回應記錄到對話歷史
    """
    user_id = update.effective_user.id if update.effective_user else 0

    try:
        from modules.ai_chat import should_use_bot_function, get_ai_response, add_to_history

        intent = should_use_bot_function(user_id, text)
        action = intent.get("action", "chat")
        query = intent.get("query", "").strip()

        logger.info(f"[dispatch] user={user_id} text='{text}' → action={action} query='{query}'")

        if action == "details" and query:
            # 查詢即時詳細資料（先發投手/進球/換人）
            await handle_details_query(update, query)
            add_to_history(user_id, "user", text)
            add_to_history(user_id, "assistant", f"查詢了 {query} 的即時詳細資料")

        elif action == "upcoming" and query:
            # 查詢未來賽程（修復「下場對誰」問題的核心）
            await reply(update, f"⏳ 查詢 {query} 的下一場賽程...")
            result = get_upcoming_matches(query)
            response = format_upcoming_response(result)
            await reply_split(update, response)
            # 記錄到對話歷史，讓後續追問能繼續理解上下文
            add_to_history(user_id, "user", text)
            add_to_history(user_id, "assistant", response[:200])  # 只記摘要

        elif action == "score" and query:
            await handle_score_query(update, query, user_id=user_id)

        elif action == "live":
            await cmd_live(update, context)

        elif action == "hot":
            await cmd_hot(update, context)

        elif action == "leaders":
            context.args = query.split() if query else []
            await cmd_leaders(update, context)

        elif action == "today":
            await cmd_today(update, context)

        elif action == "analyze" and query:
            context.args = query.split()
            await cmd_analyze(update, context)

        elif is_query(text):
            # fallback：規則式判斷為查詢
            await handle_score_query(update, text, user_id=user_id)

        else:
            # 純聊天：交由 AI 回應（get_ai_response 內部自動記錄歷史）
            ai_reply = get_ai_response(user_id, text)
            await reply(update, ai_reply)

    except Exception as e:
        logger.error(f"dispatch error: {e}", exc_info=True)
        # fallback：嘗試直接查詢或 AI 聊天
        if is_query(text):
            await handle_score_query(update, text)
        else:
            try:
                from modules.ai_chat import get_ai_response
                ai_reply = get_ai_response(user_id, text)
                await reply(update, ai_reply)
            except Exception as e2:
                logger.error(f"fallback error: {e2}")
                await reply(update, "😅 抱歉，系統暫時無法回應，請稍後再試！")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理私訊（含選單按鈕）"""
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    logger.info(f"[私訊] {text}")
    # 優先處理選單按鈕，避免被 AI 接管
    if await handle_menu_button(update, context, text):
        return
    await dispatch_message(update, context, text)


async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理群組訊息（含選單按鈕）"""
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    logger.info(f"[群組] {text}")
    # 優先處理選單按鈕
    if await handle_menu_button(update, context, text):
        return
    await dispatch_message(update, context, text)


async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理頻道訊息（頻道只處理查詢，不做 AI 聊天）"""
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


async def handle_score_query(update: Update, query: str, user_id: int = 0):
    """處理比分查詢，查詢完成後記錄到對話歷史"""
    logger.info(f"開始查詢: {query}")
    try:
        result = search_live_scores(query)
        events = result["events"]
        logger.info(f"查詢結果: {len(events)} 場")
        response = format_response(result)
        await reply_split(update, response)

        # 記錄到對話歷史，讓後續「下場對誰」能知道剛才查了什麼隊
        if user_id:
            try:
                from modules.ai_chat import add_to_history
                parsed = result.get("parsed", {})
                team_names = " / ".join(t["cn_name"] for t in parsed.get("teams", [])) if parsed.get("teams") else query
                add_to_history(user_id, "user", query)
                add_to_history(user_id, "assistant", f"查詢結果：{team_names} 共 {len(events)} 場比賽")
            except Exception:
                pass

    except Exception as e:
        logger.error(f"Query error: {e}", exc_info=True)
        await reply(update, "❌ 查詢失敗，請稍後再試")


async def handle_details_query(update: Update, query: str):
    """
    處理即時詳細資料查詢（投手/打者/進球/換人）
    自動找到進行中的比賽並呼叫 summary API
    """
    logger.info(f"即時詳細資料查詢: {query}")
    await reply(update, f"⏳ 查詢 {query} 的即時詳細資料...")

    try:
        result = search_live_scores(query)
        events = result["events"]

        # 尋找進行中的比賽
        live_events = [e for e in events if e.get("state") == "in"]

        if not live_events:
            # 沒有進行中的比賽，嘗試顯示最近一場（已結束）
            post_events = [e for e in events if e.get("state") == "post"]
            if post_events:
                e = post_events[0]
                game_id = e.get("game_id", "")
                sport = e.get("sport", "")
                league = e.get("league", "")
                if game_id and sport and league:
                    details = get_live_game_details(game_id, sport, league)
                    msg = format_game_details(details)
                    await reply_split(update, msg)
                else:
                    await reply(update, f"😴 {query} 目前沒有進行中的比賽")
            else:
                await reply(update, f"😴 {query} 目前沒有進行中的比賽\n\n請先查詢比分確認比賽進行中")
            return

        # 有進行中的比賽，取第一場
        e = live_events[0]
        game_id = e.get("game_id", "")
        sport = e.get("sport", "")
        league = e.get("league", "")

        if not game_id or not sport or not league:
            await reply(update, "❌ 無法取得比賽 ID，請稍後再試")
            return

        details = get_live_game_details(game_id, sport, league)
        msg = format_game_details(details)
        await reply_split(update, msg)

    except Exception as e:
        logger.error(f"Details query error: {e}", exc_info=True)
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
        BotCommand("details", "即時詳細資料（投手/進球/換人）"),
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
    logger.info("🤖 啟動智能查詢 Bot V11（娛樂城選單 + 歡迎訊息版）...")

    app = Application.builder().token(BOT_TOKEN).build()

    # 新成員歡迎訊息（群組）
    app.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS,
        handle_new_member
    ))

    # 指令
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("score", cmd_score))
    app.add_handler(CommandHandler("details", cmd_details))
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

    # 群組 / supergroup
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

    logger.info("✅ Bot V11 已啟動，等待查詢...")
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=["message", "channel_post", "my_chat_member"],
    )


if __name__ == "__main__":
    main()
