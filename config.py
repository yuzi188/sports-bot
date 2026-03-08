"""
體育分析機器人 - 配置文件
"""
import os
# Telegram 設定
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@LA11118")
# ESPN API 基礎 URL
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"
# 支援的體育賽事
SPORTS = {
    # 足球聯賽
    "soccer": {
        "eng.1": {"name": "英超 Premier League", "emoji": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "priority": 1},
        "esp.1": {"name": "西甲 La Liga", "emoji": "🇪🇸", "priority": 2},
        "ger.1": {"name": "德甲 Bundesliga", "emoji": "🇩🇪", "priority": 3},
        "ita.1": {"name": "意甲 Serie A", "emoji": "🇮🇹", "priority": 4},
        "fra.1": {"name": "法甲 Ligue 1", "emoji": "🇫🇷", "priority": 5},
        "uefa.champions": {"name": "歐冠 UCL", "emoji": "🏆", "priority": 0},
        "uefa.europa": {"name": "歐霸 UEL", "emoji": "🥈", "priority": 6},
        "jpn.1": {"name": "日職 J-League", "emoji": "🇯🇵", "priority": 7},
        "usa.1": {"name": "MLS 美職", "emoji": "🇺🇸", "priority": 8},
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
# 時區設定（台灣時間 UTC+8）
TIMEZONE = "Asia/Taipei"
# 發文排程（台灣時間）
SCHEDULE = {
    "morning_preview": "10:00",      # 今日賽程預覽
    "afternoon_analysis": "14:00",   # 下午深度分析
    "evening_focus": "18:00",        # 傍晚焦點戰分析
    "night_review": "23:00",         # 賽後復盤
}
