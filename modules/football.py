"""
足球賽事模組 - 使用 ESPN 免費 API
"""

import requests
from datetime import datetime
import pytz
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ESPN_BASE, TIMEZONE
from smart_search import translate_name

tz = pytz.timezone(TIMEZONE)

FOOTBALL_LEAGUES = [
    ("eng.1", "英超"),
    ("esp.1", "西甲"),
    ("ger.1", "德甲"),
    ("ita.1", "意甲"),
    ("fra.1", "法甲"),
    ("uefa.champions", "歐冠"),
]


def get_matches(date_str: str = None) -> list:
    """取得今日足球焦點賽事"""
    if not date_str:
        now = datetime.now(tz)
        date_str = now.strftime("%Y%m%d")

    matches = []

    for league_code, league_name in FOOTBALL_LEAGUES:
        try:
            url = f"{ESPN_BASE}/soccer/{league_code}/scoreboard?dates={date_str}"
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                continue
            data = resp.json()

            for event in data.get("events", []):
                comp = event.get("competitions", [{}])[0]
                competitors = comp.get("competitors", [])
                status = comp.get("status", {}).get("type", {})

                home = away = None
                for c in competitors:
                    team = c.get("team", {})
                    td = {
                        "name": translate_name(team.get("displayName", "")),
                        "score": c.get("score", "0"),
                        "record": "",
                    }
                    for rec in c.get("records", []):
                        if rec.get("name") == "overall" or rec.get("type") == "total":
                            td["record"] = rec.get("summary", "")
                    if c.get("homeAway") == "home":
                        home = td
                    else:
                        away = td

                if not home or not away:
                    continue

                state = status.get("state", "pre")
                detail = status.get("detail", "")

                # 格式化時間
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

                matches.append(f"⚽ [{league_name}] {line}")

        except Exception as e:
            continue

    return matches


if __name__ == "__main__":
    result = get_matches()
    for m in result:
        print(m)
