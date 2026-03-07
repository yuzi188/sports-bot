"""
熱門賽事推薦模組 - 自動挑選今日最值得關注的比賽
"""

import requests
from datetime import datetime
import pytz
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ESPN_BASE, TIMEZONE
from smart_search import translate_name

tz = pytz.timezone(TIMEZONE)

# 熱門隊伍清單（出現這些隊伍的比賽優先推薦）
HOT_TEAMS = {
    # 足球
    "liverpool", "manchester city", "arsenal", "real madrid", "barcelona",
    "bayern munich", "paris saint-germain", "inter milan", "manchester united",
    "chelsea", "juventus", "atletico madrid", "borussia dortmund",
    # MLB
    "new york yankees", "los angeles dodgers", "houston astros",
    "atlanta braves", "boston red sox", "new york mets",
    # NBA
    "los angeles lakers", "golden state warriors", "boston celtics",
    "oklahoma city thunder", "denver nuggets", "milwaukee bucks",
    # WBC
    "japan", "united states", "chinese taipei", "korea",
    "dominican republic", "venezuela",
}

HOT_ENDPOINTS = [
    ("soccer", "eng.1", "⚽", "英超"),
    ("soccer", "esp.1", "⚽", "西甲"),
    ("soccer", "ger.1", "⚽", "德甲"),
    ("soccer", "ita.1", "⚽", "意甲"),
    ("soccer", "fra.1", "⚽", "法甲"),
    ("soccer", "uefa.champions", "⚽", "歐冠"),
    ("baseball", "mlb", "⚾", "MLB"),
    ("baseball", "world-baseball-classic", "⚾", "WBC"),
    ("basketball", "nba", "🏀", "NBA"),
]


def get_hot_matches(max_count: int = 10) -> list:
    """取得今日熱門賽事"""
    now = datetime.now(tz)
    date_str = now.strftime("%Y%m%d")

    candidates = []

    for sport, league, emoji, label in HOT_ENDPOINTS:
        try:
            url = f"{ESPN_BASE}/{sport}/{league}/scoreboard?dates={date_str}"
            resp = requests.get(url, timeout=8)
            if resp.status_code != 200:
                continue
            data = resp.json()

            for event in data.get("events", []):
                comp = event.get("competitions", [{}])[0]
                competitors = comp.get("competitors", [])
                status = comp.get("status", {}).get("type", {})

                home = away = None
                home_en = away_en = ""
                for c in competitors:
                    team = c.get("team", {})
                    en_name = team.get("displayName", "")
                    td = {
                        "name": translate_name(en_name),
                        "score": c.get("score", "0"),
                    }
                    if c.get("homeAway") == "home":
                        home = td
                        home_en = en_name.lower()
                    else:
                        away = td
                        away_en = en_name.lower()

                if not home or not away:
                    continue

                # 計算熱度分數
                score = 0
                if home_en in HOT_TEAMS:
                    score += 2
                if away_en in HOT_TEAMS:
                    score += 2
                # 歐冠 / WBC 額外加分
                if league in ("uefa.champions", "world-baseball-classic"):
                    score += 1

                state = status.get("state", "pre")
                detail = status.get("detail", "")

                event_date = event.get("date", "")
                time_str = ""
                try:
                    dt = datetime.fromisoformat(event_date.replace("Z", "+00:00"))
                    local = dt.astimezone(tz)
                    time_str = local.strftime("%H:%M")
                except:
                    pass

                if state == "in":
                    line = f"🔴 {away['name']} {away['score']} - {home['score']} {home['name']} ({detail})"
                elif state == "post":
                    line = f"✅ {away['name']} {away['score']} - {home['score']} {home['name']}"
                else:
                    line = f"⏰ {time_str} {away['name']} vs {home['name']}"

                candidates.append({
                    "score": score,
                    "text": f"{emoji} [{label}] {line}",
                })

        except:
            continue

    # 按熱度排序
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return [c["text"] for c in candidates[:max_count]]


if __name__ == "__main__":
    result = get_hot_matches()
    for m in result:
        print(m)
