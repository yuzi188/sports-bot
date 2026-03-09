"""
智能搜尋引擎 v2 - 修復版
流程：輸入 → 運動類型識別 → 隊名匹配（精確優先，模糊需過濾通用詞）→ 聯盟判斷 → API查詢

V2 修復：
  1. 加入通用詞黑名單（_QUERY_STOP_WORDS）：「比賽」「今日」等不被模糊匹配為隊名
  2. 提高模糊匹配門檻（score_cutoff: 50 → 65）：減少誤匹配
  3. WBC 關鍵字識別優先於隊名匹配
  4. 聯盟名稱（WBC/MLB/NBA/NHL/NFL）不參與隊名模糊匹配
"""

import re
import os
from rapidfuzz import process, fuzz
from openai import OpenAI
from team_db import (
    TEAM_DATABASE, ALIAS_INDEX, EN_TO_CN,
    LEAGUE_TO_ENDPOINT, ALL_CN_ALIASES, ALL_EN_ALIASES,
)

# OpenAI client（用於 AI 語意解析和翻譯）
_client = None

def _get_client():
    global _client
    if _client is None:
        _client = OpenAI()
    return _client

# 運動類型關鍵字（從長到短排序匹配）
SPORT_KEYWORDS = {
    # WBC 最高優先（防止被誤判為 NHL）
    "世界棒球經典賽": "wbc",
    "棒球經典賽": "wbc",
    "世界棒球": "wbc",
    "經典賽": "wbc",
    "wbc": "wbc",
    # 足球
    "足球": "soccer", "英超": "soccer", "西甲": "soccer",
    "德甲": "soccer", "意甲": "soccer", "法甲": "soccer",
    "歐冠": "soccer", "歐霸": "soccer",
    "soccer": "soccer", "football": "soccer",
    # 棒球
    "棒球": "baseball", "mlb": "baseball",
    "美國職棒": "baseball", "職棒": "baseball", "baseball": "baseball",
    # 籃球
    "籃球": "basketball", "nba": "basketball",
    "美國職籃": "basketball", "職籃": "basketball", "basketball": "basketball",
    # 冰球
    "冰球": "hockey", "nhl": "hockey", "hockey": "hockey",
    "冰上曲棍球": "hockey",
    # 美式足球
    "美式足球": "football_us", "nfl": "football_us", "橄欖球": "football_us",
}

# sport_filter → ESPN 端點列表
SPORT_ENDPOINTS = {
    "soccer": [("soccer", "all", "⚽")],
    "baseball": [("baseball", "mlb", "⚾"), ("baseball", "world-baseball-classic", "⚾")],
    "basketball": [("basketball", "nba", "🏀")],
    "hockey": [("hockey", "nhl", "🏒")],
    "football_us": [("football", "nfl", "🏈")],
    "wbc": [("baseball", "world-baseball-classic", "⚾")],
}

ALL_ENDPOINTS = [
    ("soccer", "all", "⚽"),
    ("baseball", "mlb", "⚾"),
    ("baseball", "world-baseball-classic", "⚾"),
    ("basketball", "nba", "🏀"),
    ("hockey", "nhl", "🏒"),
    ("football", "nfl", "🏈"),
]

# ===== 通用詞黑名單 =====
# 這些詞不應被模糊匹配到隊名
# 例如：「比賽」→ 比爾（Bills）、「今日」→ 日本（Japan）
_QUERY_STOP_WORDS = {
    # 時間詞
    "今日", "今天", "明天", "昨天", "本週", "這週", "上週", "最近", "近期",
    "今晚", "明晚", "今早", "今午",
    # 查詢動詞
    "比賽", "賽事", "查詢", "查看", "搜尋", "搜索",
    "進行", "進行中", "直播", "即時", "最新",
    # 分析詞
    "分析", "預測", "勝率", "比分", "結果", "成績", "狀況", "情況",
    "怎樣", "如何", "怎麼", "什麼", "哪些", "有哪", "有什麼",
    # 賽程詞
    "賽程", "下場", "下一場", "接下來", "之後", "未來", "下週",
    "先發", "投手", "球員", "陣容", "名單",
    # 聯盟名稱（不是隊名）
    "wbc", "mlb", "nba", "nhl", "nfl",
    "英超", "西甲", "德甲", "意甲", "法甲", "歐冠", "歐霸",
    # 通用詞
    "世界", "國際", "全球", "所有", "全部",
    "hot", "live", "today", "score", "game", "games",
    # 中文通用詞
    "熱門", "焦點", "重點", "精彩",
}


def smart_parse(query: str) -> dict:
    """
    智能解析使用者查詢
    回傳：
    {
        "original": 原始查詢,
        "teams": [{"en_name": ..., "cn_name": ..., "league": ..., "confidence": ...}, ...],
        "sport_filter": str or None,
        "is_sport_only": bool,
        "endpoints": [(sport, league, emoji), ...],  # 要查詢的 API 端點
    }
    """
    text = query.strip()

    # Step 1: 檢查運動類型關鍵字（從長到短匹配，WBC 優先）
    sport_filter = None
    is_sport_only = False
    remaining = text

    for kw in sorted(SPORT_KEYWORDS.keys(), key=len, reverse=True):
        if kw.lower() in text.lower():
            sport_filter = SPORT_KEYWORDS[kw]
            remaining = re.sub(re.escape(kw), '', text, flags=re.IGNORECASE).strip()
            # 移除剩餘的通用詞後，判斷是否純運動查詢
            remaining_clean = _remove_stop_words(remaining)
            if not remaining_clean:
                is_sport_only = True
            break

    # Step 2: 隊名匹配（精確 + 模糊）
    teams = []
    if not is_sport_only:
        teams = match_teams(remaining)

    # Step 3: 自動判斷聯盟 → 決定要查哪些端點
    endpoints = determine_endpoints(teams, sport_filter)

    return {
        "original": text,
        "teams": teams,
        "sport_filter": sport_filter,
        "is_sport_only": is_sport_only,
        "endpoints": endpoints,
    }


def _remove_stop_words(text: str) -> str:
    """移除通用詞後回傳剩餘有意義的文字"""
    parts = re.split(r'\s+', text.strip())
    meaningful = [p for p in parts if p and p.lower() not in _QUERY_STOP_WORDS]
    return " ".join(meaningful)


def match_teams(text: str) -> list:
    """
    從文字中匹配隊名
    優先精確匹配，找不到再模糊匹配
    V2 修復：模糊匹配前過濾通用詞，提高門檻
    """
    teams = []
    remaining = text

    # Step A: 精確匹配（從長到短）
    sorted_aliases = sorted(ALIAS_INDEX.keys(), key=len, reverse=True)
    for alias in sorted_aliases:
        if len(alias) < 2:
            continue
        # 跳過聯盟名稱本身（不是隊名）
        if alias.lower() in {"wbc", "mlb", "nba", "nhl", "nfl"}:
            continue
        if alias in remaining.lower():
            info = ALIAS_INDEX[alias]
            # 避免重複
            if not any(t["en_name"] == info["en_name"] for t in teams):
                teams.append({
                    "en_name": info["en_name"],
                    "cn_name": info["cn_name"],
                    "league": info["league"],
                    "confidence": 100,
                    "matched_by": "exact",
                })
            # 從 remaining 中移除已匹配的部分
            idx = remaining.lower().find(alias)
            remaining = remaining[:idx] + remaining[idx + len(alias):]
            remaining = remaining.strip()

    # Step B: 如果精確匹配沒找到，嘗試模糊匹配
    if not teams and remaining.strip():
        # 分割剩餘文字
        parts = re.split(r'\s+|vs\.?|VS\.?|對|和|v\s', remaining)
        parts = [p.strip() for p in parts if p.strip() and len(p.strip()) >= 2]
        # ★ 過濾通用詞，防止「比賽」→ 比爾、「今日」→ 日本
        parts = [p for p in parts if p.lower() not in _QUERY_STOP_WORDS]

        for part in parts:
            # 判斷是中文還是英文
            is_chinese = any('\u4e00' <= c <= '\u9fff' for c in part)

            if is_chinese:
                candidates = ALL_CN_ALIASES
                # 中文短詞用字元級匹配
                if len(part) <= 3:
                    char_match = _chinese_char_match(part, candidates)
                    if char_match:
                        info = ALIAS_INDEX.get(char_match.lower())
                        if info and not any(t["en_name"] == info["en_name"] for t in teams):
                            teams.append({
                                "en_name": info["en_name"],
                                "cn_name": info["cn_name"],
                                "league": info["league"],
                                "confidence": 75,
                                "matched_by": "fuzzy",
                            })
                        continue
            else:
                candidates = ALL_EN_ALIASES

            if not candidates:
                continue

            # ★ 提高模糊匹配門檻（65 → 減少誤匹配）
            result = process.extractOne(
                part,
                candidates,
                scorer=fuzz.WRatio,
                score_cutoff=65,
            )

            if result:
                matched_alias, score, _ = result
                info = ALIAS_INDEX.get(matched_alias.lower())
                if info and not any(t["en_name"] == info["en_name"] for t in teams):
                    teams.append({
                        "en_name": info["en_name"],
                        "cn_name": info["cn_name"],
                        "league": info["league"],
                        "confidence": score,
                        "matched_by": "fuzzy",
                    })

    return teams


def _chinese_char_match(query: str, candidates: list) -> str:
    """
    中文字元級匹配：
    對於2-3字的中文，如果有一個字不同但其他字相同，就算匹配
    例如：洋機 → 洋基（1字不同）
    V2 修復：排除通用詞候選項
    """
    # 通用詞不參與字元匹配
    if query in _QUERY_STOP_WORDS:
        return None

    best_match = None
    best_overlap = 0

    for candidate in candidates:
        # 候選項也不能是通用詞
        if candidate in _QUERY_STOP_WORDS:
            continue
        if abs(len(candidate) - len(query)) > 1:
            continue
        # 計算共同字元數
        common = sum(1 for c in query if c in candidate)
        min_len = min(len(query), len(candidate))
        if min_len == 0:
            continue
        overlap_ratio = common / min_len
        # 至少 60% 字元相同（提高門檻）
        if overlap_ratio >= 0.6 and common > best_overlap:
            best_overlap = common
            best_match = candidate

    return best_match


def determine_endpoints(teams: list, sport_filter: str = None) -> list:
    """
    根據匹配到的隊伍和運動類型，決定要查詢哪些 API 端點
    """
    # 如果有明確的運動類型
    if sport_filter:
        return SPORT_ENDPOINTS.get(sport_filter, ALL_ENDPOINTS)

    # 如果有匹配到隊伍，根據隊伍的聯盟決定
    if teams:
        leagues = set(t["league"] for t in teams)
        endpoints = []
        seen = set()

        for league in leagues:
            # 聯盟 → ESPN 端點
            if league in LEAGUE_TO_ENDPOINT:
                ep = LEAGUE_TO_ENDPOINT[league]
                key = f"{ep[0]}/{ep[1]}"
                if key not in seen:
                    seen.add(key)
                    emoji_map = {
                        "baseball": "⚾", "basketball": "🏀",
                        "hockey": "🏒", "football": "🏈", "soccer": "⚽",
                    }
                    emoji = emoji_map.get(ep[0], "🏟")
                    endpoints.append((ep[0], ep[1], emoji))
            else:
                # 國家隊可能同時出現在足球和 WBC
                if league in ("WBC", "足球"):
                    for ep_sport, ep_league, ep_emoji in ALL_ENDPOINTS:
                        key = f"{ep_sport}/{ep_league}"
                        if key not in seen:
                            if league == "WBC" and ep_league in ("world-baseball-classic", "all"):
                                seen.add(key)
                                endpoints.append((ep_sport, ep_league, ep_emoji))
                            elif league == "足球" and ep_league == "all":
                                seen.add(key)
                                endpoints.append((ep_sport, ep_league, ep_emoji))

        if endpoints:
            return endpoints

    # 預設搜尋所有端點
    return ALL_ENDPOINTS


def _team_in_event(team: dict, event_team_names: set) -> bool:
    """
    檢查單支隊伍是否在賽事中（供 match_event_smart 呼叫）
    支援英文全名、暱稱、部分匹配
    """
    en_name = team["en_name"].lower()
    # 方法 1: 英文全名完全匹配
    if en_name in event_team_names:
        return True
    # 方法 2: 英文全名的最後一個詞（暱稱）匹配 shortDisplayName
    short_name = en_name.split()[-1] if " " in en_name else en_name
    if len(short_name) > 3 and short_name in event_team_names:
        return True
    # 方法 3: event 的名稱包含隊伍全名（或反之）
    for etn in event_team_names:
        if len(en_name) > 4 and en_name in etn:
            return True
        if len(etn) > 4 and etn in en_name:
            return True
    return False


def match_event_smart(event: dict, teams: list) -> bool:
    """
    智能匹配：用 displayName 和 shortDisplayName 匹配

    V2.1 修復：
    - 查詢 1 支隊伍時：賽事包含該隊即匹配（OR 邏輯）
    - 查詢 2 支隊伍時：賽事必須同時包含兩隊（AND 邏輯）
      → 防止「韓國 + 澳洲」匹配到「日本 vs 澳洲」
    """
    competitions = event.get("competitions", [])
    if not competitions:
        return False
    competitors = competitions[0].get("competitors", [])

    # 收集賽事中每支隊伍的名稱
    event_team_names = set()
    for c in competitors:
        team = c.get("team", {})
        for field in ["displayName", "shortDisplayName", "name"]:
            val = team.get(field, "")
            if val:
                event_team_names.add(val.lower())

    if len(teams) >= 2:
        # ★ 雙隊查詢：AND 邏輯 — 賽事必須同時包含所有查詢隊伍
        return all(_team_in_event(t, event_team_names) for t in teams)
    else:
        # 單隊查詢：OR 邏輯 — 賽事包含任一查詢隊伍即匹配
        return any(_team_in_event(t, event_team_names) for t in teams)


def translate_name(en_display_name: str) -> str:
    """英文隊名翻譯成中文（查表 + AI fallback）"""
    cn = EN_TO_CN.get(en_display_name.lower())
    if cn:
        return cn

    # 嘗試部分匹配
    en_lower = en_display_name.lower()
    for en_full, cn_name in EN_TO_CN.items():
        if en_lower in en_full or en_full in en_lower:
            return cn_name

    # 模糊匹配
    all_en_keys = list(EN_TO_CN.keys())
    if all_en_keys:
        result = process.extractOne(en_lower, all_en_keys, scorer=fuzz.ratio, score_cutoff=70)
        if result:
            return EN_TO_CN[result[0]]

    # AI fallback
    try:
        resp = _get_client().chat.completions.create(
            model="gpt-4.1-nano",
            messages=[{
                "role": "user",
                "content": f"將以下體育隊名翻譯成繁體中文，只回覆中文名稱：{en_display_name}"
            }],
            max_tokens=20,
            temperature=0,
        )
        cn_name = resp.choices[0].message.content.strip()
        if cn_name and len(cn_name) < 20:
            EN_TO_CN[en_display_name.lower()] = cn_name
            return cn_name
    except:
        pass

    return en_display_name
