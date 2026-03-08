"""
即時比賽詳細資料模組 V1
使用 ESPN summary API 抓取棒球、籃球、足球的即時詳細資訊

API 端點：
https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/summary?event={game_id}
"""

import requests
import logging
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

# 投手位置 ID
PITCHER_POSITION_IDS = {"1"}  # ESPN position id=1 為投手

# 足球事件類型對應
SOCCER_EVENT_TYPES = {
    "goal": "⚽ 進球",
    "penalty---scored": "⚽ 點球進球",
    "penalty---missed": "❌ 點球未進",
    "own-goal": "🔴 烏龍球",
    "substitution": "🔄 換人",
    "yellow-card": "🟨 黃牌",
    "red-card": "🟥 紅牌",
    "yellow-red-card": "🟨🟥 第二黃牌",
    "halftime": "⏸ 中場休息",
    "start-2nd-half": "▶️ 下半場開始",
    "end-regular-time": "🏁 比賽結束",
}

# 半場對應
SOCCER_PERIOD_NAMES = {
    1: "上半場",
    2: "下半場",
    3: "加時上半場",
    4: "加時下半場",
    5: "互射點球",
}

# NBA 節次
NBA_PERIOD_NAMES = {
    1: "第一節",
    2: "第二節",
    3: "第三節",
    4: "第四節",
    5: "加時",
    6: "第二加時",
}


def get_live_game_details(game_id: str, sport: str, league: str) -> dict:
    """
    從 ESPN summary API 取得比賽詳細資料

    Args:
        game_id: ESPN 比賽 ID
        sport: 運動類型（baseball / basketball / soccer / football）
        league: 聯賽（mlb / world-baseball-classic / nba / eng.1 等）

    Returns:
        dict: {
            "success": bool,
            "sport": sport,
            "league": league,
            "state": "pre" | "in" | "post",
            "data": {...}  # 各運動的詳細資料
        }
    """
    url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/summary?event={game_id}"
    try:
        resp = requests.get(url, timeout=12)
        if resp.status_code != 200:
            logger.warning(f"summary API 回傳 {resp.status_code}: {url}")
            return {"success": False, "error": f"API 回傳 {resp.status_code}"}
        raw = resp.json()
    except Exception as e:
        logger.error(f"summary API 請求失敗: {e}")
        return {"success": False, "error": str(e)}

    # 取得比賽狀態
    header = raw.get("header", {})
    competitions = header.get("competitions", [{}])
    comp = competitions[0] if competitions else {}
    status = comp.get("status", {}).get("type", {})
    state = status.get("state", "pre")
    status_detail = status.get("detail", "")

    # 取得隊伍基本資訊
    competitors = comp.get("competitors", [])
    teams_info = {}
    for c in competitors:
        home_away = c.get("homeAway", "")
        team = c.get("team", {})
        teams_info[home_away] = {
            "name": team.get("displayName", ""),
            "abbrev": team.get("abbreviation", ""),
            "score": c.get("score", "0"),
            # ESPN 籃球用 displayValue，足球用 value
            "linescores": [
                ls.get("displayValue", "") or ls.get("value", "")
                for ls in c.get("linescores", [])
            ],
        }

    result = {
        "success": True,
        "sport": sport,
        "league": league,
        "state": state,
        "status_detail": status_detail,
        "teams": teams_info,
        "data": {},
    }

    # 根據運動類型解析詳細資料
    if sport == "baseball":
        result["data"] = _parse_baseball(raw, state)
    elif sport == "basketball":
        result["data"] = _parse_basketball(raw, state, comp)
    elif sport == "soccer":
        result["data"] = _parse_soccer(raw, state)

    return result


# ===== 棒球解析 =====

def _parse_baseball(raw: dict, state: str) -> dict:
    """解析棒球詳細資料（投手、打者、局數）"""
    result = {
        "pitchers": {},    # {home/away: [pitcher_dict]}
        "batters": {},     # {home/away: [batter_dict]}
        "situation": {},   # 即時局面（進行中才有）
        "inning_scores": {},  # 各局得分
    }

    # boxscore players（投手 / 打者統計）
    bs = raw.get("boxscore", {})
    players = bs.get("players", [])

    for team_data in players:
        team = team_data.get("team", {})
        home_away = team_data.get("homeAway", "")
        team_name = team.get("displayName", "")

        pitchers = []
        batters = []

        for stat_group in team_data.get("statistics", []):
            stat_type = stat_group.get("type", "")
            keys = stat_group.get("keys", [])
            labels = stat_group.get("labels", [])
            athletes = stat_group.get("athletes", [])

            for a in athletes:
                athlete = a.get("athlete", {})
                name = athlete.get("displayName", "")
                is_starter = a.get("starter", False)
                stats = a.get("stats", [])
                stat_dict = dict(zip(keys, stats))

                if stat_type == "pitching":
                    pitcher = {
                        "name": name,
                        "starter": is_starter,
                        "ip": stat_dict.get("fullInnings.partInnings", stat_dict.get("innings", "")),
                        "hits": stat_dict.get("hits", ""),
                        "runs": stat_dict.get("runs", ""),
                        "er": stat_dict.get("earnedRuns", ""),
                        "bb": stat_dict.get("walks", ""),
                        "k": stat_dict.get("strikeouts", ""),
                        "team": team_name,
                    }
                    pitchers.append(pitcher)

                elif stat_type == "batting":
                    batter = {
                        "name": name,
                        "starter": is_starter,
                        "hab": stat_dict.get("hits-atBats", ""),
                        "r": stat_dict.get("runs", ""),
                        "rbi": stat_dict.get("RBIs", ""),
                        "hr": stat_dict.get("homeRuns", ""),
                        "team": team_name,
                    }
                    batters.append(batter)

        result["pitchers"][home_away] = pitchers
        result["batters"][home_away] = batters

    # situation（進行中比賽的即時局面）
    situation = raw.get("situation", {})
    if situation:
        result["situation"] = {
            "inning": situation.get("period", {}).get("number", ""),
            "inning_half": situation.get("period", {}).get("type", ""),
            "outs": situation.get("outs", ""),
            "balls": situation.get("balls", ""),
            "strikes": situation.get("strikes", ""),
            "on_first": bool(situation.get("onFirst")),
            "on_second": bool(situation.get("onSecond")),
            "on_third": bool(situation.get("onThird")),
            "batter": situation.get("batter", {}).get("athlete", {}).get("displayName", ""),
            "pitcher": situation.get("pitcher", {}).get("athlete", {}).get("displayName", ""),
        }

    # 各局得分（linescores from header）
    result["inning_scores"] = {}

    return result


# ===== 籃球解析 =====

def _parse_basketball(raw: dict, state: str, comp: dict) -> dict:
    """解析籃球詳細資料（節次、球員得分）"""
    result = {
        "top_scorers": {},   # {home/away: [player_dict]}
        "team_stats": {},    # {home/away: {stat_name: value}}
        "period": "",        # 目前節次
        "clock": "",         # 剩餘時間
    }

    # 節次和時鐘
    status = comp.get("status", {})
    result["period"] = status.get("period", 0)
    result["clock"] = status.get("displayClock", "")

    # boxscore players（球員統計）
    bs = raw.get("boxscore", {})
    players = bs.get("players", [])

    for team_data in players:
        home_away = team_data.get("homeAway", "")
        team_name = team_data.get("team", {}).get("displayName", "")
        top_players = []

        for stat_group in team_data.get("statistics", []):
            keys = stat_group.get("keys", [])
            athletes = stat_group.get("athletes", [])

            for a in athletes:
                athlete = a.get("athlete", {})
                name = athlete.get("displayName", "")
                stats = a.get("stats", [])
                stat_dict = dict(zip(keys, stats))

                pts = stat_dict.get("points", "0")
                try:
                    pts_int = int(pts)
                except (ValueError, TypeError):
                    pts_int = 0

                if pts_int > 0:
                    top_players.append({
                        "name": name,
                        "points": pts_int,
                        "rebounds": stat_dict.get("rebounds", ""),
                        "assists": stat_dict.get("assists", ""),
                        "minutes": stat_dict.get("minutes", ""),
                        "fg": stat_dict.get("fieldGoalsMade-fieldGoalsAttempted", ""),
                        "team": team_name,
                    })

        # 依得分排序，取前 5 名
        top_players.sort(key=lambda x: x["points"], reverse=True)
        result["top_scorers"][home_away] = top_players[:5]

    # team stats
    teams = bs.get("teams", [])
    for t in teams:
        home_away = t.get("homeAway", "")
        stats = t.get("statistics", [])
        stat_dict = {}
        for s in stats:
            stat_dict[s.get("name", "")] = s.get("displayValue", "")
        result["team_stats"][home_away] = stat_dict

    return result


# ===== 足球解析 =====

def _parse_soccer(raw: dict, state: str) -> dict:
    """解析足球詳細資料（進球、換人、黃紅牌）"""
    result = {
        "goals": [],         # 進球列表
        "substitutions": [], # 換人列表
        "cards": [],         # 黃紅牌列表
        "key_events": [],    # 所有重要事件（進球+換人+牌）
        "period": 1,
        "clock": "",
    }

    key_events = raw.get("keyEvents", [])

    for event in key_events:
        event_type = event.get("type", {})
        type_key = event_type.get("type", "")
        type_text = event_type.get("text", "")
        clock = event.get("clock", {}).get("displayValue", "")
        period = event.get("period", {}).get("number", 1)
        text = event.get("text", "")
        short_text = event.get("shortText", "")
        scoring = event.get("scoringPlay", False)

        # 取得球員資訊
        # ESPN 足球事件用 participants 存放球員，第一人為進球者，第二人為助攻
        participants = event.get("participants", [])
        athletes = event.get("athletes", [])  # fallback
        scorer = ""
        assist = ""
        if participants:
            if len(participants) >= 1:
                scorer = participants[0].get("athlete", {}).get("displayName", "")
            if len(participants) >= 2:
                assist = participants[1].get("athlete", {}).get("displayName", "")
        else:
            for a in athletes:
                a_type = a.get("type", "")
                a_name = a.get("athlete", {}).get("displayName", "")
                if a_type in ("scorer", "passer", ""):
                    if not scorer:
                        scorer = a_name
                elif a_type == "assist":
                    assist = a_name

        # 取得隊伍
        team_obj = event.get("team", {})
        team_name = team_obj.get("displayName", "")

        entry = {
            "type": type_key,
            "type_label": SOCCER_EVENT_TYPES.get(type_key, type_text),
            "clock": clock,
            "period": period,
            "text": text,
            "short_text": short_text,
            "team": team_name,
            "scorer": scorer,
            "assist": assist,
            "scoring": scoring,
        }

        if scoring or type_key in ("goal", "penalty---scored", "own-goal"):
            result["goals"].append(entry)
            result["key_events"].append(entry)
        elif type_key == "substitution":
            result["substitutions"].append(entry)
            result["key_events"].append(entry)
        elif type_key in ("yellow-card", "red-card", "yellow-red-card"):
            result["cards"].append(entry)
            result["key_events"].append(entry)
        elif type_key in ("halftime", "start-2nd-half", "end-regular-time"):
            result["key_events"].append(entry)

    # 目前節次（取最後一個 period）
    if key_events:
        last = key_events[-1]
        result["period"] = last.get("period", {}).get("number", 1)
        result["clock"] = last.get("clock", {}).get("displayValue", "")

    return result


# ===== 格式化輸出 =====

def format_game_details(details: dict) -> str:
    """
    將 get_live_game_details 的結果格式化為 Telegram 訊息

    Args:
        details: get_live_game_details 的回傳值

    Returns:
        格式化後的字串
    """
    if not details.get("success"):
        error = details.get("error", "未知錯誤")
        return f"❌ ESPN 目前尚未提供此比賽的詳細即時資料\n（{error}）"

    sport = details["sport"]
    state = details["state"]
    teams = details.get("teams", {})
    status_detail = details.get("status_detail", "")
    data = details.get("data", {})

    home = teams.get("home", {})
    away = teams.get("away", {})
    home_name = home.get("name", "主隊")
    away_name = away.get("name", "客隊")
    home_score = home.get("score", "0")
    away_score = away.get("score", "0")

    sep = "═" * 24
    lines = [sep]

    if sport == "baseball":
        lines.extend(_format_baseball(details, home_name, away_name, home_score, away_score, status_detail, state))
    elif sport == "basketball":
        lines.extend(_format_basketball(details, home_name, away_name, home_score, away_score, status_detail, state))
    elif sport == "soccer":
        lines.extend(_format_soccer(details, home_name, away_name, home_score, away_score, status_detail, state))
    else:
        lines.append(f"⚾🏀⚽ {away_name} vs {home_name}")
        lines.append(f"比分：{away_score} - {home_score}")
        lines.append(f"狀態：{status_detail}")

    lines.extend([sep, "📡 世界體育數據室"])
    return "\n".join(lines)


def _format_baseball(details, home_name, away_name, home_score, away_score, status_detail, state):
    """格式化棒球詳細資料"""
    lines = []
    data = details["data"]

    # 標題
    state_emoji = "🔴" if state == "in" else ("✅" if state == "post" else "⏰")
    lines.append(f"⚾ {away_name} vs {home_name}")
    lines.append(f"{state_emoji} {status_detail}")
    lines.append(f"比分：{away_name} {away_score} - {home_score} {home_name}")
    lines.append("")

    # 即時局面（進行中）
    situation = data.get("situation", {})
    if situation and state == "in":
        inning = situation.get("inning", "")
        half = situation.get("inning_half", "")
        half_zh = "上" if "Top" in str(half) else "下"
        outs = situation.get("outs", "")
        balls = situation.get("balls", "")
        strikes = situation.get("strikes", "")
        batter = situation.get("batter", "")
        pitcher = situation.get("pitcher", "")

        lines.append(f"📍 目前：第 {inning} 局{half_zh}半")
        lines.append(f"   {outs} 出局 | {balls} 壞 {strikes} 好")

        # 壘包
        bases = []
        if situation.get("on_first"):
            bases.append("一壘")
        if situation.get("on_second"):
            bases.append("二壘")
        if situation.get("on_third"):
            bases.append("三壘")
        if bases:
            lines.append(f"   壘上：{' '.join(bases)}")
        else:
            lines.append(f"   壘上：無人")

        if batter:
            lines.append(f"   打者：{batter}")
        if pitcher:
            lines.append(f"   投手：{pitcher}")
        lines.append("")

    # 投手資料
    pitchers_home = data.get("pitchers", {}).get("home", [])
    pitchers_away = data.get("pitchers", {}).get("away", [])

    if pitchers_away:
        lines.append(f"🏟 {away_name} 投手陣容：")
        for p in pitchers_away:
            role = "先發" if p["starter"] else "後援"
            ip = p.get("ip", "")
            k = p.get("k", "")
            er = p.get("er", "")
            bb = p.get("bb", "")
            lines.append(f"  {'🔵' if p['starter'] else '⚪'} {p['name']}（{role}）IP:{ip} K:{k} ER:{er} BB:{bb}")
        lines.append("")

    if pitchers_home:
        lines.append(f"🏠 {home_name} 投手陣容：")
        for p in pitchers_home:
            role = "先發" if p["starter"] else "後援"
            ip = p.get("ip", "")
            k = p.get("k", "")
            er = p.get("er", "")
            bb = p.get("bb", "")
            lines.append(f"  {'🔵' if p['starter'] else '⚪'} {p['name']}（{role}）IP:{ip} K:{k} ER:{er} BB:{bb}")
        lines.append("")

    # 打者亮點（RBI 或 HR > 0）
    highlight_batters = []
    for ha in ("away", "home"):
        team_name = away_name if ha == "away" else home_name
        for b in data.get("batters", {}).get(ha, []):
            hr = b.get("hr", "0")
            rbi = b.get("rbi", "0")
            try:
                if int(hr) > 0 or int(rbi) >= 2:
                    highlight_batters.append((team_name, b))
            except (ValueError, TypeError):
                pass

    if highlight_batters:
        lines.append("💥 打擊亮點：")
        for team_name, b in highlight_batters[:6]:
            lines.append(f"  {b['name']}（{team_name}）{b['hab']} HR:{b['hr']} RBI:{b['rbi']}")
        lines.append("")

    if not situation and not pitchers_home and not pitchers_away:
        lines.append("ℹ️ ESPN 目前尚未提供此比賽的詳細資料")

    return lines


def _format_basketball(details, home_name, away_name, home_score, away_score, status_detail, state):
    """格式化籃球詳細資料"""
    lines = []
    data = details["data"]
    teams = details.get("teams", {})

    # 標題
    state_emoji = "🔴" if state == "in" else ("✅" if state == "post" else "⏰")
    lines.append(f"🏀 {away_name} vs {home_name}")
    lines.append(f"{state_emoji} {status_detail}")

    # 各節得分
    home_linescores = teams.get("home", {}).get("linescores", [])
    away_linescores = teams.get("away", {}).get("linescores", [])

    if home_linescores or away_linescores:
        max_periods = max(len(home_linescores), len(away_linescores))
        period_labels = [NBA_PERIOD_NAMES.get(i + 1, f"Q{i+1}") for i in range(max_periods)]
        header_row = "   " + "  ".join(f"{p[:2]:>3}" for p in period_labels) + "  合計"
        away_row = f"{away_name[:6]:6}" + "  ".join(f"{str(s):>3}" for s in away_linescores) + f"  {away_score:>4}"
        home_row = f"{home_name[:6]:6}" + "  ".join(f"{str(s):>3}" for s in home_linescores) + f"  {home_score:>4}"
        lines.append(f"```")
        lines.append(header_row)
        lines.append(away_row)
        lines.append(home_row)
        lines.append(f"```")
    else:
        lines.append(f"比分：{away_name} {away_score} - {home_score} {home_name}")

    lines.append("")

    # 得分領袖
    for ha, team_name in [("away", away_name), ("home", home_name)]:
        scorers = data.get("top_scorers", {}).get(ha, [])
        if scorers:
            lines.append(f"🌟 {team_name} 得分領袖：")
            for p in scorers[:3]:
                lines.append(
                    f"  {p['name']} {p['points']}分 "
                    f"{p['rebounds']}籃 {p['assists']}助 "
                    f"({p['fg']})"
                )
            lines.append("")

    if not data.get("top_scorers"):
        lines.append("ℹ️ ESPN 目前尚未提供此比賽的詳細球員資料")

    return lines


def _format_soccer(details, home_name, away_name, home_score, away_score, status_detail, state):
    """格式化足球詳細資料"""
    lines = []
    data = details["data"]

    # 標題
    state_emoji = "🔴" if state == "in" else ("✅" if state == "post" else "⏰")
    period = data.get("period", 1)
    period_name = SOCCER_PERIOD_NAMES.get(period, f"第{period}節")
    clock = data.get("clock", "")

    lines.append(f"⚽ {away_name} vs {home_name}")
    if state == "in":
        lines.append(f"🔴 {period_name} {clock}")
    else:
        lines.append(f"{state_emoji} {status_detail}")
    lines.append(f"比分：{away_name} {away_score} - {home_score} {home_name}")
    lines.append("")

    # 進球記錄
    goals = data.get("goals", [])
    if goals:
        lines.append("⚽ 進球記錄：")
        for g in goals:
            clock_str = f"{g['clock']}" if g["clock"] else ""
            team = g.get("team", "")
            scorer = g.get("scorer", "")
            assist = g.get("assist", "")
            type_label = g.get("type_label", "⚽ 進球")

            if scorer:
                line = f"  {type_label} {clock_str} {scorer}"
                if team:
                    line += f"（{team}）"
                if assist:
                    line += f" 助攻：{assist}"
            else:
                line = f"  {type_label} {clock_str} {g.get('short_text', '')}"
            lines.append(line)
        lines.append("")

    # 換人記錄
    subs = data.get("substitutions", [])
    if subs:
        lines.append("🔄 換人記錄：")
        for s in subs:
            text = s.get("text", "")
            clock_str = s.get("clock", "")
            # 簡化換人文字
            if "replaces" in text:
                lines.append(f"  {clock_str} {text}")
            else:
                lines.append(f"  {clock_str} {s.get('short_text', text)}")
        lines.append("")

    # 黃紅牌
    cards = data.get("cards", [])
    if cards:
        lines.append("🃏 紀律記錄：")
        for c in cards:
            type_label = c.get("type_label", "")
            clock_str = c.get("clock", "")
            short = c.get("short_text", "")
            lines.append(f"  {type_label} {clock_str} {short}")
        lines.append("")

    if not goals and not subs and not cards:
        if state == "in":
            lines.append("ℹ️ 比賽剛開始，暫無重要事件")
        else:
            lines.append("ℹ️ ESPN 目前尚未提供此比賽的詳細資料")

    return lines
