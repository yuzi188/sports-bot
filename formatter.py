"""
Telegram 訊息格式化模組 - 所有隊名一律自動翻譯為中文
"""

from datetime import datetime
import pytz
from config import TIMEZONE, SPORTS
from team_search import translate_team_name

tz = pytz.timezone(TIMEZONE)


def cn(name: str) -> str:
    """翻譯隊名為中文的快捷函數"""
    return translate_team_name(name)


def format_time(iso_date: str) -> str:
    """將 ISO 時間轉換為台灣時間"""
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        local = dt.astimezone(tz)
        return local.strftime("%H:%M")
    except:
        return ""


def format_date_header() -> str:
    """格式化日期標題"""
    now = datetime.now(tz)
    weekdays = ["一", "二", "三", "四", "五", "六", "日"]
    wd = weekdays[now.weekday()]
    return f"📅 {now.strftime('%Y/%m/%d')} 星期{wd}"


def format_scoreboard_message(events_by_league: dict, max_events_per_league: int = 8) -> str:
    """格式化比分板訊息（隊名全中文）"""
    sep = "═" * 24
    dash = "─" * 20
    lines = []
    lines.append(sep)
    lines.append(f"🏟 {format_date_header()}")
    lines.append(sep)

    sorted_leagues = sorted(
        events_by_league.items(),
        key=lambda x: x[1]["info"]["priority"]
    )

    for key, data in sorted_leagues:
        info = data["info"]
        events = data["events"]

        lines.append(f"\n{info['emoji']} {info['name']}")
        lines.append(dash)

        shown = events[:max_events_per_league]
        for e in shown:
            time_str = format_time(e["date"])
            home = e.get("home", {})
            away = e.get("away", {})

            if not home or not away:
                continue

            home_name = cn(home.get('short', home.get('name', '')))
            away_name = cn(away.get('short', away.get('name', '')))

            if e["state"] == "post":
                lines.append(f"✅ {away_name} {away.get('score', '0')} - {home.get('score', '0')} {home_name}")
                lines.append(f"   {e.get('status_detail', '終')}")
            elif e["state"] == "in":
                lines.append(f"🔴 {away_name} {away.get('score', '0')} - {home.get('score', '0')} {home_name}")
                lines.append(f"   ⏱ {e.get('status_detail', '進行中')}")
            else:
                lines.append(f"⏰ {time_str}  {away_name} vs {home_name}")

        if len(events) > max_events_per_league:
            lines.append(f"   ...及其他 {len(events) - max_events_per_league} 場比賽")

    lines.append(f"\n{sep}")
    lines.append("📡 世界體育數據室")
    lines.append("🤖 數據即時更新")

    return "\n".join(lines)


def format_preview_message(ai_preview: str) -> str:
    """格式化每日預覽訊息"""
    sep = "═" * 24
    lines = [
        sep,
        f"📋 今日賽事預覽",
        format_date_header(),
        sep,
        "",
        ai_preview,
        "",
        sep,
        "📡 世界體育數據室",
        "💼 商務合作：https://t.me/OFA168Abe1",
        "🔔 開啟通知不錯過精彩賽事",
    ]
    return "\n".join(lines)


def format_analysis_message(match_data: dict, league_info: dict, analysis: str) -> str:
    """格式化單場分析訊息（隊名全中文）"""
    home = match_data.get("home", {})
    away = match_data.get("away", {})
    odds = match_data.get("odds", {})
    sep = "═" * 24
    dash = "─" * 20

    home_name = cn(home.get('name', ''))
    away_name = cn(away.get('name', ''))

    lines = [sep, f"{league_info['emoji']} {league_info['name']}", sep, ""]

    if match_data["state"] == "post":
        lines.append(f"⚡ {away_name} {away.get('score', '0')} - {home.get('score', '0')} {home_name}")
        lines.append(f"📍 {match_data.get('venue', '')}")
        lines.append(f"📊 {match_data.get('status_detail', '')}")
    else:
        time_str = format_time(match_data["date"])
        lines.append(f"⏰ 開賽時間：{time_str}")
        lines.append(f"📍 {match_data.get('venue', '')}")
        lines.append("")
        lines.append(f"🏠 主隊：{home_name} ({home.get('record', '')})")
        lines.append(f"✈️ 客隊：{away_name} ({away.get('record', '')})")
        if odds.get("details"):
            lines.append("")
            lines.append(f"💰 盤口：{odds['details']}")
            if odds.get("overUnder"):
                lines.append(f"📏 大小分：{odds['overUnder']}")

    lines.extend(["", dash, "🔍 專業分析", dash, "", analysis, "", sep, "📡 世界體育數據室", "💼 商務合作：https://t.me/OFA168Abe1", "⚠️ 分析僅供參考"])
    return "\n".join(lines)


def format_review_message(ai_review: str) -> str:
    """格式化賽後復盤訊息"""
    sep = "═" * 24
    lines = [
        sep,
        "📝 今日賽後復盤",
        format_date_header(),
        sep,
        "",
        ai_review,
        "",
        sep,
        "📡 世界體育數據室",
        "💼 商務合作：https://t.me/OFA168Abe1",
        "🌙 明日見",
    ]
    return "\n".join(lines)


def format_standings_message(sport: str, league_code: str, league_info: dict, standings_text: str) -> str:
    """格式化排名訊息"""
    sep = "═" * 24
    lines = [
        sep,
        f"{league_info['emoji']} {league_info['name']} 排名",
        format_date_header(),
        sep,
        "",
        standings_text,
        "",
        sep,
        "📡 世界體育數據室",
    ]
    return "\n".join(lines)


def build_events_summary(events_by_league: dict) -> str:
    """建立賽事摘要文字（供 AI 分析用，隊名全中文）"""
    lines = []
    for key, data in events_by_league.items():
        info = data["info"]
        events = data["events"]
        lines.append(f"\n{info['name']}:")
        for e in events:
            home = e.get("home", {})
            away = e.get("away", {})
            if not home or not away:
                continue
            time_str = format_time(e["date"])
            home_name = cn(home.get('name', ''))
            away_name = cn(away.get('name', ''))
            if e["state"] == "post":
                lines.append(f"  [{e.get('status_detail', '終')}] {away_name} {away.get('score', '0')} - {home.get('score', '0')} {home_name}")
            elif e["state"] == "in":
                lines.append(f"  [進行中 {e.get('status_detail', '')}] {away_name} {away.get('score', '0')} - {home.get('score', '0')} {home_name}")
            else:
                odds = e.get("odds", {})
                odds_str = f" | 盤口:{odds.get('details', '')}" if odds.get("details") else ""
                lines.append(f"  [{time_str}] {away_name} ({away.get('record', '')}) vs {home_name} ({home.get('record', '')}){odds_str}")
    return "\n".join(lines)


def select_focus_matches(events_by_league: dict, max_matches: int = 5) -> list:
    """選出焦點比賽（用於深度分析）"""
    all_matches = []
    for key, data in events_by_league.items():
        info = data["info"]
        for e in data["events"]:
            home = e.get("home", {})
            away = e.get("away", {})
            if not home or not away:
                continue
            all_matches.append({
                "match": e,
                "league_info": info,
                "sport": data["sport"],
                "league": data["league"],
                "priority": info["priority"],
            })
    all_matches.sort(key=lambda x: x["priority"])
    return all_matches[:max_matches]
