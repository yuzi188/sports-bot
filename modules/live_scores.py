"""
即時比分模組 - 抓取所有進行中的比賽
"""

import requests
from datetime import datetime
import pytz
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ESPN_BASE, TIMEZONE
from smart_search import translate_name

tz = pytz.timezone(TIMEZONE)

LIVE_ENDPOINTS = [
    ("soccer", "eng.1", "⚽", "英超"),
    ("soccer", "esp.1", "⚽", "西甲"),
    ("soccer", "ger.1", "⚽", "德甲"),
    ("soccer", "ita.1", "⚽", "意甲"),
    ("soccer", "fra.1", "⚽", "法甲"),
    ("soccer", "uefa.champions", "⚽", "歐冠"),
    ("baseball", "mlb", "⚾", "MLB"),
    ("baseball", "world-baseball-classic", "⚾", "WBC"),
    ("basketball", "nba", "🏀", "NBA"),
    ("hockey", "nhl", "🏒", "NHL"),
]


def get_live_scores() -> list:
    """取得所有進行中的比賽即時比分"""
    live = []

    for sport, league, emoji, label in LIVE_ENDPOINTS:
        try:
            url = f"{ESPN_BASE}/{sport}/{league}/scoreboard"
            resp = requests.get(url, timeout=8)
            if resp.status_code != 200:
                continue
            data = resp.json()

            for event in data.get("events", []):
                comp = event.get("competitions", [{}])[0]
                status = comp.get("status", {}).get("type", {})
                state = status.get("state", "pre")

                if state != "in":
                    continue

                competitors = comp.get("competitors", [])
                home = away = None
                for c in competitors:
                    team = c.get("team", {})
                    td = {
                        "name": translate_name(team.get("displayName", "")),
                        "score": c.get("score", "0"),
                    }
                    if c.get("homeAway") == "home":
                        home = td
                    else:
                        away = td

                if not home or not away:
                    continue

                detail = status.get("detail", "進行中")
                live.append(
                    f"{emoji} [{label}] {away['name']} {away['score']} - {home['score']} {home['name']} ({detail})"
                )

        except:
            continue

    return live


if __name__ == "__main__":
    result = get_live_scores()
    if result:
        for s in result:
            print(s)
    else:
        print("目前沒有進行中的比賽")
