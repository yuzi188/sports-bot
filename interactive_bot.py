"""互動式 Telegram Bot V21.0 - LA1 SPORTS AI PLATFORM 全面升級版）

V19.1 修復：
  - 群組訊息（ChatType.GROUPS）改綁定到 handle_group_message
    原本錯誤綁定到 handle_channel_post，導致群組走舊路徑，沒有 GPT 整理
  - handle_channel_post 的體育查詢補上 user_id + user_lang，確保 GPT 整理

V19 新增：
  1. 全面 GPT 自然語言回覆架構
     - 客服問題（充值/提現/帳號/USDT 等）→ FAQ 話術直接回答，零延遲
     - 體育賽事問題 → GPT 理解意圖 → ESPN API 查資料 → GPT 自然語言整理回覆
     - 所有體育查詢結果都通過 generate_sports_reply() 整理成自然語言

  2. 修復意圖識別誤判
     - WBC 查詢不再被誤判為 NHL 楓葉隊
     - 「比賽」「今日」等通用詞不再被模糊匹配為隊名
     - 加入前置規則：WBC/MLB/NBA/NHL/NFL 直接識別，不走 GPT

V18 保留：
  3. 用戶喜好記憶學習（SQLite）
  4. 投票預測遊戲（Telegram Poll + 積分系統）
  5. 群體行為學習分析系統
  6. /football /baseball /basketball /allanalyze — 三種運動 AI 分析
  7. /winrate — 勝率統計面板
"""
import sys
import os
import logging
import re
from datetime import datetime
import pytz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram import Update, BotCommand, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, Poll
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    PollAnswerHandler,
    filters,
    ContextTypes,
)

from config import BOT_TOKEN, TIMEZONE
from live_query import (
    search_live_scores, format_response,
    get_upcoming_matches, format_upcoming_response,
)
from modules.game_details import get_live_game_details, format_game_details
from smart_search import SPORT_KEYWORDS, ALIAS_INDEX
# ── 539 彩票模組（V20）──
from modules.lottery import (
    lottery_init_db,
    lottery_info_cmd,
    bet_ui_cmd,
    lottery_balance_cmd,
    lottery_daily_cmd,
    lottery_history_cmd,
    lottery_result_cmd,
    lottery_rank_cmd,
    lottery_rules_cmd,
    lottery_exit_cmd,
    lottery_callback_handler,
    claim_chat_bonus,
    lottery_settings,
)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
tz = pytz.timezone(TIMEZONE)

# ===== 娛樂城設定 =====
GAME_URL      = "http://la1111.ofa168kh.com/"
CHANNEL_URL   = "https://t.me/LA11118"
CS_URL        = "https://t.me/yu_888yu"
BOT_USERNAME  = "LA1111_bot"
TARGET_GROUP  = "@G5ofa"

# ===== 語言設定 =====
LANGUAGES = {
    "zh_tw": ("🇹🇼 繁體中文", "✅ 語言已設定為繁體中文"),
    "en":    ("🇺🇸 English",    "✅ Language set to English"),
    "km":    ("🇰🇭 ភាសាខ្មែរ",    "✅ ភាសាត្រូវបានកំណត់ជាភាសាខ្មែរ"),
    "zh_cn": ("🇨🇳 简体中文", "✅ 语言已设置为简体中文"),
    "vi":    ("🇻🇳 Tiếng Việt", "✅ Ngôn ngữ đã được đặt thành Tiếng Việt"),
    "th":    ("🇹🇭 ภาษาไทย",    "✅ ตั้งค่าภาษาเป็นภาษาไทยแล้ว"),
}

# ===== 主選單鍵盤 =====
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🎮 遊戲"],
        ["👉 邀請好友", "🌐 語言設置"],
        ["📢 官方頻道", "👥 客服列表"],
    ],
    resize_keyboard=True
)

# ===== 個資偵測 Regex（V17 修復版）=====
# - 原 r"\d{8,20}" 會誤判球衣號碼等短數字
# - 改為 12-20 位獨立數字（銀行帳號），台灣手機保持精確 pattern
PII_PATTERNS = [
    r"09\d{8}",                                       # 台灣手機（精確 10 位）
    r"\+852\s?\d{4}\s?\d{4}",                         # 香港手機
    r"(?<!\d)\d{12,20}(?!\d)",                        # 銀行帳號（12-20 位獨立數字）
    r"[A-Z][12]\d{8}",                                # 台灣身分證
    r"(?i)(密碼|password|pwd)\s*[:：]\s*\S+",          # 密碼（需要冒號才觸發）
]


# ══════════════════════════════════════════════
#  輔助函數
# ══════════════════════════════════════════════

async def reply(update: Update, text: str, reply_markup=None):
    """統一回覆函數（支援私訊、群組、頻道）"""
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    elif update.channel_post:
        await update.channel_post.reply_text(text, reply_markup=reply_markup)


async def reply_split(update: Update, text: str):
    """處理長訊息分段發送（每段最多 4000 字元）"""
    if len(text) <= 4000:
        await reply(update, text)
        return
    parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for p in parts:
        await reply(update, p)


def _append_cs_contact(text: str) -> str:
    """
    若 GPT 回覆中提到「客服/人工/轉接」等字眼，
    且回覆中尚未包含 @yu_888yu，則自動附上客服聯絡方式。
    """
    cs_trigger_words = ["客服", "人工", "轉接", "聯繫", "聯絡", "contact", "support"]
    cs_contact = "\n\n👑 客服聯絡：@yu_888yu"
    if "@yu_888yu" not in text and any(w in text for w in cs_trigger_words):
        return text + cs_contact
    return text


def is_query(text: str) -> bool:
    """判斷是否為比分查詢（隊名或運動類型）"""
    text_lower = text.lower()
    if any(kw in text_lower for kw in SPORT_KEYWORDS):
        return True
    if any(alias in text_lower for alias in ALIAS_INDEX):
        return True
    return False


def _get_user_lang(context: ContextTypes.DEFAULT_TYPE, user_id: int = 0) -> str:
    """
    安全取得用戶語言設定。
    V18：優先從 SQLite 讀取（跨 session 持久化），再 fallback 到 context.user_data。
    """
    # 優先從 SQLite 讀取
    if user_id:
        try:
            from modules.user_preferences import get_user_language
            lang = get_user_language(user_id)
            if lang in LANGUAGES:
                return lang
        except Exception:
            pass
    # Fallback 到 context.user_data
    if context and context.user_data:
        lang = context.user_data.get("language", "zh_tw")
        if lang in LANGUAGES:
            return lang
    return "zh_tw"


def _get_username(update: Update) -> str:
    """取得用戶顯示名稱"""
    user = update.effective_user
    if not user:
        return "匿名用戶"
    if user.username:
        return f"@{user.username}"
    return user.first_name or f"用戶{user.id}"


def _record_user_query(user_id: int, query_value: str, query_type: str = "team", sport: str = ""):
    """統一的查詢記錄函數（同時記錄個人喜好 + 群體統計）"""
    try:
        from modules.user_preferences import record_query, infer_sport_from_query
        from modules.community_analytics import record_community_query
        if not sport:
            sport = infer_sport_from_query(query_value)
        record_query(user_id, query_type, query_value, sport)
        record_community_query(user_id, query_value, query_type, sport)
    except Exception as e:
        logger.debug(f"記錄查詢失敗（非致命）: {e}")


# ══════════════════════════════════════════════
#  選單按鈕處理
# ══════════════════════════════════════════════

async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    """處理選單按鈕點擊"""
    user_id = update.effective_user.id if update.effective_user else 0
    if text == "🎮 遊戲":
        game_link = f"{GAME_URL}?tgid={user_id}"
        inline_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🎮 立即進入遊戲", url=game_link)]])
        await reply(update, "🎮 點擊下方按鈕進入遊戲平台！", reply_markup=inline_kb)
        return True
    elif text == "👉 邀請好友":
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
        msg = f"🎉 你的專屬邀請連結：\n{ref_link}\n\n分享給朋友，一起享受體育分析！⚽🏀⚾"
        await reply(update, msg)
        return True
    elif text == "🌐 語言設置":
        buttons = []
        keys = list(LANGUAGES.keys())
        for i in range(0, len(keys), 2):
            row = [
                InlineKeyboardButton(LANGUAGES[keys[i]][0],   callback_data=f"lang_{keys[i]}"),
                InlineKeyboardButton(LANGUAGES[keys[i+1]][0], callback_data=f"lang_{keys[i+1]}"),
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
    """處理語言選擇按鈕點擊（V18：同步儲存到 SQLite）"""
    query = update.callback_query
    await query.answer()
    lang_code = query.data.replace("lang_", "")
    if lang_code in LANGUAGES:
        # 同步到 context.user_data
        context.user_data["language"] = lang_code
        # V18：同步儲存到 SQLite（跨 session 持久化）
        user_id = query.from_user.id
        try:
            from modules.user_preferences import set_user_language
            set_user_language(user_id, lang_code)
        except Exception as e:
            logger.warning(f"SQLite 語言儲存失敗: {e}")
        await query.edit_message_text(LANGUAGES[lang_code][1])
        logger.info(f"用戶 {user_id} 語言設定為 {lang_code}")


async def handle_style_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理互動習慣選擇按鈕點擊"""
    query = update.callback_query
    await query.answer()
    style_code = query.data.replace("style_", "")
    user_id = query.from_user.id
    style_labels = {
        "detailed": "📊 詳細分析派",
        "brief":    "⚡ 快速比分派",
        "auto":     "🤖 自動判斷",
    }
    if style_code in style_labels:
        try:
            from modules.user_preferences import set_user_style
            set_user_style(user_id, style_code)
            await query.edit_message_text(f"✅ 互動習慣已設定為：{style_labels[style_code]}")
        except Exception as e:
            logger.error(f"設定互動習慣失敗: {e}")
            await query.edit_message_text("老闆您好，語言設定暫時無法更新，如需協助請聯繫客服 @yu_888yu")


async def cmd_lottery_exit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """退出 539 彩票模式，切換回體育 Bot 選單"""
    await update.message.reply_text(
        "👋 已退出 539 彩票模式，切換回體育 Bot 選單。",
        reply_markup=MAIN_KEYBOARD
    )


# ══════════════════════════════════════════════
#  基本指令
# ══════════════════════════════════════════════

# ===== 歡迎影片設定 =====
# 影片公開 URL（直接傳給 Telegram send_video）
# 第一次發送後，將回傳的 file_id 快取起來，後續發送不重複下載
WELCOME_VIDEO_URL     = "https://files.manuscdn.com/user_upload_by_module/session_file/310419663032670396/zOYpATipTMNEkuCQ.mp4"
WELCOME_VIDEO_FILE_ID = None   # 第一次發送後自動快取


def _build_welcome_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """
    建立歡迎頁完整 inline keyboard。
    使用現有程式碼裡已有的所有連結。
    """
    game_link = f"{GAME_URL}?tgid={user_id}"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇹🇼 台站",   url="http://La1111.meta1788.com/"),
            InlineKeyboardButton("🇭🇰 U站",    url="http://la1111.ofa168kh.com/"),
        ],
        [
            InlineKeyboardButton("🇰🇭 代理入口", url="http://la1111.ofa168kh.com/"),
        ],
        [
            InlineKeyboardButton("🆕 免費開戶註冊", url=game_link),
        ],
        [
            InlineKeyboardButton("🎁 優惠領取聯絡客服", url=CS_URL),
        ],
        [
            InlineKeyboardButton("🤝 商務合作",   url="https://t.me/OFA168Abe1"),
        ],
        [
            InlineKeyboardButton("🎮 立即進入遊戲", url=game_link),
        ],
    ])


async def _get_welcome_video_source() -> str:
    """
    取得歡迎影片來源（file_id 或 URL）。

    策略：
    1. 如果已快取 file_id → 直接回傳 file_id（最快）
    2. 否則回傳公開 URL（Telegram 支援直接用 URL 發送影片）
    """
    if WELCOME_VIDEO_FILE_ID:
        return WELCOME_VIDEO_FILE_ID
    return WELCOME_VIDEO_URL


async def send_daily_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """
    發送每日歡迎影片 + inline keyboard。
    由 handle_message / handle_group_message 在用戶每天第一次傳訊息時呼叫。
    發送後自動標記今天已發送，同一天內不重複。
    """
    global WELCOME_VIDEO_FILE_ID
    welcome_kb = _build_welcome_keyboard(user_id)
    video_source = await _get_welcome_video_source()

    try:
        msg = await update.message.reply_video(
            video=video_source,
            reply_markup=welcome_kb,
        )
        logger.info(f"[每日歡迎] 已發送影片給 user_id={user_id}")

        # 快取 file_id，後續發送不重複下載
        if not WELCOME_VIDEO_FILE_ID and msg.video:
            WELCOME_VIDEO_FILE_ID = msg.video.file_id
            logger.info(f"[每日歡迎] 已快取 file_id={WELCOME_VIDEO_FILE_ID}")

    except Exception as e:
        logger.warning(f"[每日歡迎] 影片發送失敗: {e}，改發按鈕")
        # Fallback：影片失敗改發按鈕
        try:
            await update.message.reply_text(
                "🏆 LA1 智能體育服務平台，歡迎你回來！",
                reply_markup=welcome_kb,
            )
        except Exception:
            pass

    # 標記今天已發送
    try:
        from modules.user_preferences import mark_daily_welcome_sent
        mark_daily_welcome_sent(user_id)
    except Exception as e:
        logger.warning(f"[每日歡迎] 標記失敗: {e}")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start 指令處理函數（V19.3 歡迎影片版）

    流程：
    1. 第一次進入（SQLite 判斷）：發送影片 + 完整 inline keyboard
    2. 之後再 /start：只發普通歡迎訊息
    """
    logger.info("收到 /start")

    if not update.message:
        if update.channel_post:
            welcome_text = (
                "🏆 歡迎來到 LA1 智能服務平台！\n\n"
                "🌐 平台入口：\n"
                "🇹🇼 台站｜La1111.meta1788.com/\n"
                "🇭🇰🇲🇾🇲🇴🇻🇳 U站｜la1111.ofa168kh.com/\n"
                "🇰🇭 代理｜la1111.ofa168kh.com/"
            )
            await update.channel_post.reply_text(welcome_text)
        return

    user_id = update.effective_user.id if update.effective_user else 0

    # ── 判斷是否為第一次進入 ──
    is_first_time = False
    if user_id:
        try:
            from modules.user_preferences import has_seen_welcome_video, mark_welcome_video_sent
            is_first_time = not has_seen_welcome_video(user_id)
        except Exception as e:
            logger.warning(f"檢查歡迎影片狀態失敗: {e}")
            is_first_time = True  # 出錯時保守，假設為第一次

    welcome_text = (
        "🤖 老闆您好 👋\n"
        "歡迎來到 LA1 智能客服\n"
        "請問需要什麼協助？\n\n"
        "例如可以詢問：\n"
        "• 有什麼遊戲\n"
        "• 如何註冊\n"
        "• 如何儲值\n"
        "• 今日賽事\n\n"
        "✅ MLB / NBA / NHL / 足球 即時比分\n"
        "✅ AI 勝率預測與比賽分析\n"
        "✅ 🎰 L幣 539 彩票遊戲\n\n"
        "🌐 平台入口：\n"
        "🇹🇼 台站｜La1111.meta1788.com/\n"
        "🇭🇰🇲🇾🇲🇴🇻🇳 U站｜la1111.ofa168kh.com/\n"
        "🇰🇭 代理｜la1111.ofa168kh.com/\n\n"
        "🤝 商務合作：https://t.me/OFA168Abe1\n\n"
        "🎰 輸入 /539 開始 L幣 539 彩票！\n\n"
        "🎮 點擊下方按鈕立即進入！"
    )

    if is_first_time and user_id:
        # ★ 第一次進入：發送影片 + 完整 inline keyboard
        global WELCOME_VIDEO_FILE_ID
        welcome_kb = _build_welcome_keyboard(user_id)

        # 取得影片來源（已快取的 file_id 或公開 URL）
        video_source = await _get_welcome_video_source()
        video_sent = False

        try:
            msg = await update.message.reply_video(
                video=video_source,
                caption=welcome_text,
                reply_markup=welcome_kb,
            )
            video_sent = True
            logger.info(f"[歡迎影片] 已發送影片給 user_id={user_id}")

            # 快取 file_id，後續發送不重複下載
            if not WELCOME_VIDEO_FILE_ID and msg.video:
                WELCOME_VIDEO_FILE_ID = msg.video.file_id
                logger.info(f"[歡迎影片] 已快取 file_id={WELCOME_VIDEO_FILE_ID}")

        except Exception as e:
            logger.warning(f"[歡迎影片] 發送影片失敗: {e}")

        if not video_sent:
            # 影片發送失敗，改發文字 + 按鈕
            await update.message.reply_text(welcome_text, reply_markup=welcome_kb)
            logger.info(f"[歡迎影片] 影片失敗，改發文字給 user_id={user_id}")

        # 標記已發送，避免重複
        try:
            from modules.user_preferences import mark_welcome_video_sent
            mark_welcome_video_sent(user_id)
        except Exception as e:
            logger.warning(f"標記歡迎影片已發送失敗: {e}")

        # 發送主選單鍵盤
        await update.message.reply_text("👇 點擊下方選單開始使用！", reply_markup=MAIN_KEYBOARD)

    else:
        # 非第一次：只發普通歡迎訊息
        await update.message.reply_text(welcome_text, reply_markup=MAIN_KEYBOARD)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("收到 /help")
    await reply(update, """📖 LA1 SPORTS AI PLATFORM V21.0

🔍 查詢方式：
• 直接輸入隊名：利物浦 曼城
• 輸入運動類型：棒球、NBA、足球
• 問「日本下場對誰」→ AI 自動查未來賽程

📊 即時體育數據：
• /score 隊名 → 即時比分 + 近況 + 勝率
• /today → 今日所有賽事總覽
• /live → 目前進行中的比賽
• /hot → 今日熱門焦點賽事
• /leaders → MLB全壘打/NBA得分/足球射手榜
• /odds 隊名 → 盤口資訊

🤖 AI 賽事分析：
• /football → ⚽ 今日足球 AI 分析
• /baseball → ⚾ 今日棒球 AI 分析
• /basketball → 🏀 今日籃球 AI 分析
• /allanalyze → 🔥 三種運動綜合 AI 分析
• /analyze 隊名 → AI 賽事分析預測
• /winrate 運動 → 勝率統計面板

🎯 預測遊戲 & 積分：
• /checkin → ✅ 每日簽到領積分（連續簽到加成）
• /predict → 🎯 今日焦點賽事預測投票
• /myprediction → 📝 我的預測記錄
• /rank → 🏆 積分排行榜 Top 10
• /myscore → 📊 我的積分與戰績
• 猜對 +10分 | 簽到 +10~30分

🎰 L幣 539 彩票：
• /539 → 查看 539 說明
• /539 03 08 12 25 37 → 下注 5 個號碼
• /quick → 快速隨機下注
• /balance → 查看 L幣餘額
• /daily → 每日簽到（+20 L幣）
• /history → 我的投注紀錄
• /result → 今日開獎結果
• /lrank → L幣排行榜
• /rules → 遊戲規則

👤 個人化：
• /myfav → 我的體育偏好總覽
• /style → 切換詳細分析/快速比分模式
• /insights → 即時社群趨勢洞察

📢 每日自動推播：
• 10:00 今日賽事預覽 + AI 分析
• 18:00 焦點賽事預測投票
• 22:00 賽後復盤總結
""")


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("收到 /today")
    user_id = update.effective_user.id if update.effective_user else 0
    _record_user_query(user_id, "today", "command")
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
    user_id = update.effective_user.id if update.effective_user else 0
    user_lang = _get_user_lang(context, user_id)
    _record_user_query(user_id, query, "team")
    _record_user_query(user_id, "analyze", "command")
    await reply(update, f"⏳ 正在為您進行 AI 賽事分析：{query}...")
    try:
        from modules.ai_chat import get_ai_response
        ai_reply = get_ai_response(user_id, f"深度分析 {query} 的近期表現、勝率預測與爆冷可能", user_lang=user_lang)
        await reply_split(update, ai_reply)
    except Exception as e:
        logger.error(f"Analyze error: {e}", exc_info=True)
        await reply(update, "老闆您好，AI 分析功能暫時無法使用。如需協助請聯繫客服 @yu_888yu")


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


# ══════════════════════════════════════════════
#  三種運動 AI 分析指令（V17）
# ══════════════════════════════════════════════

async def cmd_football_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """⚽ 今日足球 AI 分析"""
    logger.info("收到 /football")
    user_id = update.effective_user.id if update.effective_user else 0
    _record_user_query(user_id, "football", "sport", "football")
    _record_user_query(user_id, "football", "command")
    await reply(update, "⏳ 正在生成今日足球 AI 分析，請稍候...")
    try:
        from modules.football import get_matches
        from modules.sports_analyzer import analyze_football
        matches = get_matches()
        if not matches:
            await reply(update, "⚽ 今日暫無足球賽事資訊。")
            return
        sep = "═" * 24
        analysis = analyze_football("\n".join(matches))
        await reply_split(update, f"{sep}\n⚽ 今日足球 AI 分析\n{sep}\n\n{analysis}\n\n{sep}\n📡 世界體育數據室\n⚠️ 分析僅供參考，請理性投注")
    except Exception as e:
        logger.error(f"Football analyze error: {e}", exc_info=True)
        await reply(update, "老闆您好，足球分析功能暫時無法使用。如需協助請聯繫客服 @yu_888yu")


async def cmd_baseball_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """⚾ 今日棒球 AI 分析"""
    logger.info("收到 /baseball")
    user_id = update.effective_user.id if update.effective_user else 0
    _record_user_query(user_id, "baseball", "sport", "baseball")
    _record_user_query(user_id, "baseball", "command")
    await reply(update, "⏳ 正在生成今日棒球 AI 分析，請稍候...")
    try:
        from modules.mlb import get_games
        from modules.sports_analyzer import analyze_baseball
        games = get_games()
        if not games:
            await reply(update, "⚾ 今日暫無棒球賽事資訊。")
            return
        sep = "═" * 24
        analysis = analyze_baseball("\n".join(games))
        await reply_split(update, f"{sep}\n⚾ 今日棒球 AI 分析\n{sep}\n\n{analysis}\n\n{sep}\n📡 世界體育數據室\n⚠️ 分析僅供參考，請理性投注")
    except Exception as e:
        logger.error(f"Baseball analyze error: {e}", exc_info=True)
        await reply(update, "老闆您好，棒球分析功能暫時無法使用。如需協助請聯繫客服 @yu_888yu")


async def cmd_basketball_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🏀 今日籃球 AI 分析"""
    logger.info("收到 /basketball")
    user_id = update.effective_user.id if update.effective_user else 0
    _record_user_query(user_id, "basketball", "sport", "basketball")
    _record_user_query(user_id, "basketball", "command")
    await reply(update, "⏳ 正在生成今日籃球 AI 分析，請稍候...")
    try:
        from modules.nba import get_games
        from modules.sports_analyzer import analyze_basketball
        games = get_games()
        if not games:
            await reply(update, "🏀 今日暫無籃球賽事資訊。")
            return
        sep = "═" * 24
        analysis = analyze_basketball("\n".join(games))
        await reply_split(update, f"{sep}\n🏀 今日籃球 AI 分析\n{sep}\n\n{analysis}\n\n{sep}\n📡 世界體育數據室\n⚠️ 分析僅供參考，請理性投注")
    except Exception as e:
        logger.error(f"Basketball analyze error: {e}", exc_info=True)
        await reply(update, "老闆您好，籃球分析功能暫時無法使用。如需協助請聯繫客服 @yu_888yu")


async def cmd_all_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🔥 三種運動綜合 AI 分析"""
    logger.info("收到 /allanalyze")
    user_id = update.effective_user.id if update.effective_user else 0
    _record_user_query(user_id, "allanalyze", "command")
    await reply(update, "⏳ 正在生成三種運動綜合 AI 分析，請稍候（約需 30 秒）...")
    try:
        from modules.football import get_matches as get_football
        from modules.mlb import get_games as get_baseball
        from modules.nba import get_games as get_basketball
        from modules.sports_analyzer import analyze_all_sports
        football_text   = "\n".join(get_football()) or ""
        baseball_text   = "\n".join(get_baseball()) or ""
        basketball_text = "\n".join(get_basketball()) or ""
        if not any([football_text, baseball_text, basketball_text]):
            await reply(update, "😴 今日暫無足球、棒球、籃球賽事資訊。")
            return
        sep = "═" * 24
        now_str = datetime.now(tz).strftime("%Y/%m/%d")
        analysis = analyze_all_sports(football_text, baseball_text, basketball_text)
        await reply_split(update, f"{sep}\n🔥 三種運動綜合 AI 分析\n📅 {now_str}\n{sep}\n\n{analysis}\n\n{sep}\n📡 世界體育數據室\n⚠️ 分析僅供參考，請理性投注")
    except Exception as e:
        logger.error(f"All analyze error: {e}", exc_info=True)
        await reply(update, "老闆您好，綜合分析功能暫時無法使用。如需協助請聯繫客服 @yu_888yu")


async def cmd_winrate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """📊 勝率統計面板（靈感來自 playsport.cc）"""
    logger.info("收到 /winrate")
    sport = " ".join(context.args) if context.args else ""
    if not sport:
        await reply(update, (
            "📊 勝率統計面板\n\n請指定運動類型，例如：\n"
            "• /winrate 足球\n• /winrate 棒球\n• /winrate 籃球\n\n"
            "此功能顯示各聯盟近期主推勝率統計，靈感來自 playsport.cc 的戰績總覽。"
        ))
        return
    try:
        from modules.sports_analyzer import generate_win_rate_panel
        demo_records = {
            "足球": [
                {"league": "英超", "wins": 12, "losses": 5},
                {"league": "西甲", "wins": 8,  "losses": 6},
                {"league": "德甲", "wins": 10, "losses": 4},
                {"league": "意甲", "wins": 7,  "losses": 7},
                {"league": "歐冠", "wins": 9,  "losses": 3},
            ],
            "棒球": [
                {"league": "MLB", "wins": 15, "losses": 8},
                {"league": "WBC", "wins": 6,  "losses": 2},
            ],
            "籃球": [
                {"league": "NBA", "wins": 18, "losses": 7},
            ],
        }
        sport_key = sport.strip()
        records = demo_records.get(sport_key, [])
        if not records:
            await reply(update, f"❌ 找不到「{sport_key}」的勝率資料，請輸入：足球、棒球 或 籃球")
            return
        panel = generate_win_rate_panel(sport_key, records)
        sep = "═" * 24
        await reply(update, f"{sep}\n{panel}\n{sep}\n📡 世界體育數據室\n⚠️ 數據僅供參考")
    except Exception as e:
        logger.error(f"Winrate error: {e}", exc_info=True)
        await reply(update, "老闆您好，勝率統計功能暫時無法使用。如需協助請聯繫客服 @yu_888yu")


# ══════════════════════════════════════════════
#  V18 新增：用戶喜好記憶指令
# ══════════════════════════════════════════════

async def cmd_myfav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/myfav — 個人喜好總覽"""
    logger.info("收到 /myfav")
    user_id = update.effective_user.id if update.effective_user else 0
    try:
        from modules.user_preferences import format_user_preference_summary
        summary = format_user_preference_summary(user_id)
        await reply_split(update, summary)
    except Exception as e:
        logger.error(f"myfav error: {e}", exc_info=True)
        await reply(update, "老闆您好，個人喜好查詢功能暫時無法使用。如需協助請聯繫客服 @yu_888yu")


async def cmd_style(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/style — 切換互動習慣偏好"""
    logger.info("收到 /style")
    buttons = [
        [InlineKeyboardButton("📊 詳細分析派（完整 AI 分析）", callback_data="style_detailed")],
        [InlineKeyboardButton("⚡ 快速比分派（簡短比分）",     callback_data="style_brief")],
        [InlineKeyboardButton("🤖 自動判斷（根據習慣）",       callback_data="style_auto")],
    ]
    await reply(
        update,
        "📱 請選擇您的互動習慣偏好：\n\n"
        "• 📊 詳細分析派：每次查詢都附上完整 AI 分析\n"
        "• ⚡ 快速比分派：只顯示比分，不附分析\n"
        "• 🤖 自動判斷：根據您的使用習慣自動選擇",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ══════════════════════════════════════════════
#  V18 新增：投票預測遊戲指令
# ══════════════════════════════════════════════

async def cmd_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/checkin — 每日簽到領積分"""
    logger.info("收到 /checkin")
    user_id = update.effective_user.id if update.effective_user else 0
    user = update.effective_user
    username = f"@{user.username}" if user and user.username else ""
    full_name = user.full_name if user else ""
    try:
        from modules.checkin_system import do_checkin, format_checkin_message, init_checkin_db
        init_checkin_db()
        result = do_checkin(user_id, username, full_name)
        msg = format_checkin_message(result)
        await reply_split(update, msg)
    except Exception as e:
        logger.error(f"checkin error: {e}", exc_info=True)
        await reply(update, "老闆您好，簽到功能暫時無法使用。如需協助請聯繫客服 @yu_888yu")


async def cmd_rank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/rank — 積分排行榜 Top 10（整合簽到 + 預測積分）"""
    logger.info("收到 /rank")
    try:
        from modules.checkin_system import get_points_leaderboard, format_leaderboard, init_checkin_db
        init_checkin_db()
        leaderboard = get_points_leaderboard(top_n=10)
        if leaderboard:
            msg = format_leaderboard(leaderboard)
        else:
            # 嘗試舊版排行榜
            from modules.prediction_game import get_leaderboard, format_leaderboard_message
            leaderboard = get_leaderboard(top_n=10)
            msg = format_leaderboard_message(leaderboard)
        await reply_split(update, msg)
    except Exception as e:
        logger.error(f"rank error: {e}", exc_info=True)
        await reply(update, "老闆您好，排行榜功能暫時無法使用。如需協助請聯繫客服 @yu_888yu")


async def cmd_myscore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/myscore — 個人積分與預測戰績"""
    logger.info("收到 /myscore")
    user_id = update.effective_user.id if update.effective_user else 0
    username = _get_username(update)
    try:
        from modules.checkin_system import get_user_points_info, format_user_score, init_checkin_db
        init_checkin_db()
        info = get_user_points_info(user_id)
        if info:
            msg = format_user_score(info)
        else:
            from modules.prediction_game import format_personal_score_message
            msg = format_personal_score_message(user_id, username)
        await reply_split(update, msg)
    except Exception as e:
        logger.error(f"myscore error: {e}", exc_info=True)
        await reply(update, "老闆您好，積分查詢功能暫時無法使用。如需協助請聯繫客服 @yu_888yu")


async def cmd_predict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/predict — 查看今日可預測的比賽"""
    logger.info("收到 /predict")
    try:
        from modules.daily_analysis import fetch_all_today_games, generate_focus_matches, format_prediction_poll_text
        all_games = fetch_all_today_games()
        if not all_games:
            await reply(update, "目前暫無可預測的賽事，請稍後再試！")
            return
        focus = generate_focus_matches(all_games)
        if not focus:
            await reply(update, "今日暫無即將開始的焦點賽事可供預測。")
            return
        for match in focus:
            poll_text = format_prediction_poll_text(match)
            try:
                await update.message.reply_poll(
                    question=f"{match['league']}：{match['away_team']} vs {match['home_team']}，誰會贏？",
                    options=[match['away_team'], match['home_team'], "平手/其他"],
                    is_anonymous=False,
                )
            except Exception as poll_err:
                logger.error(f"發送投票失敗: {poll_err}")
                await reply(update, poll_text)
    except Exception as e:
        logger.error(f"predict error: {e}", exc_info=True)
        await reply(update, "老闆您好，預測功能暫時無法使用。如需協助請聯繫客服 @yu_888yu")


async def cmd_myprediction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/myprediction — 查看我的預測記錄"""
    logger.info("收到 /myprediction")
    user_id = update.effective_user.id if update.effective_user else 0
    username = _get_username(update)
    try:
        from modules.prediction_game import format_personal_score_message
        msg = format_personal_score_message(user_id, username)
        await reply_split(update, msg)
    except Exception as e:
        logger.error(f"myprediction error: {e}", exc_info=True)
        await reply(update, "老闆您好，預測記錄查詢功能暫時無法使用。如需協助請聯繫客服 @yu_888yu")


async def cmd_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/score [隊伍名] — 查詢隊伍即時比分 + 近況"""
    logger.info("收到 /score")
    user_id = update.effective_user.id if update.effective_user else 0
    user_lang = _get_user_lang(context, user_id)
    args = context.args
    if not args:
        await reply(update, "請輸入隊伍名稱，例如：/score 湖人")
        return
    query = " ".join(args)
    try:
        await handle_score_query(
            update, query,
            user_id=user_id,
            original_message=f"/score {query}",
            action="score",
            user_lang=user_lang,
        )
        _record_user_query(user_id, query, "team")
    except Exception as e:
        logger.error(f"score cmd error: {e}", exc_info=True)
        await reply(update, f"查詢 {query} 失敗，請稍後再試。如需協助請聯繫客服 @yu_888yu")


async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    處理 Telegram Poll 投票（PollAnswerHandler）。
    當用戶在頻道 Poll 中投票時自動觸發。
    """
    poll_answer = update.poll_answer
    if not poll_answer:
        return

    poll_id     = poll_answer.poll_id
    user_id     = poll_answer.user.id
    username    = f"@{poll_answer.user.username}" if poll_answer.user.username else poll_answer.user.first_name
    option_ids  = poll_answer.option_ids  # 用戶選擇的選項索引列表

    if not option_ids:
        return  # 用戶撤回投票

    chosen_option = option_ids[0]  # 單選 Poll 只取第一個

    try:
        from modules.prediction_game import record_vote
        record_vote(poll_id, user_id, username, chosen_option)
        logger.info(f"[投票記錄] user={user_id} poll={poll_id} option={chosen_option}")
    except Exception as e:
        logger.error(f"handle_poll_answer error: {e}", exc_info=True)


# ══════════════════════════════════════════════
#  V18 新增：群體行為洞察指令
# ══════════════════════════════════════════════

async def cmd_insights(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/insights — 即時社群趨勢洞察"""
    logger.info("收到 /insights")
    await reply(update, "⏳ 正在生成社群趨勢洞察...")
    try:
        from modules.community_analytics import generate_insights_snapshot
        snapshot = generate_insights_snapshot()
        await reply_split(update, snapshot)
    except Exception as e:
        logger.error(f"insights error: {e}", exc_info=True)
        await reply(update, "老闆您好，趨勢洞察功能暫時無法使用。如需協助請聯繫客服 @yu_888yu")


# ══════════════════════════════════════════════
#  訊息分發邏輯
# ══════════════════════════════════════════════

async def dispatch_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """
    統一的訊息分發函數（私訊和群組共用）。
    V19 重構：
      - 客服問題（充值/提現/帳號等）→ FAQ 話術直接回答
      - 體育問題 → GPT 意圖識別 → ESPN API → GPT 自然語言整理回覆
      - 查詢時自動記錄個人喜好 + 群體統計
      - 查詢後主動推薦相關賽事（若有喜好記錄）
    """
    user_id = update.effective_user.id if update.effective_user else 0
    user_lang = _get_user_lang(context, user_id)

    # ── Step 0：功能介紹關鍵字檢測（固定回覆，不走 GPT）──
    _INTRO_KEYWORDS = [
        "你能做什麼", "你有什麼功能", "介紹一下",
        "你是什麼", "有什麼功能", "有哪些功能", "能做什麼",
        "你可以做什麼", "有什麼用", "怎麼用", "怎麼使用",
        "你的功能", "有什麼服務", "能幫我什麼", "能幫什麼",
        "what can you do", "what are your features", "introduce yourself",
    ]
    _INTRO_REPLY = (
        "🤖 LA1 智能服務平台\n\n"
        "✨ AI 體育分析 | 即時比分 | 勝率預測\n\n"
        "🎰 539 彩票遊戲（L幣系統）\n\n"
        "📊 我能幫你做什麼：\n"
        "• 查詢任何賽事比分、賽程、排名\n"
        "• WBC、NBA、足球等即時數據\n"
        "• AI 分析勝率與賽事預測\n"
        "• 每日 20:30 自動開獎 539 彩票\n\n"
        "🛠 AI Bot 設計與自動化服務\n\n"
        "可建立：\n"
        "• AI 客服 Bot\n"
        "• Telegram 社群 Bot\n"
        "• AI 分析系統\n"
        "• 自動推播\n"
        "• 自動行銷\n\n"
        "從 設計 → 開發 → 部署 → 維護\n"
        "完整技術服務。\n\n"
        "合作洽詢 👉 @LA1111_bot"
    )
    text_lower = text.lower()
    if any(kw in text_lower for kw in _INTRO_KEYWORDS):
        await reply_split(update, _INTRO_REPLY)
        return

    # ── Step 1：代理 / 商務合作關鍵字 ──
    _AGENT_KEYWORDS = ["代理", "合作", "招商", "推廣", "加盟", "代理合作"]
    if any(kw in text_lower for kw in _AGENT_KEYWORDS):
        await reply_split(update,
            "老闆您好 👋\n\n"
            "代理 / 商務合作請聯繫：\n\n"
            "🤝 @OFA168Abe1"
        )
        return

    # ── Step 2：平台規章 FAQ（先於一般客服關鍵字，避免多帳號/USDT/超商被欸消）──
    if "多帳號" in text_lower:
        await reply_split(update,
            "老闆您好 👋\n\n"
            "一位會員僅可使用一組帳號，請勿重複註冊。"
        )
        return
    if "未滿18" in text_lower or "未满18" in text_lower:
        await reply_split(update,
            "老闆您好 👋\n\n"
            "本平台僅提供年滿 18 歲會員使用，請確認您符合年齡規定。"
        )
        return
    if "usdt" in text_lower:
        await reply_split(update,
            "老闆您好 👋\n\n"
            "USDT 儲值不會自動上分，請提供轉帳明細給客服 👑 @yu_888yu 協助上分。"
        )
        return
    if "超商" in text_lower:
        await reply_split(update,
            "老闆您好 👋\n\n"
            "超商代碼支付約 10–20 分鐘會自動上分，請耐心等候即可。"
        )
        return

    # ── Step 3：人工客服關鍵字（金流 / 帳號問題）──
    _CS_KEYWORDS_DIRECT = [
        "儲值", "充值", "上分", "提款", "提現",
        "託售", "帳號", "登入", "密碼", "異常",
        "退款", "銀行",
    ]
    if any(kw in text_lower for kw in _CS_KEYWORDS_DIRECT):
        await reply_split(update,
            "老闆您好 👋\n\n"
            "此問題需要客服協助處理\n\n"
            "請聯繫客服：\n\n"
            "👑 @yu_888yu"
        )
        return

    # ── Step 4：註冊 / 開戶 FAQ ──
    _REG_KEYWORDS = ["註冊", "我要註冊", "如何註冊", "怎麼開戶", "開戶", "註冊入口"]
    if any(kw in text_lower for kw in _REG_KEYWORDS):
        await reply_split(update,
            "老闆您好 👋\n\n"
            "請使用以下入口註冊：\n\n"
            "🇹🇼 台站\n"
            "http://La1111.meta1788.com/\n\n"
            "🌏 U站\n"
            "http://la1111.ofa168kh.com/"
        )
        return

    try:
        from modules.ai_chat import (
            should_use_bot_function, get_ai_response, add_to_history,
            generate_sports_reply, classify_message_type, _check_faq,
        )

        # ── Step 1：快速判斷訊息類型 ──
        msg_type = classify_message_type(text)
        logger.info(f"[dispatch] user={user_id} lang={user_lang} type={msg_type} text='{text}'")

        # ── Step 2：客服問題 → FAQ 話術直接回答（不走 GPT 意圖識別）──
        if msg_type == "cs":
            faq_reply = _check_faq(text, lang=user_lang)
            if faq_reply:
                await reply_split(update, faq_reply)
                add_to_history(user_id, "user", text)
                add_to_history(user_id, "assistant", faq_reply[:200])
                return
            # FAQ 未命中，走 GPT 客服助理
            ai_reply = get_ai_response(user_id, text, user_lang=user_lang)
            ai_reply = _append_cs_contact(ai_reply)
            await reply_split(update, ai_reply)
            return

        # ── Step 3：所有訊息（體育/聊天）→ GPT 意圖識別 ──
        # 注意：msg_type 可能是 "sports" 或 "chat"，兩者都必須有回覆
        if msg_type in ("sports", "chat"):
            intent = should_use_bot_function(user_id, text)
            action = intent.get("action", "chat")
            query  = intent.get("query", "").strip()
            logger.info(f"[dispatch] → action={action} query='{query}'")

            if action == "details" and query:
                await handle_details_query(update, query)
                _record_user_query(user_id, query, "team")
                add_to_history(user_id, "user", text)
                add_to_history(user_id, "assistant", f"查詢了 {query} 的即時詳細資料")

            elif action == "upcoming" and query:
                await reply(update, f"⏳ 查詢 {query} 的下一場賽程...")
                result = get_upcoming_matches(query)
                raw_response = format_upcoming_response(result)
                # ── 用 GPT 整理賽程回覆 ──
                try:
                    gpt_reply = generate_sports_reply(
                        user_id=user_id,
                        user_message=text,
                        raw_data=raw_response,
                        action="upcoming",
                        query=query,
                        user_lang=user_lang,
                    )
                    await reply_split(update, gpt_reply)
                except Exception:
                    await reply_split(update, raw_response)
                _record_user_query(user_id, query, "team")
                add_to_history(user_id, "user", text)
                add_to_history(user_id, "assistant", raw_response[:200])

            elif action == "score" and query:
                await handle_score_query(
                    update, query,
                    user_id=user_id,
                    original_message=text,
                    action="score",
                    user_lang=user_lang,
                )
                _record_user_query(user_id, query, "team")

            elif action == "live":
                await reply(update, "⏳ 正在獲取目前進行中的比賽...")
                result = search_live_scores("live")
                raw_text = format_response(result)
                try:
                    gpt_reply = generate_sports_reply(
                        user_id=user_id, user_message=text,
                        raw_data=raw_text, action="live", query="",
                        user_lang=user_lang,
                    )
                    await reply_split(update, gpt_reply)
                except Exception:
                    await reply_split(update, raw_text)

            elif action == "hot":
                await reply(update, "⏳ 正在獲取今日熱門焦點賽事...")
                result = search_live_scores("hot")
                raw_text = format_response(result)
                try:
                    gpt_reply = generate_sports_reply(
                        user_id=user_id, user_message=text,
                        raw_data=raw_text, action="hot", query="",
                        user_lang=user_lang,
                    )
                    await reply_split(update, gpt_reply)
                except Exception:
                    await reply_split(update, raw_text)

            elif action == "leaders":
                context.args = query.split() if query else []
                await cmd_leaders(update, context)

            elif action == "today":
                await reply(update, "⏳ 正在獲取今日賽事總覽...")
                result = search_live_scores("today")
                raw_text = format_response(result)
                try:
                    gpt_reply = generate_sports_reply(
                        user_id=user_id, user_message=text,
                        raw_data=raw_text, action="today", query="",
                        user_lang=user_lang,
                    )
                    await reply_split(update, gpt_reply)
                except Exception:
                    await reply_split(update, raw_text)
                _record_user_query(user_id, "today", "command")

            elif action == "analyze" and query:
                context.args = query.split()
                await cmd_analyze(update, context)

            elif action == "football_analyze":
                await cmd_football_analyze(update, context)

            elif action == "baseball_analyze":
                await cmd_baseball_analyze(update, context)

            elif action == "basketball_analyze":
                await cmd_basketball_analyze(update, context)

            elif is_query(text):
                # 備用：is_query 判斷為體育查詢但 GPT 沒識別到
                await handle_score_query(
                    update, text,
                    user_id=user_id,
                    original_message=text,
                    action="score",
                    user_lang=user_lang,
                )
                _record_user_query(user_id, text, "team")

            else:
                # action == "chat" 或其他未識別動作 → 走 GPT 客服助理
                # 這是所有一般訊息（嗨、你好、有什麼遊戲等）的最終回覆路徑
                logger.info(f"[dispatch] → 走 GPT 客服助理 text='{text}'")
                ai_reply = get_ai_response(user_id, text, user_lang=user_lang)
                ai_reply = _append_cs_contact(ai_reply)
                await reply_split(update, ai_reply)
                add_to_history(user_id, "user", text)
                add_to_history(user_id, "assistant", ai_reply[:200])

        # ── V18：查詢後主動推薦（僅私訊，避免頻道刷屏）──
        if update.message and update.message.chat.type == "private":
            await _maybe_send_recommendation(update, user_id)

    except Exception as e:
        logger.error(f"dispatch error: {e}", exc_info=True)
        if is_query(text):
            try:
                await handle_score_query(update, text, user_id=user_id)
            except Exception as e2:
                logger.error(f"score query fallback error: {e2}")
                await reply(update, "老闆您好，查詢暫時無法取得資料，如需協助請聯繫客服 @yu_888yu")
        else:
            try:
                from modules.ai_chat import get_ai_response
                ai_reply = get_ai_response(user_id, text, user_lang=user_lang)
                ai_reply = _append_cs_contact(ai_reply)
                await reply_split(update, ai_reply)
            except Exception as e2:
                logger.error(f"AI fallback error: {e2}", exc_info=True)
                # V21.1: 最終 fallback 也給出友好回覆，不再千篇一律客服訊息
                await reply(update, "老闆您好！我是 LA1 體育 AI 助手。\n\n您可以：\n- 直接輸入隊名查即時比分\n- 輸入 /help 查看所有指令\n- 問我任何體育相關問題！\n\n如有帳號或金流問題，請聯繫客服 @yu_888yu")


async def _maybe_send_recommendation(update: Update, user_id: int):
    """
    主動推薦相關賽事（V18 新增）。
    條件：用戶有查詢歷史 + 距上次推薦超過 4 小時 + 有相關賽事。
    """
    try:
        from modules.user_preferences import should_send_recommendation, generate_recommendation
        from modules.football import get_matches as get_football
        from modules.mlb import get_games as get_baseball
        from modules.nba import get_games as get_basketball

        if not should_send_recommendation(user_id):
            return

        all_matches = []
        try:
            all_matches.extend(get_football())
        except Exception:
            pass
        try:
            all_matches.extend(get_baseball())
        except Exception:
            pass
        try:
            all_matches.extend(get_basketball())
        except Exception:
            pass

        if not all_matches:
            return

        rec = generate_recommendation(user_id, all_matches)
        if rec:
            await reply(update, f"💡 個人化推薦\n\n{rec}")
            logger.info(f"[推薦] 已發送給 user={user_id}")
    except Exception as e:
        logger.debug(f"推薦發送失敗（非致命）: {e}")


# ══════════════════════════════════════════════
#  歡迎與訊息處理
# ══════════════════════════════════════════════

async def send_first_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """首次私訊自動歡迎（V18：同步語言到 SQLite）"""
    user_id = update.effective_user.id if update.effective_user else 0
    welcome_text = (
        "🏆 歡迎來到 LA1 智能服務平台！\n\n"
        "✅ MLB / NBA / NHL / 足球 即時比分\n"
        "✅ AI 勝率預測與比賽分析\n"
        "✅ ⚽⚾🏀 三種運動 AI 深度分析\n"
        "✅ 🎯 投票預測遊戲 + 積分排行榜\n"
        "✅ 📊 社群趨勢洞察 + 個人喜好記憶\n"
        "✅ 直接問任何體育問題，不需要指令！\n\n"
        "🌐 平台入口：\n"
        "🇹🇼 台站｜La1111.meta1788.com/\n"
        "🇭🇰🇲🇾🇲🇴🇻🇳 U站｜la1111.ofa168kh.com/\n"
        "🇰🇭 代理｜la1111.ofa168kh.com/\n\n"
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

    user_id = update.effective_user.id if update.effective_user else 0

    # ── 安全檢查（速率限制 / Prompt Injection / 訊息長度）──
    from modules.security import check_message as _sec_check
    sec = _sec_check(user_id, text)
    if not sec.allowed:
        logger.info(f"[安全] 私訊被擋截 user_id={user_id} reason={sec.reason}")
        await update.message.reply_text(sec.reply_text)
        return

    # ── 每日第一次訊息：發送歡迎影片 + inline keyboard ──
    if user_id:
        try:
            from modules.user_preferences import should_send_daily_welcome
            if should_send_daily_welcome(user_id):
                await send_daily_welcome(update, context, user_id)
        except Exception as e:
            logger.warning(f"[每日歡迎] 判斷失敗: {e}")

    if await handle_menu_button(update, context, text):
        return
    await dispatch_message(update, context, text)


async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理群組訊息"""
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    logger.info(f"[群組] {text}")

    user_id = update.effective_user.id if update.effective_user else 0

    # ── 安全檢查（速率限制 / Prompt Injection / 訊息長度）──
    from modules.security import check_message as _sec_check
    sec = _sec_check(user_id, text)
    if not sec.allowed:
        logger.info(f"[安全] 群組訊息被擋截 user_id={user_id} reason={sec.reason}")
        await update.message.reply_text(sec.reply_text)
        return

    # ── 每日第一次訊息：發送歡迎影片 + inline keyboard ──
    if user_id:
        try:
            from modules.user_preferences import should_send_daily_welcome
            if should_send_daily_welcome(user_id):
                await send_daily_welcome(update, context, user_id)
        except Exception as e:
            logger.warning(f"[每日歡迎] 判斷失敗: {e}")

    # ── 群組說話 L幣獎勵（V20）──
    if user_id:
        try:
            user = update.effective_user
            username = user.username if user else None
            full_name = user.full_name if user else "Unknown"
            bonus_result = claim_chat_bonus(
                user_id=user_id,
                username=username,
                full_name=full_name,
                amount=lottery_settings.chat_bonus,
                starting_coins=lottery_settings.starting_coins,
                now_iso=datetime.now(pytz.timezone(TIMEZONE)).isoformat(),
            )
            if bonus_result is not None:
                logger.info(f"[L幣] user_id={user_id} 群組發言獎勵 +{lottery_settings.chat_bonus}，餘額={bonus_result}")
        except Exception as e:
            logger.warning(f"[L幣] 群組發言獎勵失敗: {e}")

    if await handle_menu_button(update, context, text):
        return
    await dispatch_message(update, context, text)


async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理頻道留言區訊息（含幽默引導與個資偵測）"""
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    logger.info(f"[頻道留言] {text}")

    # ── 1. 個資偵測與自動刪除（V17 修復：更精確的 pattern）──
    is_pii = False
    matched_pattern = None
    for pattern in PII_PATTERNS:
        if re.search(pattern, text):
            is_pii = True
            matched_pattern = pattern
            break

    if is_pii:
        logger.info(f"[PII 偵測] 觸發 pattern: {matched_pattern}, 訊息: {text[:30]}...")
        try:
            await update.message.delete()
            await reply(update, "嘿！個資不能亂貼喔 🙈 為了保護你的安全，剛才那則訊息已被移除。有問題請私訊 @LA1111_bot 處理！")
        except Exception as e:
            logger.error(f"刪除個資訊息失敗: {e}")
            await reply(update, "嘿！個資不能亂貼喔 🙈 為了保護你的安全，請盡快移除剛才的訊息。有問題請私訊 @LA1111_bot 處理！")
        return

    # ── 2. 幽默引導與客服問題處理 ──
    text_lower = text.lower()
    cs_keywords = ["帳號", "儲值", "提現", "充值", "託售", "點數", "沒上分", "密碼", "註冊", "登入"]
    if any(kw in text_lower for kw in cs_keywords):
        import random
        humor_replies = [
            "哇！這個問題問得好！不過我只是個愛看球的 AI，這種大事還是交給真人處理比較穩 😂 快去找 @LA1111_bot，他比我厲害多了！",
            "這種問題找我沒用啦 😂 快去找 @LA1111_bot，他專門處理這種疑難雜症！",
            "哎呀，我的電路板處理不了金流問題 🤖 這種專業的事請私訊 @LA1111_bot 處理喔！",
        ]
        await reply(update, random.choice(humor_replies))
        return

    # ── 3. 正常體育查詢（頻道留言走 dispatch_message，確保 GPT 整理）──
    user_id = update.effective_user.id if update.effective_user else 0
    user_lang_ch = _get_user_lang(context, user_id)
    if is_query(text):
        await handle_score_query(
            update, text,
            user_id=user_id,
            original_message=text,
            action="score",
            user_lang=user_lang_ch,
        )
    else:
        import random
        humor_chat = [
            "這球你怎麼看？我覺得很有戲喔！😎",
            "哈哈，說得好！大家一起幫主隊加油！🔥",
            "看球就是要熱鬧！有什麼想問的隨時問我喔 🏀⚾",
            "我也在盯著這場，心跳好快啊！💓",
        ]
        await reply(update, random.choice(humor_chat))


async def handle_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """新成員歡迎訊息"""
    if not update.message or not update.message.new_chat_members:
        return
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        name    = member.username if member.username else member.first_name
        mention = f"@{name}" if member.username else f"[{name}](tg://user?id={member.id})"
        welcome_text = (
            f"👋 歡迎 {mention} 加入！\n\n"
            "🏆 世界體育數據室 提供：\n"
            "• MLB / NBA / NHL / 足球 即時比分\n"
            "• ⚽⚾🏀 三種運動 AI 分析\n"
            "• 🎯 投票預測遊戲 + 積分排行榜\n"
            "• 直接問 Bot 任何體育問題！\n\n"
            "💼 合作夥伴：https://t.me/yu_888yu"
        )
        await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def handle_score_query(
    update: Update,
    query: str,
    user_id: int = 0,
    original_message: str = "",
    action: str = "score",
    user_lang: str = "zh_tw",
):
    """
    處理比分查詢。
    V19 更新：查完 ESPN 資料後，用 GPT generate_sports_reply() 生成自然語言回覆。
    """
    logger.info(f"開始查詢: {query}")
    try:
        result   = search_live_scores(query)
        raw_text = format_response(result)

        # ── V19：用 GPT 整理成自然語言回覆 ──
        if user_id:
            try:
                from modules.ai_chat import generate_sports_reply, add_to_history
                gpt_reply = generate_sports_reply(
                    user_id=user_id,
                    user_message=original_message or query,
                    raw_data=raw_text,
                    action=action,
                    query=query,
                    user_lang=user_lang,
                )
                await reply_split(update, gpt_reply)
                add_to_history(user_id, "user", original_message or query)
                add_to_history(user_id, "assistant", gpt_reply[:200])
            except Exception as gpt_err:
                logger.warning(f"GPT 整理回覆失敗，改用原始資料: {gpt_err}")
                await reply_split(update, raw_text)
        else:
            # 沒有 user_id 時直接回傳原始格式（頻道查詢等）
            await reply_split(update, raw_text)

    except Exception as e:
        logger.error(f"Query error: {e}", exc_info=True)
        await reply(update, "老闆您好，查詢暫時無法取得資料，請稍後再試，或聯繫客服 @yu_888yu 協助。")
async def handle_details_query(update: Update, query: str):
    """處理即時詳細資料查詢"""
    logger.info(f"即時詳細資料查詢: {query}")
    try:
        result      = search_live_scores(query)
        live_events = [e for e in result.get("events", []) if e.get("state") == "in"]
        if not live_events:
            await reply(update, f"😴 {query} 目前沒有進行中的比賽")
            return
        e       = live_events[0]
        details = get_live_game_details(e.get("game_id"), e.get("sport"), e.get("league"))
        msg     = format_game_details(details)
        await reply_split(update, msg)
    except Exception as e:
        logger.error(f"Details error: {e}", exc_info=True)
        await reply(update, "❌ 查詢詳細資料失敗")


# ══════════════════════════════════════════════
#  主程式
# ══════════════════════════════════════════════

def main():
    if not BOT_TOKEN:
        logger.error("未設定 BOT_TOKEN 環境變數")
        return

    # ── 初始化 539 彩票資料庫（V20）──
    try:
        lottery_init_db()
        logger.info("[539] 彩票資料庫初始化完成")
    except Exception as e:
        logger.error(f"[539] 彩票資料庫初始化失敗: {e}")

    # ── 初始化簽到積分資料庫（V21）──
    try:
        from modules.checkin_system import init_checkin_db
        init_checkin_db()
        logger.info("[簽到] 積分資料庫初始化完成")
    except Exception as e:
        logger.error(f"[簽到] 積分資料庫初始化失敗: {e}")

    app = Application.builder().token(BOT_TOKEN).build()

    # ── 基本指令 ──
    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("help",       cmd_help))
    app.add_handler(CommandHandler("today",      cmd_today))
    app.add_handler(CommandHandler("live",       cmd_live))
    app.add_handler(CommandHandler("hot",        cmd_hot))
    app.add_handler(CommandHandler("leaders",    cmd_leaders))
    app.add_handler(CommandHandler("analyze",    cmd_analyze))
    app.add_handler(CommandHandler("odds",       cmd_odds))

    # ── 三種運動 AI 分析（V17）──
    app.add_handler(CommandHandler("football",   cmd_football_analyze))
    app.add_handler(CommandHandler("baseball",   cmd_baseball_analyze))
    app.add_handler(CommandHandler("basketball", cmd_basketball_analyze))
    app.add_handler(CommandHandler("allanalyze", cmd_all_analyze))
    app.add_handler(CommandHandler("winrate",    cmd_winrate))

    # ── 用戶喜好記憶（V18）──
    app.add_handler(CommandHandler("myfav",      cmd_myfav))
    app.add_handler(CommandHandler("style",      cmd_style))

    # ── 預測遊戲 & 積分系統（V21）──
    app.add_handler(CommandHandler("checkin",     cmd_checkin))
    app.add_handler(CommandHandler("rank",        cmd_rank))
    app.add_handler(CommandHandler("myscore",     cmd_myscore))
    app.add_handler(CommandHandler("predict",     cmd_predict))
    app.add_handler(CommandHandler("myprediction",cmd_myprediction))
    app.add_handler(CommandHandler("score",       cmd_score))
    app.add_handler(PollAnswerHandler(handle_poll_answer))
    # ── 群體行為洞察（V18）──
    app.add_handler(CommandHandler("insights",    cmd_insights))

    # ── 539 彩票指令（V20.3 修復：移除未定義的 quick_cmd）──
    app.add_handler(CommandHandler("539",       lottery_info_cmd))
    app.add_handler(CommandHandler("quick",     bet_ui_cmd))   # /quick = 快速下注 UI
    app.add_handler(CommandHandler("balance",   lottery_balance_cmd))
    app.add_handler(CommandHandler("daily",     lottery_daily_cmd))
    app.add_handler(CommandHandler("history",   lottery_history_cmd))
    app.add_handler(CommandHandler("result",    lottery_result_cmd))
    app.add_handler(CommandHandler("lrank",     lottery_rank_cmd))
    app.add_handler(CommandHandler("rules",     lottery_rules_cmd))

    # ── 539 底部選單按鈕處理（group=-1 優先執行，且只處理精確匹配，不影響一般訊息）──
    app.add_handler(CallbackQueryHandler(lottery_callback_handler, pattern=r"^lot_"))
    app.add_handler(MessageHandler(filters.Regex("^🎱下注$"),      bet_ui_cmd),      group=-1)
    app.add_handler(MessageHandler(filters.Regex("^📋查詢下注$"),  lottery_history_cmd), group=-1)
    app.add_handler(MessageHandler(filters.Regex("^💰查詢L幣$"),  lottery_balance_cmd), group=-1)
    app.add_handler(MessageHandler(filters.Regex("^🏆排行榜$"),    lottery_rank_cmd),  group=-1)
    app.add_handler(MessageHandler(filters.Regex("^📖遊戲規則$"),  lottery_rules_cmd), group=-1)
    app.add_handler(MessageHandler(filters.Regex("^🔙退出彩票$"),  cmd_lottery_exit),  group=-1)
    app.add_handler(CallbackQueryHandler(handle_style_callback, pattern=r"^style_"))

    # ── 訊息處理（group=0，在 539 Regex handler 之後，確保一般訊息正常到達）──
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_members))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT, handle_message))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS  & filters.TEXT, handle_group_message))

    # ── 539 每日 20:30 開獎排程（V20）──
    try:
        from modules.lottery.scheduler_tasks import draw_job
        from datetime import time as dt_time
        jq = app.job_queue
        tz_obj = pytz.timezone(TIMEZONE)
        jq.run_daily(
            draw_job,
            time=dt_time(
                hour=lottery_settings.draw_hour,
                minute=lottery_settings.draw_minute,
                tzinfo=tz_obj,
            ),
            name="lottery_daily_draw",
        )
        logger.info(f"[539] 開獎排程已設定：每日 {lottery_settings.draw_hour:02d}:{lottery_settings.draw_minute:02d}")
    except Exception as e:
        logger.error(f"[539] 開獎排程設定失敗: {e}")

    logger.info("Bot V21.0 LA1 SPORTS AI PLATFORM 已啟動（全面 GPT + 簽到積分 + 預測遅戲 + AI 推播 + 539 彩票）...")

    # ── Webhook 模式（避免與其他實例 Conflict）──
    WEBHOOK_DOMAIN = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
    PORT = int(os.environ.get("PORT", 8443))

    if WEBHOOK_DOMAIN:
        WEBHOOK_URL = f"https://{WEBHOOK_DOMAIN}/webhook"
        logger.info(f"[啟動] Webhook 模式：{WEBHOOK_URL} port={PORT}")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path="/webhook",
            webhook_url=WEBHOOK_URL,
            allowed_updates=["message", "callback_query", "poll_answer", "chat_member"],
            drop_pending_updates=True,
        )
    else:
        # 本地開發或未設定 RAILWAY_PUBLIC_DOMAIN 時使用 polling
        logger.info("[啟動] Polling 模式（未偵測到 RAILWAY_PUBLIC_DOMAIN）")
        app.run_polling(
            allowed_updates=["message", "callback_query", "poll_answer", "chat_member"],
            drop_pending_updates=True,
        )


if __name__ == "__main__":
    main()
