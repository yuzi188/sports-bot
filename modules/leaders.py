"""
排行榜模組 - 使用 ESPN 免費 Core API
足球射手榜、MLB 全壘打榜、NBA 得分榜
"""

import requests
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CORE_API = "https://sports.core.api.espn.com/v2/sports"


def _fetch_leaders(sport: str, league: str, season: int, category_abbr: str, top_n: int = 10) -> list:
    """
    從 ESPN Core API 取得排行榜
    回傳: [{"name": ..., "team": ..., "value": ...}, ...]
    """
    url = f"{CORE_API}/{sport}/leagues/{league}/seasons/{season}/types/2/leaders"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return []
        data = resp.json()
        categories = data.get("categories", [])

        target_cat = None
        for cat in categories:
            if cat.get("abbreviation") == category_abbr:
                target_cat = cat
                break

        if not target_cat and categories:
            target_cat = categories[0]

        if not target_cat:
            return []

        leaders = target_cat.get("leaders", [])[:top_n]
        results = []

        for leader in leaders:
            # 取得球員資訊（需要 follow $ref）
            ath_ref = leader.get("athlete", {}).get("$ref", "")
            if ath_ref:
                ath_url = ath_ref.replace("http://", "https://")
                try:
                    ath_resp = requests.get(ath_url, timeout=5)
                    ath_data = ath_resp.json()
                    name = ath_data.get("displayName", "")
                    # 取得隊伍
                    team_ref = ath_data.get("team", {}).get("$ref", "")
                    team_name = ""
                    if team_ref:
                        try:
                            team_url = team_ref.replace("http://", "https://")
                            team_resp = requests.get(team_url, timeout=5)
                            team_data = team_resp.json()
                            team_name = team_data.get("abbreviation", "")
                        except:
                            pass

                    value = leader.get("displayValue", str(leader.get("value", "")))
                    results.append({
                        "name": name,
                        "team": team_name,
                        "value": value,
                    })
                except:
                    continue

        return results

    except Exception as e:
        return []


def get_mlb_hr_leaders(top_n: int = 10) -> str:
    """取得 MLB 全壘打排行榜（當季）"""
    # 嘗試 2025 賽季，如果沒有就用 2024
    leaders = _fetch_leaders("baseball", "mlb", 2025, "HR", top_n)
    season = "2025"
    if not leaders:
        leaders = _fetch_leaders("baseball", "mlb", 2024, "HR", top_n)
        season = "2024"

    if not leaders:
        return "⚾ MLB 全壘打排行榜暫時無法取得"

    lines = [f"⚾ MLB {season} 全壘打排行 Top {len(leaders)}", "─" * 20]
    for i, l in enumerate(leaders, 1):
        team_str = f" ({l['team']})" if l['team'] else ""
        # 從 displayValue 中提取 HR 數字
        value = l['value']
        if 'HR' in value:
            # 格式如 "179-541, 53 HR, ..."
            parts = value.split(',')
            for p in parts:
                if 'HR' in p:
                    value = p.strip()
                    break
        lines.append(f"{i}. {l['name']}{team_str} - {value}")

    return "\n".join(lines)


def get_nba_scoring_leaders(top_n: int = 10) -> str:
    """取得 NBA 得分排行榜（當季）"""
    leaders = _fetch_leaders("basketball", "nba", 2025, "PTS", top_n)
    season = "2024-25"
    if not leaders:
        leaders = _fetch_leaders("basketball", "nba", 2024, "PTS", top_n)
        season = "2023-24"

    if not leaders:
        return "🏀 NBA 得分排行榜暫時無法取得"

    lines = [f"🏀 NBA {season} 得分排行 Top {len(leaders)}", "─" * 20]
    for i, l in enumerate(leaders, 1):
        team_str = f" ({l['team']})" if l['team'] else ""
        lines.append(f"{i}. {l['name']}{team_str} - {l['value']} PPG")

    return "\n".join(lines)


def get_football_scorers(league: str = "eng.1", top_n: int = 10) -> str:
    """取得足球射手榜"""
    league_names = {
        "eng.1": "英超", "esp.1": "西甲", "ger.1": "德甲",
        "ita.1": "意甲", "fra.1": "法甲",
    }
    label = league_names.get(league, league)

    # 足球射手榜用不同端點
    url = f"{CORE_API}/soccer/leagues/{league}/seasons/2024/types/1/leaders"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return f"⚽ {label}射手榜暫時無法取得"

        data = resp.json()
        categories = data.get("categories", [])

        # 找進球類別
        target = None
        for cat in categories:
            abbr = cat.get("abbreviation", "").upper()
            name = cat.get("name", "").lower()
            if abbr in ("G", "GLS", "GOALS") or "goal" in name:
                target = cat
                break
        if not target and categories:
            target = categories[0]

        if not target:
            return f"⚽ {label}射手榜暫時無法取得"

        leaders = target.get("leaders", [])[:top_n]
        results = []

        for leader in leaders:
            ath_ref = leader.get("athlete", {}).get("$ref", "")
            if ath_ref:
                try:
                    ath_url = ath_ref.replace("http://", "https://")
                    ath_data = requests.get(ath_url, timeout=5).json()
                    name = ath_data.get("displayName", "")
                    value = leader.get("displayValue", str(leader.get("value", "")))
                    results.append({"name": name, "value": value})
                except:
                    continue

        if not results:
            return f"⚽ {label}射手榜暫時無法取得"

        lines = [f"⚽ {label} 射手榜 Top {len(results)}", "─" * 20]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r['name']} - {r['value']} 球")

        return "\n".join(lines)

    except Exception as e:
        return f"⚽ {label}射手榜暫時無法取得"


if __name__ == "__main__":
    print(get_mlb_hr_leaders(5))
    print()
    print(get_nba_scoring_leaders(5))
    print()
    print(get_football_scorers("eng.1", 5))
