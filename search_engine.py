"""
搜尋引擎 v3 - 精確隊名匹配
核心原則：
1. 中文隊名必須完整匹配（「洋基」匹配「洋基」，不會匹配「洋」或「基」）
2. 匹配 ESPN 的 displayName 和 shortDisplayName（不用 abbreviation 和 location）
3. 匹配方式：隊名完全相等，或隊伍暱稱（如 Yankees）完全等於 shortDisplayName
"""

import re
from team_search import TEAM_ALIASES, SPORT_KEYWORDS


def parse_query(text: str) -> dict:
    """
    解析使用者查詢
    回傳：
      - team_groups: list of dict，每個 group 是一支隊伍的中文名和英文別名
      - sport_filter: str or None
      - is_sport_only: bool（純運動類型查詢如「棒球」）
    """
    # 移除查詢前綴
    prefixes = [
        "我想知道", "查詢", "查比分", "即時比分",
        "目前比分", "現在比分", "比數", "戰況", "查",
        "score", "live", "結果", "怎麼樣了", "比分",
    ]
    cleaned = text.strip()
    for p in prefixes:
        if cleaned.startswith(p):
            cleaned = cleaned[len(p):].strip()

    # 檢查運動類型關鍵字
    sport_filter = None
    is_sport_only = False
    remaining = cleaned

    for sport_kw, sport_type in sorted(SPORT_KEYWORDS.items(), key=lambda x: len(x[0]), reverse=True):
        if sport_kw.lower() in cleaned.lower():
            sport_filter = sport_type
            remaining = re.sub(re.escape(sport_kw), '', cleaned, flags=re.IGNORECASE).strip()
            if not remaining:
                is_sport_only = True
            break

    # 從 remaining 中提取隊名（貪婪匹配中文隊名，從長到短）
    team_groups = []
    temp = remaining
    sorted_cn = sorted(TEAM_ALIASES.keys(), key=len, reverse=True)
    for cn_name in sorted_cn:
        if cn_name in temp:
            en_names = TEAM_ALIASES[cn_name]
            # 只保留長度 > 3 的英文名稱（排除縮寫如 BOS, NYY）
            full_names = [n for n in en_names if len(n) > 3]
            team_groups.append({
                "cn": cn_name,
                "en_names_full": [n.lower() for n in full_names],
            })
            temp = temp.replace(cn_name, " ", 1).strip()

    # 如果沒有匹配到中文隊名，嘗試英文匹配
    if not team_groups and temp.strip():
        parts = re.split(r'\s+vs\.?\s+|\s+VS\.?\s+|\s+對\s+|\s+和\s+|\s+v\s+|\s+', temp)
        parts = [p.strip() for p in parts if p.strip()]
        for part in parts:
            part_lower = part.lower()
            found = False
            for cn_name, en_names in TEAM_ALIASES.items():
                for en in en_names:
                    if len(en) > 3 and en.lower() == part_lower:
                        full_names = [n for n in en_names if len(n) > 3]
                        team_groups.append({
                            "cn": cn_name,
                            "en_names_full": [n.lower() for n in full_names],
                        })
                        found = True
                        break
                if found:
                    break
            if not found and len(part) >= 2:
                team_groups.append({
                    "cn": part,
                    "en_names_full": [part.lower()],
                })

    return {
        "original": text,
        "team_groups": team_groups,
        "sport_filter": sport_filter,
        "is_sport_only": is_sport_only,
    }


def match_event_strict(event: dict, team_groups: list) -> bool:
    """
    嚴格匹配：只用 displayName 和 shortDisplayName 匹配
    不用 abbreviation（避免 BOS 同時匹配紅襪和棕熊）
    不用 location（避免 New York 匹配所有紐約隊伍）
    """
    competitions = event.get("competitions", [])
    if not competitions:
        return False
    competitors = competitions[0].get("competitors", [])

    # 收集賽事中每支隊伍的名稱（只用 displayName 和 shortDisplayName）
    event_teams = []
    for c in competitors:
        team = c.get("team", {})
        names = set()
        for field in ["displayName", "shortDisplayName", "name"]:
            val = team.get(field, "")
            if val:
                names.add(val.lower())
        event_teams.append(names)

    # 對每個 team_group 檢查是否匹配
    for group in team_groups:
        en_names = group["en_names_full"]
        matched = False
        for en_name in en_names:
            for team_names in event_teams:
                for tn in team_names:
                    # 完全相等
                    if en_name == tn:
                        matched = True
                        break
                    # 包含匹配：en_name 必須是 tn 的子字串
                    # 例如 "yankees" in "new york yankees"
                    # 但不能反過來（"new york yankees" in "new york rangers" → False）
                    if len(en_name) > 4:
                        if en_name in tn:
                            matched = True
                            break
                    # 反向：tn 是 en_name 的子字串
                    # 例如 tn="yankees", en_name="new york yankees"
                    if len(tn) > 4:
                        if tn in en_name:
                            matched = True
                            break
                if matched:
                    break
            if matched:
                break
        if matched:
            return True

    return False
