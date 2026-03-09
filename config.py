"""
LA1 SPORTS AI PLATFORM - 配置文件 V21.0
功能：
  - Telegram Bot / 頻道 / 群組設定
  - OpenAI GPT 設定
  - 平台入口 URL 與聯絡資訊
  - ESPN API 體育賽事設定
  - 排程時間設定
"""
import os

# ── Telegram 設定 ──
BOT_TOKEN  = os.environ.get("BOT_TOKEN", "").strip()
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@LA11118").strip()
GROUP_ID   = os.environ.get("GROUP_ID", CHANNEL_ID).strip()

# ── OpenAI 設定 ──
OPENAI_API_KEY  = os.environ.get("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "").strip()
OPENAI_MODEL    = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip()

# ── 平台入口 URL ──
GAME_URL_TW      = os.environ.get("GAME_URL_TW", "https://La1111.meta1788.com").strip()
GAME_URL_U       = os.environ.get("GAME_URL_U", "http://la1111.ofa168kh.com").strip()
AGENT_URL_KH     = os.environ.get("AGENT_URL_KH", "https://agent.ofa168kh.com").strip()

# ── 聯絡資訊 ──
HUMAN_SUPPORT    = os.environ.get("HUMAN_SUPPORT", "@yu_888yu").strip()
BUSINESS_CONTACT = os.environ.get("BUSINESS_CONTACT", "@OFA168Abe1").strip()

# ── ESPN API 基礎 URL ──
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"

# ── 支援的體育賽事 ──
SPORTS = {
    # 足球聯賽
    "soccer": {
        "eng.1":         {"name": "英超 Premier League", "emoji": "🏴\U000e0067\U000e0062\U000e0065\U000e006e\U000e0067\U000e007f", "priority": 1},
        "esp.1":         {"name": "西甲 La Liga",         "emoji": "🇪🇸", "priority": 2},
        "ger.1":         {"name": "德甲 Bundesliga",      "emoji": "🇩🇪", "priority": 3},
        "ita.1":         {"name": "意甲 Serie A",          "emoji": "🇮🇹", "priority": 4},
        "fra.1":         {"name": "法甲 Ligue 1",          "emoji": "🇫🇷", "priority": 5},
        "uefa.champions":{"name": "歐冠 UCL",             "emoji": "🏆", "priority": 0},
        "uefa.europa":   {"name": "歐霸 UEL",             "emoji": "🥈", "priority": 6},
        "jpn.1":         {"name": "日職 J-League",        "emoji": "🇯🇵", "priority": 7},
        "usa.1":         {"name": "MLS 美職",             "emoji": "🇺🇸", "priority": 8},
    },
    # 美國職業運動
    "baseball": {
        "mlb": {"name": "MLB 美國職棒", "emoji": "⚾", "priority": 1},
    },
    "basketball": {
        "nba": {"name": "NBA 美國職籃", "emoji": "🏀", "priority": 1},
    },
    "football": {
        "nfl": {"name": "NFL 美式足球", "emoji": "🏈", "priority": 1},
    },
    "hockey": {
        "nhl": {"name": "NHL 冰球", "emoji": "🏒", "priority": 1},
    },
}

# ── 時區設定（台灣時間 UTC+8）──
TIMEZONE = os.environ.get("TIMEZONE", "Asia/Taipei").strip()

# ── 發文排程（台灣時間）──
SCHEDULE = {
    "morning_preview":    "10:00",   # 今日賽程預覽 + AI 分析
    "afternoon_analysis": "14:00",   # 下午深度分析
    "evening_focus":      "18:00",   # 焦點賽事預測投票
    "night_review":       "22:00",   # 賽後復盤總結
}


def validate_config():
    """
    驗證必要環境變數。
    OPENAI_API_KEY 缺失時只印警告，不中斷啟動（AI 功能降級為 FAQ 回覆）。
    """
    if not BOT_TOKEN:
        raise RuntimeError("Missing required environment variable: BOT_TOKEN")
    if not OPENAI_API_KEY:
        import warnings
        warnings.warn(
            "OPENAI_API_KEY 未設定，AI 功能將使用 FAQ 回覆模式",
            RuntimeWarning,
            stacklevel=2,
        )
