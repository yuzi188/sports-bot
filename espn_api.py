"""
ESPN API 數據抓取模組
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Optional
import pytz
from config import ESPN_BASE, SPORTS, TIMEZONE


tz = pytz.timezone(TIMEZONE)


def get_scoreboard(sport: str, league: str, date: Optional[str] = None) -> dict:
    """取得比分板數據"""
    url = f"{ESPN_BASE}/{sport}/{league}/scoreboard"
    params = {}
    if date:
        params["dates"] = date  # format: YYYYMMDD
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Error fetching {sport}/{league}: {e}")
        return {}


def get_standings(sport: str, league: str) -> dict:
    """取得排名數據"""
    url = f"https://site.api.espn.com/apis/v2/sports/{sport}/{league}/standings"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Error fetching standings {sport}/{league}: {e}")
        return {}


def get_team_info(sport: str, league: str, team_id: str) -> dict:
    """取得隊伍詳細資訊"""
    url = f"{ESPN_BASE}/{sport}/{league}/teams/{team_id}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Error fetching team {team_id}: {e}")
        return {}


def get_news(sport: str, league: str) -> dict:
    """取得新聞"""
    url = f"{ESPN_BASE}/{sport}/{league}/news"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Error fetching news {sport}/{league}: {e}")
        return {}


def parse_event(event: dict) -> dict:
    """解析單場賽事數據"""
    competition = event.get("competitions", [{}])[0]
    competitors = competition.get("competitors", [])
    status = competition.get("status", {})
    
    home = away = None
    for c in competitors:
        team_data = {
            "id": c.get("team", {}).get("id", ""),
            "name": c.get("team", {}).get("displayName", ""),
            "short": c.get("team", {}).get("shortDisplayName", ""),
            "abbreviation": c.get("team", {}).get("abbreviation", ""),
            "score": c.get("score", "0"),
            "logo": c.get("team", {}).get("logo", ""),
            "record": "",
            "form": "",
        }
        # 取得戰績
        for rec in c.get("records", []):
            if rec.get("name") == "overall" or rec.get("type") == "total":
                team_data["record"] = rec.get("summary", "")
            elif rec.get("name") == "Home" or rec.get("type") == "home":
                team_data["home_record"] = rec.get("summary", "")
            elif rec.get("name") == "Road" or rec.get("type") == "road":
                team_data["away_record"] = rec.get("summary", "")
        # 取得近期表現
        if c.get("form"):
            team_data["form"] = c.get("form", "")
        
        # 取得統計數據
        stats = {}
        for s in c.get("statistics", []):
            stats[s.get("name", "")] = s.get("displayValue", "")
        team_data["stats"] = stats
        
        if c.get("homeAway") == "home":
            home = team_data
        else:
            away = team_data
    
    # 取得賽事狀態
    state = status.get("type", {}).get("state", "pre")
    status_detail = status.get("type", {}).get("detail", "")
    
    # 取得場地
    venue = competition.get("venue", {})
    venue_name = venue.get("fullName", "")
    
    # 取得賠率
    odds_data = {}
    for odds in competition.get("odds", []):
        odds_data = {
            "details": odds.get("details", ""),
            "overUnder": odds.get("overUnder", ""),
            "spread": odds.get("spread", ""),
            "home_ml": "",
            "away_ml": "",
        }
        # 取得 moneyline
        for hl in odds.get("homeTeamOdds", {}).get("moneyLine", [None]):
            if isinstance(hl, (int, float)):
                odds_data["home_ml"] = str(hl)
        if odds.get("homeTeamOdds", {}).get("moneyLine"):
            odds_data["home_ml"] = str(odds["homeTeamOdds"]["moneyLine"])
        if odds.get("awayTeamOdds", {}).get("moneyLine"):
            odds_data["away_ml"] = str(odds["awayTeamOdds"]["moneyLine"])
        break
    
    # 取得頭條
    headlines = []
    for h in competition.get("headlines", []):
        headlines.append(h.get("shortLinkText", h.get("description", "")))
    
    return {
        "id": event.get("id", ""),
        "name": event.get("name", ""),
        "short_name": event.get("shortName", ""),
        "date": event.get("date", ""),
        "state": state,
        "status_detail": status_detail,
        "home": home,
        "away": away,
        "venue": venue_name,
        "odds": odds_data,
        "headlines": headlines,
    }


def get_today_events(date_str: Optional[str] = None) -> dict:
    """取得今日所有賽事，按運動類別分組"""
    if not date_str:
        now = datetime.now(tz)
        date_str = now.strftime("%Y%m%d")
    
    all_events = {}
    
    for sport, leagues in SPORTS.items():
        for league_code, league_info in leagues.items():
            data = get_scoreboard(sport, league_code, date_str)
            events = data.get("events", [])
            if events:
                parsed = [parse_event(e) for e in events]
                key = f"{sport}/{league_code}"
                all_events[key] = {
                    "info": league_info,
                    "events": parsed,
                    "sport": sport,
                    "league": league_code,
                }
    
    return all_events


def get_league_standings_text(sport: str, league: str, top_n: int = 10) -> str:
    """取得聯賽排名文字"""
    data = get_standings(sport, league)
    if not data:
        return ""
    
    lines = []
    children = data.get("children", [])
    if not children:
        return ""
    
    for group in children:
        group_name = group.get("name", "")
        standings = group.get("standings", {})
        entries = standings.get("entries", [])
        
        if group_name:
            lines.append(f"\n📊 {group_name}")
        
        for i, entry in enumerate(entries[:top_n]):
            team_name = entry.get("team", {}).get("displayName", "")
            stats = {}
            for s in entry.get("stats", []):
                stats[s.get("abbreviation", s.get("name", ""))] = s.get("displayValue", "")
            
            # 根據運動類型格式化
            if sport == "soccer":
                gp = stats.get("GP", stats.get("gamesPlayed", "0"))
                w = stats.get("W", stats.get("wins", "0"))
                d = stats.get("D", stats.get("draws", "0"))
                l = stats.get("L", stats.get("losses", "0"))
                pts = stats.get("P", stats.get("points", "0"))
                gd = stats.get("GD", stats.get("goalDifference", "0"))
                lines.append(f"  {i+1}. {team_name}  {pts}分 ({w}勝{d}平{l}敗) 淨勝球{gd}")
            else:
                w = stats.get("W", stats.get("wins", "0"))
                l = stats.get("L", stats.get("losses", "0"))
                pct = stats.get("PCT", stats.get("winPercent", ""))
                gb = stats.get("GB", stats.get("gamesBehind", ""))
                if pct:
                    lines.append(f"  {i+1}. {team_name}  {w}勝{l}敗 (勝率{pct}) GB:{gb}")
                else:
                    lines.append(f"  {i+1}. {team_name}  {w}勝{l}敗")
    
    return "\n".join(lines)


if __name__ == "__main__":
    # 測試
    events = get_today_events()
    for key, data in events.items():
        print(f"\n{'='*50}")
        print(f"{data['info']['emoji']} {data['info']['name']}")
        for e in data["events"]:
            print(f"  {e['short_name']} | {e['status_detail']}")
            if e['home']:
                print(f"    主: {e['home']['name']} {e['home']['score']} ({e['home']['record']})")
            if e['away']:
                print(f"    客: {e['away']['name']} {e['away']['score']} ({e['away']['record']})")
