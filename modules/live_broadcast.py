"""
live_broadcast.py - 每兩小時自動推播進行中賽事

功能：
  - 查詢 NBA 和 MLB 進行中（state=in）的比賽
  - 格式化為推播訊息
  - 若無進行中比賽則不發推播（避免空訊息）
"""

import requests
import logging
from datetime import datetime
import pytz
from config import ESPN_BASE, TIMEZONE

logger = logging.getLogger(__name__)
tz = pytz.timezone(TIMEZONE)


# ── 推播目標運動 ──
BROADCAST_SPORTS = [
    {
        "sport": "basketball",
        "league": "nba",
        "name": "NBA",
        "emoji": "🏀",
    },
    {
        "sport": "baseball",
        "league": "mlb",
        "name": "MLB",
        "emoji": "⚾",
    },
]


def _get_live_events(sport: str, league: str) -> list:
    """
    從 ESPN scoreboard API 取得進行中（state=in）的比賽。

    Returns:
        list of dict: 每筆包含 home_name, away_name, home_score, away_score, detail
    """
    url = f"{ESPN_BASE}/{sport}/{league}/scoreboard"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            logger.warning(f"ESPN {league} scoreboard 回應 {resp.status_code}")
            return []

        data = resp.json()
        events = data.get("events", [])
        live = []

        for event in events:
            competitions = event.get("competitions", [])
            if not competitions:
                continue
            competition = competitions[0]
            status = competition.get("status", {})
            state = status.get("type", {}).get("state", "pre")

            if state != "in":
                continue

            # 取得隊伍與比分
            competitors = competition.get("competitors", [])
            home = away = None
            for c in competitors:
                team_name = c.get("team", {}).get("displayName", "?")
                score = c.get("score", "0")
                if c.get("homeAway") == "home":
                    home = {"name": team_name, "score": score}
                else:
                    away = {"name": team_name, "score": score}

            if not home or not away:
                continue

            # 比賽狀態描述（第X節/第X局/剩餘時間）
            detail = status.get("type", {}).get("detail", "")

            live.append({
                "home_name": home["name"],
                "home_score": home["score"],
                "away_name": away["name"],
                "away_score": away["score"],
                "detail": detail,
            })

        return live

    except Exception as e:
        logger.error(f"取得 {league} 即時比賽失敗: {e}")
        return []


def _translate_team(name: str) -> str:
    """
    簡單的隊名中文對照（常見 NBA/MLB 隊伍）。
    若找不到對照則回傳原英文名。
    """
    _MAP = {
        # NBA
        "Boston Celtics": "波士頓塞爾提克",
        "Brooklyn Nets": "布魯克林籃網",
        "New York Knicks": "紐約尼克",
        "Philadelphia 76ers": "費城76人",
        "Toronto Raptors": "多倫多暴龍",
        "Chicago Bulls": "芝加哥公牛",
        "Cleveland Cavaliers": "克里夫蘭騎士",
        "Detroit Pistons": "底特律活塞",
        "Indiana Pacers": "印第安納溜馬",
        "Milwaukee Bucks": "密爾瓦基公鹿",
        "Atlanta Hawks": "亞特蘭大老鷹",
        "Charlotte Hornets": "夏洛特黃蜂",
        "Miami Heat": "邁阿密熱火",
        "Orlando Magic": "奧蘭多魔術",
        "Washington Wizards": "華盛頓巫師",
        "Denver Nuggets": "丹佛金塊",
        "Minnesota Timberwolves": "明尼蘇達灰狼",
        "Oklahoma City Thunder": "奧克拉荷馬雷霆",
        "Portland Trail Blazers": "波特蘭拓荒者",
        "Utah Jazz": "猶他爵士",
        "Golden State Warriors": "金州勇士",
        "Los Angeles Clippers": "洛杉磯快艇",
        "Los Angeles Lakers": "洛杉磯湖人",
        "Phoenix Suns": "鳳凰城太陽",
        "Sacramento Kings": "沙加緬度國王",
        "Dallas Mavericks": "達拉斯獨行俠",
        "Houston Rockets": "休士頓火箭",
        "Memphis Grizzlies": "曼菲斯灰熊",
        "New Orleans Pelicans": "紐奧良鵜鶘",
        "San Antonio Spurs": "聖安東尼奧馬刺",
        # MLB
        "New York Yankees": "紐約洋基",
        "Boston Red Sox": "波士頓紅襪",
        "Toronto Blue Jays": "多倫多藍鳥",
        "Baltimore Orioles": "巴爾的摩金鶯",
        "Tampa Bay Rays": "坦帕灣光芒",
        "Chicago White Sox": "芝加哥白襪",
        "Cleveland Guardians": "克里夫蘭守護者",
        "Detroit Tigers": "底特律老虎",
        "Kansas City Royals": "堪薩斯市皇家",
        "Minnesota Twins": "明尼蘇達雙城",
        "Houston Astros": "休士頓太空人",
        "Los Angeles Angels": "洛杉磯天使",
        "Oakland Athletics": "奧克蘭運動家",
        "Seattle Mariners": "西雅圖水手",
        "Texas Rangers": "德州遊騎兵",
        "Atlanta Braves": "亞特蘭大勇士",
        "Miami Marlins": "邁阿密馬林魚",
        "New York Mets": "紐約大都會",
        "Philadelphia Phillies": "費城費城人",
        "Washington Nationals": "華盛頓國民",
        "Chicago Cubs": "芝加哥小熊",
        "Cincinnati Reds": "辛辛那提紅人",
        "Milwaukee Brewers": "密爾瓦基釀酒人",
        "Pittsburgh Pirates": "匹茲堡海盜",
        "St. Louis Cardinals": "聖路易紅雀",
        "Arizona Diamondbacks": "亞利桑那響尾蛇",
        "Colorado Rockies": "科羅拉多落磯",
        "Los Angeles Dodgers": "洛杉磯道奇",
        "San Diego Padres": "聖地牙哥教士",
        "San Francisco Giants": "舊金山巨人",
    }
    return _MAP.get(name, name)


def build_live_broadcast_message() -> str | None:
    """
    建立推播訊息。
    若無任何進行中比賽，回傳 None（不發推播）。

    Returns:
        str: 格式化的推播訊息，或 None
    """
    now_str = datetime.now(tz).strftime("%m/%d %H:%M")
    sections = []

    for sport_cfg in BROADCAST_SPORTS:
        live_events = _get_live_events(sport_cfg["sport"], sport_cfg["league"])
        if not live_events:
            continue

        lines = [f"{sport_cfg['emoji']} {sport_cfg['name']}"]
        for ev in live_events:
            home = _translate_team(ev["home_name"])
            away = _translate_team(ev["away_name"])
            hs = ev["home_score"]
            as_ = ev["away_score"]
            detail = ev["detail"]
            # 格式：主隊 XX - XX 客隊（狀態）
            line = f"  {home} {hs} - {as_} {away}"
            if detail:
                line += f"（{detail}）"
            lines.append(line)

        sections.append("\n".join(lines))

    if not sections:
        # 無進行中比賽，不發推播
        return None

    body = "\n\n".join(sections)

    message = (
        f"🔴 直播中 熱門賽事\n"
        f"{'─' * 22}\n\n"
        f"{body}\n\n"
        f"{'─' * 22}\n"
        f"🎮 娛樂城：http://la1111.ofa168hk.com/\n"
        f"💼 商務合作：https://t.me/yu_888yu\n\n"
        f"📡 世界體育數據室"
    )

    return message


def task_live_broadcast():
    """
    每兩小時推播任務。
    由 scheduler.py 呼叫，若無進行中比賽則靜默跳過。
    """
    from telegram_sender import send_message

    logger.info("📡 執行每兩小時即時推播...")
    try:
        msg = build_live_broadcast_message()
        if msg is None:
            logger.info("目前無進行中比賽，跳過推播")
            return
        result = send_message(msg)
        if result.get("ok"):
            logger.info("✅ 即時推播已發送")
        else:
            logger.warning(f"推播發送失敗：{result.get('description', '')}")
    except Exception as e:
        logger.error(f"即時推播任務失敗: {e}", exc_info=True)
