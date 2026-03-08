"""
即時比分查詢模組 v6 - 智能搜尋引擎 + 未來賽程查詢 + 即時詳細資料
"""

import requests
from datetime import datetime, timedelta
import pytz
import logging
from config import ESPN_BASE, TIMEZONE
from smart_search import (
    smart_parse, match_event_smart, translate_name,
    ALL_ENDPOINTS, SPORT_ENDPOINTS,
)

tz = pytz.timezone(TIMEZONE)
logger = logging.getLogger(__name__)


def search_live_scores(query: str) -> dict:
    """智能搜尋即時比分"""
    parsed = smart_parse(query)
    teams = parsed["teams"]
    endpoints = parsed["endpoints"]
    is_sport_only = parsed["is_sport_only"]

    if not teams and not is_sport_only:
        return {"parsed": parsed, "events": [], "recent_history": {}}

    matched_events = []

    for sport, league, emoji in endpoints:
        try:
            url = f"{ESPN_BASE}/{sport}/{league}/scoreboard"
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                continue
            data = resp.json()
            events = data.get("events", [])

            if is_sport_only and not teams:
                for event in events:
                    pe = parse_event(event, emoji)
                    if pe:
                        pe["sport"] = sport
                        pe["league"] = league
                        matched_events.append(pe)
            else:
                for event in events:
                    if match_event_smart(event, teams):
                        pe = parse_event(event, emoji)
                        if pe:
                            pe["sport"] = sport
                            pe["league"] = league
                            matched_events.append(pe)
        except:
            continue

    # 近3場歷史比分
    recent_history = {}
    if teams and not is_sport_only:
        recent_history = get_recent_matches(teams, endpoints)

    return {
        "parsed": parsed,
        "events": matched_events,
        "recent_history": recent_history,
    }


def get_upcoming_matches(query: str) -> dict:
    """
    查詢指定隊伍的未來賽程（下一場或接下來幾場）

    搜尋策略：
    1. 先查今日 scoreboard（state=pre 的比賽即為未開始）
    2. 若今日無未來賽程，往後查 7 天
    3. 回傳最多 3 場未來賽事

    Returns:
        dict: {
            "parsed": parsed,
            "upcoming": [event_dict, ...],   # 最多 3 場
            "found": bool
        }
    """
    parsed = smart_parse(query)
    teams = parsed["teams"]
    endpoints = parsed["endpoints"]

    if not teams:
        return {"parsed": parsed, "upcoming": [], "found": False}

    upcoming_events = []
    today = datetime.now(tz)

    # 搜尋今日 + 未來 7 天
    for day_offset in range(0, 8):
        if len(upcoming_events) >= 3:
            break

        date = today + timedelta(days=day_offset)
        date_str = date.strftime("%Y%m%d")

        for sport, league, emoji in endpoints:
            if len(upcoming_events) >= 3:
                break
            try:
                url = f"{ESPN_BASE}/{sport}/{league}/scoreboard?dates={date_str}"
                resp = requests.get(url, timeout=10)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                events = data.get("events", [])

                for event in events:
                    if not match_event_smart(event, teams):
                        continue

                    comps = event.get("competitions", [])
                    if not comps:
                        continue
                    comp = comps[0]
                    status = comp.get("status", {}).get("type", {})
                    state = status.get("state", "")

                    # 只取未開始的比賽
                    if state != "pre":
                        continue

                    pe = parse_event(event, emoji)
                    if pe:
                        # 避免重複
                        is_dup = any(
                            u["home"]["name"] == pe["home"]["name"]
                            and u["away"]["name"] == pe["away"]["name"]
                            and u["date"] == pe["date"]
                            for u in upcoming_events
                        )
                        if not is_dup:
                            upcoming_events.append(pe)

            except Exception as e:
                logger.info(f"upcoming query error: {e}")
                continue

    return {
        "parsed": parsed,
        "upcoming": upcoming_events[:3],
        "found": len(upcoming_events) > 0,
    }


def format_upcoming_response(result: dict) -> str:
    """格式化未來賽程回覆"""
    parsed = result["parsed"]
    upcoming = result["upcoming"]

    team_names = " / ".join(t["cn_name"] for t in parsed["teams"]) if parsed["teams"] else parsed.get("original", "")

    if not result["found"] or not upcoming:
        return (
            f"📅 {team_names} 未來賽程\n\n"
            f"😴 目前查不到 {team_names} 的下一場賽程\n"
            f"可能原因：賽程尚未公布，或本賽季已結束\n\n"
            f"💡 試試直接輸入隊名查詢今日比分"
        )

    sep = "═" * 24
    lines = [sep, f"📅 {team_names} 即將出賽", sep, ""]

    for e in upcoming:
        home = e["home"]
        away = e["away"]
        emoji = e["emoji"]
        pool = e.get("pool", "")
        pool_str = f" ({pool})" if pool else ""

        try:
            dt = datetime.fromisoformat(e["date"].replace("Z", "+00:00"))
            local = dt.astimezone(tz)
            time_str = local.strftime("%m/%d（%a）%H:%M")
        except:
            time_str = "時間待定"

        lines.append(f"{emoji} {away['name']} vs {home['name']}{pool_str}")
        lines.append(f"⏰ {time_str}")
        lines.append("")

    lines.extend([sep, "📡 世界體育數據室"])
    return "\n".join(lines)


def get_recent_matches(teams: list, endpoints: list) -> dict:
    """取得每支隊伍的近3場已結束比賽"""
    history = {}
    today = datetime.now(tz)

    for team in teams:
        cn_name = team["cn_name"]
        team_matches = []

        for sport, league, emoji in endpoints:
            for day_offset in range(0, 8):
                if len(team_matches) >= 3:
                    break
                date = today - timedelta(days=day_offset)
                date_str = date.strftime("%Y%m%d")

                try:
                    url = f"{ESPN_BASE}/{sport}/{league}/scoreboard?dates={date_str}"
                    resp = requests.get(url, timeout=8)
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    events = data.get("events", [])

                    for event in events:
                        if match_event_smart(event, [team]):
                            comps = event.get("competitions", [])
                            if not comps:
                                continue
                            comp = comps[0]
                            status = comp.get("status", {}).get("type", {})
                            if status.get("state") != "post":
                                continue

                            competitors = comp.get("competitors", [])
                            home_data = away_data = None
                            for c in competitors:
                                t = c.get("team", {})
                                en_name = t.get("displayName", "")
                                td = {
                                    "name": translate_name(en_name),
                                    "score": c.get("score", "0"),
                                }
                                if c.get("homeAway") == "home":
                                    home_data = td
                                else:
                                    away_data = td

                            if home_data and away_data:
                                event_date = event.get("date", "")
                                try:
                                    dt = datetime.fromisoformat(event_date.replace("Z", "+00:00"))
                                    local_dt = dt.astimezone(tz)
                                    date_display = local_dt.strftime("%m/%d")
                                except:
                                    date_display = ""

                                match_record = {
                                    "date": date_display,
                                    "away": away_data["name"],
                                    "home": home_data["name"],
                                    "away_score": away_data["score"],
                                    "home_score": home_data["score"],
                                    "emoji": emoji,
                                }

                                is_dup = any(
                                    m["away"] == match_record["away"]
                                    and m["home"] == match_record["home"]
                                    and m["date"] == match_record["date"]
                                    for m in team_matches
                                )
                                if not is_dup:
                                    team_matches.append(match_record)
                except:
                    continue

            if len(team_matches) >= 3:
                break

        history[cn_name] = team_matches[:3]

    return history


def parse_event(event: dict, emoji: str = "🏟") -> dict:
    """解析賽事，隊名自動翻譯為中文"""
    competitions = event.get("competitions", [])
    if not competitions:
        return None
    competition = competitions[0]
    competitors = competition.get("competitors", [])
    if not competitors:
        return None
    status = competition.get("status", {})

    # WBC Pool 資訊
    notes = competition.get("notes", [])
    pool_info = ""
    if notes:
        headline = notes[0].get("headline", "")
        if "Pool" in headline:
            pool_info = headline.split("Pool")[-1].strip()
            pool_info = f"Pool {pool_info}"

    home = away = None
    for c in competitors:
        team = c.get("team", {})
        en_name = team.get("displayName", "")
        team_data = {
            "name": translate_name(en_name),
            "score": c.get("score", "0"),
        }
        if c.get("homeAway") == "home":
            home = team_data
        else:
            away = team_data

    if not home or not away:
        return None

    state = status.get("type", {}).get("state", "pre")
    status_detail = status.get("type", {}).get("detail", "")

    return {
        "emoji": emoji,
        "state": state,
        "status_detail": status_detail,
        "home": home,
        "away": away,
        "date": event.get("date", ""),
        "pool": pool_info,
        "game_id": event.get("id", ""),
        "sport": "",   # 由呼叫方填入
        "league": "",  # 由呼叫方填入
    }


def format_response(result: dict) -> str:
    """格式化完整回覆"""
    parsed = result["parsed"]
    events = result["events"]
    recent_history = result.get("recent_history", {})

    if not events and not recent_history:
        return format_no_result(parsed)

    # 排序：進行中 > 未開始 > 已結束
    state_order = {"in": 0, "pre": 1, "post": 2}
    events.sort(key=lambda e: state_order.get(e["state"], 3))

    # 標題
    if parsed["teams"]:
        team_names = " / ".join(t["cn_name"] for t in parsed["teams"])
        header = f"🔍 查詢：{team_names}"
        # 如果有模糊匹配，顯示提示
        fuzzy_teams = [t for t in parsed["teams"] if t.get("matched_by") == "fuzzy"]
        if fuzzy_teams:
            hints = ", ".join(f"{t['cn_name']}({t['confidence']}%)" for t in fuzzy_teams)
            header += f"\n💡 模糊匹配：{hints}"
    else:
        header = f"🔍 查詢：{parsed['original']}"

    lines = [header, ""]

    MAX_SHOW = 20
    show = events[:MAX_SHOW]

    # 判斷是否有進行中的比賽需要詳細資料
    has_live = any(e["state"] == "in" for e in show)
    # 只有一場進行中比賽時才自動帶入詳細資料（避免多場比賽時太長）
    single_live = sum(1 for e in show if e["state"] == "in") == 1

    for e in show:
        use_details = (e["state"] == "in" and single_live)
        lines.append(format_single_event(e, with_details=use_details))
        lines.append("")

    if len(events) > MAX_SHOW:
        lines.append(f"...另有 {len(events) - MAX_SHOW} 場未顯示")
        lines.append("")

    # 近3場歷史比分
    if recent_history:
        for team_cn, matches in recent_history.items():
            if matches:
                lines.append(f"📋 {team_cn} 近期戰績：")
                for m in matches:
                    lines.append(
                        f"  {m['emoji']} {m['date']} {m['away']} {m['away_score']} - {m['home_score']} {m['home']}"
                    )
                lines.append("")

    lines.append(f"📊 共找到 {len(events)} 場相關比賽")
    lines.append("📡 世界體育數據室")

    return "\n".join(lines)


def format_single_event(event: dict, with_details: bool = False) -> str:
    """
    格式化單場比賽

    Args:
        event: parse_event 回傳的賽事字典
        with_details: 若為 True 且比賽進行中，自動呼叫 summary API 附加詳細資料
    """
    home = event["home"]
    away = event["away"]
    emoji = event["emoji"]
    pool = event.get("pool", "")
    pool_str = f" ({pool})" if pool else ""

    if event["state"] == "in":
        base = (
            f"{emoji} {away['name']} vs {home['name']}{pool_str}\n"
            f"🔴 進行中 {event['status_detail']}\n"
            f"{away['name']} {away['score']} - {home['score']} {home['name']}"
        )
        # 進行中：嘗試附加詳細資料
        if with_details:
            game_id = event.get("game_id", "")
            sport = event.get("sport", "")
            league = event.get("league", "")
            if game_id and sport and league:
                try:
                    from modules.game_details import get_live_game_details, format_game_details
                    details = get_live_game_details(game_id, sport, league)
                    if details.get("success"):
                        detail_text = format_game_details(details)
                        return detail_text
                except Exception as e:
                    logger.warning(f"get_live_game_details 失敗: {e}")
        return base
    elif event["state"] == "post":
        return (
            f"{emoji} {away['name']} vs {home['name']}{pool_str}\n"
            f"📊 比賽結束\n"
            f"{away['name']} {away['score']} - {home['score']} {home['name']}"
        )
    else:
        try:
            dt = datetime.fromisoformat(event["date"].replace("Z", "+00:00"))
            local = dt.astimezone(tz)
            time_str = local.strftime("%m/%d %H:%M")
        except:
            time_str = ""
        return (
            f"{emoji} {away['name']} vs {home['name']}{pool_str}\n"
            f"⏰ {time_str}"
        )


def format_no_result(parsed: dict) -> str:
    """格式化無結果"""
    if parsed["teams"]:
        team_names = " / ".join(t["cn_name"] for t in parsed["teams"])
        return (
            f"🔍 查詢：{team_names}\n\n"
            f"😴 今日沒有找到相關比賽\n\n"
            "💡 試試：\n"
            "• 隊名查詢：洋基 紅襪\n"
            "• 運動查詢：棒球、WBC、NBA"
        )
    return (
        f"🔍 找不到「{parsed['original']}」的比賽\n\n"
        "💡 試試：\n"
        "• 隊名查詢：洋基 紅襪\n"
        "• 運動查詢：棒球、WBC、NBA"
    )



