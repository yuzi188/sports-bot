"""
球隊近期戰績模組 - 使用 ESPN 免費 API
查詢近 N 場比賽結果（含比分和日期）
"""

import requests
from datetime import datetime, timedelta
import pytz
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ESPN_BASE, TIMEZONE
from smart_search import translate_name, match_event_smart

tz = pytz.timezone(TIMEZONE)


def get_recent_matches(team_info: dict, endpoints: list, count: int = 3) -> list:
    """
    取得某隊近 N 場已結束比賽
    team_info: {"en_name": ..., "cn_name": ..., "league": ...}
    endpoints: [(sport, league, emoji), ...]
    """
    today = datetime.now(tz)
    matches = []

    for sport, league, emoji in endpoints:
        for day_offset in range(0, 10):
            if len(matches) >= count:
                break
            date = today - timedelta(days=day_offset)
            date_str = date.strftime("%Y%m%d")

            try:
                url = f"{ESPN_BASE}/{sport}/{league}/scoreboard?dates={date_str}"
                resp = requests.get(url, timeout=8)
                if resp.status_code != 200:
                    continue
                data = resp.json()

                for event in data.get("events", []):
                    if not match_event_smart(event, [team_info]):
                        continue

                    comp = event.get("competitions", [{}])[0]
                    status = comp.get("status", {}).get("type", {})
                    if status.get("state") != "post":
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

                    event_date = event.get("date", "")
                    date_display = ""
                    try:
                        dt = datetime.fromisoformat(event_date.replace("Z", "+00:00"))
                        local_dt = dt.astimezone(tz)
                        date_display = local_dt.strftime("%m/%d")
                    except:
                        pass

                    record = {
                        "date": date_display,
                        "away": away["name"],
                        "home": home["name"],
                        "away_score": away["score"],
                        "home_score": home["score"],
                        "emoji": emoji,
                    }

                    # 去重
                    is_dup = any(
                        m["away"] == record["away"]
                        and m["home"] == record["home"]
                        and m["date"] == record["date"]
                        for m in matches
                    )
                    if not is_dup:
                        matches.append(record)

            except:
                continue

        if len(matches) >= count:
            break

    return matches[:count]


def format_recent(cn_name: str, matches: list) -> str:
    """格式化近期戰績"""
    if not matches:
        return f"📋 {cn_name} 近期無比賽記錄"

    lines = [f"📋 {cn_name} 近期戰績："]
    for m in matches:
        lines.append(
            f"  {m['emoji']} {m['date']} {m['away']} {m['away_score']} - {m['home_score']} {m['home']}"
        )
    return "\n".join(lines)
