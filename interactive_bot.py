"""
互動式 Telegram Bot V14 - 頻道留言優化與個資偵測
新增：
1. 更新私訊歡迎訊息（多站台入口）
2. 頻道留言區幽默引導（引導至 @LA1111_bot）
3. 頻道留言區個資偵測與自動刪除
"""
import sys
import os
import logging
import re
from datetime import datetime
import pytz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram import Update, BotCommand, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
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
CS_URL = "https://t.me/yu_888yu"
BOT_USERNAME = "LA1111_bot"  # 邀請連結用的 Bot username
TARGET_GROUP = "@G5ofa"

# ===== 語言設定 =====
LANGUAGES = {
    "zh_tw": ("🇹🇼 繁體中文", "✅ 語言已設定為繁體中文"),
    "en":    ("🇺🇸 English",    "✅ Language set to English"),
    "km":    ("🇰🇭 ភាសាខ្មែរ",    "✅ ភាសាត្រូវបានកំណត់ជាភាសាខ្មែរ"),
    "zh_cn": ("🇨🇳 简体中文", "✅ 语言已设置为简体中文"),
    "vi":    ("🇻🇳 Tiếng Việt", "✅ Ngôn ngữ đã được đặt thành Tiếng Việt"),
    "th":    ("🇹🇭 ภาษาไทย",    "✅ ตั้งค่าภาษาเป็นภาษาไทยแล้ว"),
}

# ===== 主選單鍵盤（升級版） =====
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🎮 遊戲"],
        ["👉 邀請好友", "🌐 語言設置"],
        ["📢 官方頻道", "👥 客服列表"],
    ],
    resize_keyboard=True
)

# ===== 個資偵測 Regex =====
PII_PATTERNS = [
    r"09\d{8}",                # 台灣手機
    r"\+852\s?\d{4}\s?\d{4}",  # 香港手機
    r"\d{8,20}",               # 銀行帳號（連續數字）
    r"[A-Z][12]\d{8}",         # 台灣身分證
    r"(?i)(密碼|password|pwd)[:：\s]*\w+", # 密碼相關
    r"(?i)(帳號|account)[:：\s]*\w+",      # 帳號相關
]

# ===== 輔助函數 =====
async def reply(update: Update, text: str, reply_markup=None):
    """統一回覆函數（支援私訊、群組、頻道）"""
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    elif update.channel_post:
        await update.channel_post.reply_text(text, reply_markup=reply_markup)

async def reply_split(update: Update, text: str):
    """處理長訊息分段發送"""
    if len(text) <= 4000:
        await reply(update, text)
        return
    parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for p in parts:
        await reply(update, p)

def is_query(text: str) -> bool:
    """判斷是否為比分查詢（隊名或運動類型）"""
    text_lower = text.lower()
    if any(kw in text_lower for kw in SPORT_KEYWORDS):
        return True
    if any(alias in text_lower for alias in ALIAS_INDEX):
        return True
    return False

async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    """處理選單按鈕點擊"""
    user_id = update.effective_user.id if update.effective_user else 0
    if text == "🎮 遊戲":
        game_link = f"{GAME_URL}?tgid={user_id}"
        inline_kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🎮 立即進入遊戲", url=game_link)]]
        )
        await reply(update, "🎮 點擊下方按鈕進入遊戲平台！", reply_markup=inline_kb)
        return True
    elif text == "👉 邀請好友":
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
        msg = (
            "🎉 你的專屬邀請連結：\n"
            f"{ref_link}\n\n"
            "分享給朋友，一起享受體育分析！⚽🏀⚾"
        )
        await reply(update, msg)
        return True
    elif text == "🌐 語言設置":
        buttons = []
        keys = list(LANGUAGES.keys())
        for i in range(0, len(keys), 2):
            row = [
                InlineKeyboardButton(LANGUAGES[keys[i]][0], callback_data=f"lang_{keys[i]}"),
                InlineKeyboardButton(LANGUAGES[keys[i+1]][0], callback_data=f"lang_{keys[i+1]}")
            ]
            buttons.append(row)
        await reply(update, "🌐 請選擇您的語言：", reply_markup=InlineKeyboardMarkup(buttons))
        return True
    elif text == "📢 官方頻道":
        await reply(update, f"📢 官方頻道：{CHANNEL_URL}\n\n訂閱頻道獲取最新體育資訊！")
        return True
    elif text == "👥 客服列表":
        await reply(update, f"👥 客服列表\n\n👸 VIP 客服專員：{CS_URL}\n\n有任何問題都可以直接聯繫！")
        return True
    return False

async def handle_lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理語言選擇按鈕點擊"""
    query = update.callback_query
    await query.answer()
    lang_code = query.data.replace("lang_", "")
    if lang_code in LANGUAGES:
        context.user_data["language"] = lang_code
        await query.edit_message_text(LANGUAGES[lang_code][1])

# ===== 指令 =====
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("收到 /start")
    welcome_text = (
        "🏆 歡迎來到 LA1 智能服務平台！\n\n"
        "✅ MLB / NBA / NHL / 足球 即時比分\n"
        "✅ AI 勝率預測與比賽分析\n"
        "✅ 直接問任何體育問題，不需要指令！\n\n"
        "🌐 平台入口：\n"
        "🇹🇼 台站｜La1111.meta1788.com\n"
        "🇭🇰🇲🇾🇲🇴🇻🇳 U站｜la1111.ofa168hk.com\n"
        "🇰🇭 代理｜agent.ofa168kh.com\n\n"
        "🤝 商務合作：https://t.me/OFA168Abe1\n\n"
        "🎮 點擊下方【遊戲】按鈕立即進入！"
    )
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=MAIN_KEYBOARD)
    elif update.channel_post:
        await update.channel_post.reply_text(welcome_text)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("收到 /help")
    await reply(update, """📖 使用說明 V14
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
""")

async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("收到 /today")
    await reply(update, "⏳ 正在獲取今日賽事總覽...")
    result = search_live_scores("today")
    response = format_response(result)
    await reply_split(update, response)

async def cmd_live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("收到 /live")
    await reply(update, "⏳ 正在獲取目前進行中的比賽...")
    result = search_live_scores("live")
    response = format_response(result)
    await reply_split(update, response)

async def cmd_hot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("收到 /hot")
    await reply(update, "⏳ 正在獲取今日熱門焦點賽事...")
    result = search_live_scores("hot")
    response = format_response(result)
    await reply_split(update, response)

async def cmd_leaders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("收到 /leaders")
    query = " ".join(context.args) if context.args else "MLB"
    await reply(update, f"⏳ 正在獲取 {query} 數據榜單...")
    result = search_live_scores(f"leaders {query}")
    response = format_response(result)
    await reply_split(update, response)

async def cmd_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("收到 /analyze")
    if not context.args:
        await reply(update, "請輸入隊名，例如：/analyze 湖人")
        return
    query = " ".join(context.args)
    await reply(update, f"⏳ 正在為您進行 AI 賽事分析：{query}...")
    try:
        from modules.ai_chat import get_ai_response
        ai_reply = get_ai_response(update.effective_user.id, f"分析 {query}")
        await reply(update, ai_reply)
    except Exception as e:
        logger.error(f"Analyze error: {e}")
        await reply(update, "😅 抱歉，AI 分析暫時無法使用，請稍後再試！")

async def cmd_odds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("收到 /odds")
    if not context.args:
        await reply(update, "請輸入隊名，例如：/odds 湖人")
        return
    query = " ".join(context.args)
    await reply(update, f"⏳ 正在獲取 {query} 的盤口資訊...")
    result = search_live_scores(f"odds {query}")
    response = format_response(result)
    await reply_split(update, response)

# ===== 訊息處理邏輯 =====
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
            await handle_details_query(update, query)
            add_to_history(user_id, "user", text)
            add_to_history(user_id, "assistant", f"查詢了 {query} 的即時詳細資料")
        elif action == "upcoming" and query:
            await reply(update, f"⏳ 查詢 {query} 的下一場賽程...")
            result = get_upcoming_matches(query)
            response = format_upcoming_response(result)
            await reply_split(update, response)
            add_to_history(user_id, "user", text)
            add_to_history(user_id, "assistant", response[:200])
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
            await handle_score_query(update, text, user_id=user_id)
        else:
            ai_reply = get_ai_response(user_id, text)
            await reply(update, ai_reply)
    except Exception as e:
        logger.error(f"dispatch error: {e}", exc_info=True)
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

async def send_first_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """首次私訊自動歡迎"""
    user_id = update.effective_user.id if update.effective_user else 0
    welcome_text = (
        "🏆 歡迎來到 LA1 智能服務平台！\n\n"
        "✅ MLB / NBA / NHL / 足球 即時比分\n"
        "✅ AI 勝率預測與比賽分析\n"
        "✅ 直接問任何體育問題，不需要指令！\n\n"
        "🌐 平台入口：\n"
        "🇹🇼 台站｜La1111.meta1788.com\n"
        "🇭🇰🇲🇾🇲🇴🇻🇳 U站｜la1111.ofa168hk.com\n"
        "🇰🇭 代理｜agent.ofa168kh.com\n\n"
        "🤝 商務合作：https://t.me/OFA168Abe1\n\n"
        "🎮 點擊下方【遊戲】按鈕立即進入！"
    )
    await update.message.reply_text(welcome_text, reply_markup=MAIN_KEYBOARD)
    
    lang_buttons = [
        [InlineKeyboardButton(LANGUAGES["zh_tw"][0], callback_data="lang_zh_tw"),
         InlineKeyboardButton(LANGUAGES["en"][0],    callback_data="lang_en")],
        [InlineKeyboardButton(LANGUAGES["km"][0],    callback_data="lang_km"),
         InlineKeyboardButton(LANGUAGES["zh_cn"][0], callback_data="lang_zh_cn")],
        [InlineKeyboardButton(LANGUAGES["vi"][0],    callback_data="lang_vi"),
         InlineKeyboardButton(LANGUAGES["th"][0],    callback_data="lang_th")],
    ]
    await update.message.reply_text("🌐 請選擇您的語言：", reply_markup=InlineKeyboardMarkup(lang_buttons))
    
    game_link = f"{GAME_URL}?tgid={user_id}"
    inline_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🎮 立即進入遊戲", url=game_link)]])
    await update.message.reply_text("🎮 點擊下方按鈕進入遊戲平台！", reply_markup=inline_kb)
    
    context.user_data["welcomed"] = True
    logger.info(f"[首次歡迎] 已發送給 user_id={user_id}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理私訊"""
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    logger.info(f"[私訊] {text}")
    if not context.user_data.get("welcomed"):
        await send_first_welcome(update, context)
    if await handle_menu_button(update, context, text):
        return
    await dispatch_message(update, context, text)

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理群組訊息"""
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    logger.info(f"[群組] {text}")
    if await handle_menu_button(update, context, text):
        return
    await dispatch_message(update, context, text)

async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理頻道留言區訊息（含幽默引導與個資偵測）"""
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    logger.info(f"[頻道留言] {text}")

    # ── 1. 個資偵測與自動刪除 ──
    is_pii = False
    for pattern in PII_PATTERNS:
        if re.search(pattern, text):
            is_pii = True
            break
    
    if is_pii:
        try:
            await update.message.delete()
            await reply(update, "嘿！個資不能亂貼喔 🙈 為了保護你的安全，剛才那則訊息已被移除。有問題請私訊 @LA1111_bot 處理！")
            return
        except Exception as e:
            logger.error(f"刪除個資訊息失敗: {e}")
            await reply(update, "嘿！個資不能亂貼喔 🙈 為了保護你的安全，請盡快移除剛才的訊息。有問題請私訊 @LA1111_bot 處理！")
            return

    # ── 2. 幽默引導與客服問題處理 ──
    text_lower = text.lower()
    cs_keywords = ["帳號", "儲值", "提現", "充值", "託售", "點數", "沒上分", "密碼", "註冊", "登入"]
    if any(kw in text_lower for kw in cs_keywords):
        humor_replies = [
            "哇！這個問題問得好！不過我只是個愛看球的 AI，這種大事還是交給真人處理比較穩 😂 快去找 @LA1111_bot，他比我厲害多了！",
            "這種問題找我沒用啦 😂 快去找 @LA1111_bot，他專門處理這種疑難雜症！",
            "哎呀，我的電路板處理不了金流問題 🤖 這種專業的事請私訊 @LA1111_bot 處理喔！",
        ]
        import random
        await reply(update, random.choice(humor_replies))
        return

    # ── 3. 正常體育查詢 ──
    if is_query(text):
        await handle_score_query(update, text)
    else:
        # 一般留言：幽默互動
        humor_chat = [
            "這球你怎麼看？我覺得很有戲喔！😎",
            "哈哈，說得好！大家一起幫主隊加油！🔥",
            "看球就是要熱鬧！有什麼想問的隨時問我喔 🏀⚾",
            "我也在盯著這場，心跳好快啊！💓",
        ]
        import random
        await reply(update, random.choice(humor_chat))

async def handle_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """新成員歡迎訊息"""
    if not update.message or not update.message.new_chat_members:
        return
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        name = member.username if member.username else member.first_name
        mention = f"@{name}" if member.username else f"[{name}](tg://user?id={member.id})"
        welcome_text = (
            f"👋 歡迎 {mention} 加入！\n\n"
            "🏆 世界體育數據室 提供：\n"
            "• MLB / NBA / NHL / 足球 即時比分\n"
            "• AI 勝率預測與比賽分析\n"
            "• 直接問 Bot 任何體育問題，不需要指令！\n\n"
            "💼 合作夥伴：https://t.me/yu_888yu"
        )
        await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def handle_score_query(update: Update, query: str, user_id: int = 0):
    """處理比分查詢"""
    logger.info(f"開始查詢: {query}")
    try:
        result = search_live_scores(query)
        response = format_response(result)
        await reply_split(update, response)
        if user_id:
            try:
                from modules.ai_chat import add_to_history
                add_to_history(user_id, "user", query)
                add_to_history(user_id, "assistant", f"查詢結果：{query}")
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Query error: {e}")
        await reply(update, "❌ 查詢失敗，請稍後再試")

async def handle_details_query(update: Update, query: str):
    """處理即時詳細資料查詢"""
    logger.info(f"即時詳細資料查詢: {query}")
    try:
        result = search_live_scores(query)
        live_events = [e for e in result["events"] if e.get("state") == "in"]
        if not live_events:
            await reply(update, f"😴 {query} 目前沒有進行中的比賽")
            return
        e = live_events[0]
        details = get_live_game_details(e.get("game_id"), e.get("sport"), e.get("league"))
        msg = format_game_details(details)
        await reply_split(update, msg)
    except Exception as e:
        logger.error(f"Details error: {e}")
        await reply(update, "❌ 查詢詳細資料失敗")

# ===== 主程式 =====
def main():
    if not BOT_TOKEN:
        logger.error("未設定 BOT_TOKEN 環境變數")
        return
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("live", cmd_live))
    app.add_handler(CommandHandler("hot", cmd_hot))
    app.add_handler(CommandHandler("leaders", cmd_leaders))
    app.add_handler(CommandHandler("analyze", cmd_analyze))
    app.add_handler(CommandHandler("odds", cmd_odds))
    app.add_handler(CallbackQueryHandler(handle_lang_callback, pattern=r"^lang_"))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_members))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT, handle_message))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.TEXT, handle_channel_post))
    logger.info("Bot 已啟動...")
    app.run_polling(allowed_updates=["message", "callback_query", "chat_member"])

if __name__ == "__main__":
    main()
