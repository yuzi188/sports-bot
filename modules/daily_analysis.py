"""
AI 賽事分析自動推送模組 V1.0

功能：
  - 每日自動從 ESPN API 抓取今日焦點賽事
  - 透過 GPT 生成賽事分析（含勝率、爆冷指數）
  - 自動推送到 Telegram 頻道
  - 自動發起投票預測
"""

import logging
import os
import json
import requests
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"

# 支援的運動和聯賽
LEAGUES = {
    "NBA": ("basketball", "nba"),
    "MLB": ("baseball", "mlb"),
    "英超": ("soccer", "eng.1"),
    "西甲": ("soccer", "esp.1"),
    "歐冠": ("soccer", "uefa.champions"),
    "NFL": ("football", "nfl"),
    "NHL": ("hockey", "nhl"),
}


def fetch_today_games(sport: str, league: str) -> list[dict]:
    """從 ESPN API 抓取今日賽事"""
    try:
        url = f"{ESPN_BASE}/{sport}/{league}/scoreboard"
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        games = []
        for event in data.get("events", []):
            competition = event.get("competitions", [{}])[0]
            competitors = competition.get("competitors", [])
            if len(competitors) < 2:
                continue

            home = competitors[0]
            away = competitors[1]
            status = competition.get("status", {})
            status_type = status.get("type", {}).get("name", "STATUS_SCHEDULED")

            game = {
                "id": event.get("id", ""),
                "name": event.get("name", ""),
                "home_team": home.get("team", {}).get("displayName", ""),
                "home_abbr": home.get("team", {}).get("abbreviation", ""),
                "home_score": home.get("score", "0"),
                "home_record": home.get("records", [{}])[0].get("summary", "") if home.get("records") else "",
                "away_team": away.get("team", {}).get("displayName", ""),
                "away_abbr": away.get("team", {}).get("abbreviation", ""),
                "away_score": away.get("score", "0"),
                "away_record": away.get("records", [{}])[0].get("summary", "") if away.get("records") else "",
                "status": status_type,
                "status_detail": status.get("type", {}).get("shortDetail", ""),
                "date": event.get("date", ""),
                "broadcast": competition.get("broadcasts", [{}])[0].get("names", [""])[0] if competition.get("broadcasts") else "",
            }
            games.append(game)

        return games
    except Exception as e:
        logger.error(f"[賽事分析] 抓取 {sport}/{league} 失敗: {e}")
        return []


def fetch_all_today_games() -> dict[str, list[dict]]:
    """抓取所有聯賽的今日賽事"""
    all_games = {}
    for league_name, (sport, league) in LEAGUES.items():
        games = fetch_today_games(sport, league)
        if games:
            all_games[league_name] = games
            logger.info(f"[賽事分析] {league_name}: {len(games)} 場比賽")
    return all_games


def generate_daily_analysis_with_gpt(all_games: dict) -> str:
    """透過 GPT 生成今日焦點賽事分析"""
    try:
        from openai import OpenAI

        api_key = os.environ.get("OPENAI_API_KEY")
        base_url = os.environ.get("OPENAI_BASE_URL")
        if not api_key:
            return _generate_fallback_analysis(all_games)

        client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)

        # 準備賽事資料
        games_text = ""
        for league, games in all_games.items():
            games_text += f"\n【{league}】\n"
            for g in games:
                record_info = ""
                if g["home_record"]:
                    record_info = f" (主{g['home_record']} vs 客{g['away_record']})"
                games_text += f"  {g['away_team']} @ {g['home_team']}{record_info}\n"

        prompt = f"""你是 LA1 體育數據室的 AI 分析師。請根據以下今日賽事，生成一份精彩的「今日焦點賽事分析」推播文章。

今日賽事列表：
{games_text}

要求：
1. 從所有賽事中挑選 3-5 場最值得關注的焦點比賽
2. 每場比賽分析包含：
   - 對戰雙方和聯賽
   - 簡短的近況分析（根據戰績推測）
   - 勝率預測（百分比）
   - 爆冷指數（1-5星，5星最可能爆冷）
3. 格式要求：
   - 使用繁體中文
   - 適當使用 emoji 讓文章生動
   - 最後附上一句鼓勵語
4. 不要提及「ESPN」、「資料來源」等字眼
5. 文章開頭用「🏆 LA1 今日焦點賽事分析」作為標題
6. 文章結尾附上：「📊 更多即時比分 → @LA1111_bot」"""

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            temperature=0.8,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"[賽事分析] GPT 分析生成失敗: {e}")
        return _generate_fallback_analysis(all_games)


def _generate_fallback_analysis(all_games: dict) -> str:
    """GPT 不可用時的備用分析格式"""
    lines = ["🏆 LA1 今日焦點賽事\n"]
    total = 0

    for league, games in all_games.items():
        if not games:
            continue
        lines.append(f"\n{'='*20}")
        lines.append(f"📺 {league}")
        lines.append(f"{'='*20}")

        for g in games[:5]:  # 每聯賽最多5場
            total += 1
            status_icon = "🔴" if g["status"] == "STATUS_IN_PROGRESS" else "⏰"
            record = ""
            if g["home_record"]:
                record = f"\n   📊 主 {g['home_record']} | 客 {g['away_record']}"

            if g["status"] == "STATUS_IN_PROGRESS":
                score = f" ({g['away_score']}-{g['home_score']})"
            elif g["status"] == "STATUS_FINAL":
                score = f" ({g['away_score']}-{g['home_score']}) 已結束"
            else:
                score = ""

            lines.append(f"\n{status_icon} {g['away_team']} @ {g['home_team']}{score}{record}")

    if total == 0:
        return "🏆 LA1 今日賽事\n\n目前暫無賽事資料，請稍後再查詢！"

    lines.append(f"\n\n📊 共 {total} 場比賽")
    lines.append("💬 即時比分查詢 → @LA1111_bot")
    lines.append("📢 訂閱頻道 → @LA11118")

    return "\n".join(lines)


def generate_focus_matches(all_games: dict) -> list[dict]:
    """
    挑選今日焦點比賽（用於自動發起投票）。
    優先選擇有戰績記錄的比賽。
    """
    focus = []
    for league, games in all_games.items():
        for g in games:
            if g["status"] in ("STATUS_SCHEDULED", "STATUS_PRE_EVENT"):
                focus.append({
                    "league": league,
                    "home_team": g["home_team"],
                    "away_team": g["away_team"],
                    "home_record": g["home_record"],
                    "away_record": g["away_record"],
                    "date": g["date"],
                })
    # 按聯賽優先級排序，取前 3 場
    priority = {"歐冠": 0, "NBA": 1, "英超": 2, "MLB": 3, "西甲": 4, "NFL": 5, "NHL": 6}
    focus.sort(key=lambda x: priority.get(x["league"], 99))
    return focus[:3]


def format_prediction_poll_text(match: dict) -> str:
    """格式化投票預測文字"""
    league = match["league"]
    home = match["home_team"]
    away = match["away_team"]

    text = f"🎯 今日預測挑戰\n\n"
    text += f"📺 {league}\n"
    text += f"⚔️ {away} vs {home}\n"

    if match["home_record"] and match["away_record"]:
        text += f"📊 戰績：{away} ({match['away_record']}) vs {home} ({match['home_record']})\n"

    text += f"\n你覺得誰會贏？猜對 +10 積分！"
    return text
