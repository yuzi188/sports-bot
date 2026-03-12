"""
三種運動 AI 分析模組 V2 - 足球 / 棒球 / 籃球
升級版：使用 gemini-2.5-flash 自行搜尋今日最新賽事資訊後進行深度分析

分析內容：
  1. 今日賽程與焦點比賽
  2. 球評分析（隊伍狀態、歷史對決、關鍵數據）
  3. 勝率預測（含百分比與理由）
  4. 預測比分
  5. 爆冷可能性分析

作者：sports-bot V2 升級
"""
import os
import logging
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

# ── 延遲初始化 OpenAI Client ──
_client = None

def _get_client():
    global _client
    if _client is not None:
        return _client
    try:
        from openai import OpenAI
        api_key  = os.environ.get("OPENAI_API_KEY", "")
        base_url = os.environ.get("OPENAI_BASE_URL", "")
        if not api_key:
            logger.error("OPENAI_API_KEY 未設定")
            return None
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        _client = OpenAI(**kwargs)
        return _client
    except Exception as e:
        logger.error(f"OpenAI client 初始化失敗: {e}")
        return None


def _get_today_str() -> tuple[str, str]:
    """回傳今日日期字串（台北時間）"""
    tz = pytz.timezone("Asia/Taipei")
    now = datetime.now(tz)
    date_str = now.strftime("%Y年%m月%d日")
    weekday = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"][now.weekday()]
    return date_str, weekday


# ══════════════════════════════════════════════
#  升級版通用分析函數（gemini-2.5-flash 搜尋 + 分析）
# ══════════════════════════════════════════════

def _analyze_with_search(sport_label: str, sport_emoji: str, matches_hint: str = "") -> str:
    """
    升級版 AI 分析：讓 gemini-2.5-flash 自行搜尋今日最新賽事資訊後進行深度分析。

    Args:
        sport_label:  運動名稱（如「足球」「棒球」「籃球」）
        sport_emoji:  對應 emoji（如 ⚽ ⚾ 🏀）
        matches_hint: 從 ESPN API 取得的賽事資訊（可為空，作為補充參考）

    Returns:
        AI 分析結果文字
    """
    client = _get_client()
    if client is None:
        return f"{sport_emoji} {sport_label}分析功能暫時無法使用，請稍後再試。"

    today, weekday = _get_today_str()

    # 根據運動類型設定搜尋關鍵字
    sport_config = {
        "足球": {
            "leagues": "英超、西甲、德甲、意甲、法甲、歐冠、歐聯",
            "search_hint": "soccer football Premier League La Liga Bundesliga Serie A Ligue 1 Champions League",
            "score_format": "X:X",
        },
        "棒球": {
            "leagues": "MLB（美國職棒大聯盟）、NPB（日本職棒）、CPBL（中華職棒）",
            "search_hint": "MLB baseball NPB CPBL",
            "score_format": "X-X",
        },
        "籃球": {
            "leagues": "NBA、CBA、SBL",
            "search_hint": "NBA basketball",
            "score_format": "XXX-XXX",
        },
    }
    cfg = sport_config.get(sport_label, {"leagues": sport_label, "search_hint": sport_label, "score_format": "X-X"})

    # ESPN 資料補充
    espn_context = ""
    if matches_hint and matches_hint.strip():
        espn_context = f"\n\n【ESPN API 取得的今日賽程參考】\n{matches_hint}\n"

    prompt = f"""今天是 {today}（{weekday}）。

請搜尋今日（{today}）{sport_label}最新賽事資訊，包含 {cfg['leagues']} 的比賽。{espn_context}

請依照以下格式，用繁體中文提供完整的體育分析報告（總字數 400~600 字）：

{sport_emoji} 【今日賽程】
列出今日所有重要比賽（台北時間），格式：時間 客隊 vs 主隊
若今日無正式賽事，請說明原因並提供近期重要賽事預告。

🔍 【球評分析】
針對 1~3 場最值得關注的比賽，分析：
- 兩隊近期狀態（最近 5 場戰績）
- 關鍵球員狀況（傷兵、近期表現）
- 歷史對決紀錄
- 主客場優勢分析

📊 【關鍵數據】
提供具體數據支撐分析，例如：
- 各隊本季勝率、得失分差
- 近期連勝/連敗紀錄
- 特定球員的近期數據

🎯 【預測比分】
針對焦點比賽給出預測比分，格式：
隊名A {cfg['score_format']} 隊名B（主勝率 XX% / 客勝率 XX%）
附上預測理由（50字以內）

❄️ 【爆冷分析】
分析今日是否有潛在爆冷場次：
- 爆冷指數：低(<20%) / 中(20-40%) / 高(>40%)
- 說明爆冷條件與可能性

---
注意：
- 請提供最新、最準確的資訊
- 若資訊不足或無法確認，請如實說明
- 分析僅供參考，請理性投注"""

    try:
        resp = client.chat.completions.create(
            model="gemini-2.5-flash",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"你是一位專業的{sport_label}數據分析師，擁有即時搜尋網路資訊的能力。"
                        f"你能夠搜尋最新的{sport_label}賽事資訊、球隊戰績、球員數據和賠率，"
                        "並以台灣運動彩券分析平台的風格，提供客觀、有數據支撐的賽事分析。"
                        "請使用繁體中文，加入適當的 emoji 讓報告更易讀。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=1200,
            temperature=0.4,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"{sport_label} AI 分析錯誤: {e}", exc_info=True)
        # fallback 到基本分析
        return _analyze_fallback(sport_label, sport_emoji, matches_hint)


def _analyze_fallback(sport_label: str, sport_emoji: str, matches: str) -> str:
    """
    Fallback：使用 gpt-4.1-mini 進行基本分析（不含網路搜尋）
    即使沒有 ESPN 資料，也讓 GPT 根據自身知識分析當前賽季狀況
    """
    client = _get_client()
    if client is None:
        return f"{sport_emoji} {sport_label}分析功能暫時無法使用，請稍後再試。"

    today, weekday = _get_today_str()

    if matches and matches.strip():
        matches_section = f"\n\n以下是今日{sport_label}賽事資訊：\n{matches}"
    else:
        matches_section = f"\n\n（今日 ESPN API 暫無{sport_label}賽事資料，請根據你的知識分析當前賽季最新動態，若目前為季前賽/春訓期間請說明，並預告即將到來的重要賽事）"

    prompt = f"""今天是 {today}（{weekday}）。{matches_section}

請用繁體中文提供分析（300~400字），包含：
1. {sport_emoji} 今日焦點比賽或近期重要賽事
2. 📊 勝率預測（主隊XX% vs 客隊XX%）
3. 🎯 預測比分
4. ❄️ 爆冷可能性

分析僅供參考，請理性投注。"""

    try:
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": f"你是專業的{sport_label}分析師，用繁體中文提供精準的賽事分析。"},
                {"role": "user", "content": prompt},
            ],
            max_tokens=600,
            temperature=0.6,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"{sport_label} fallback 分析錯誤: {e}", exc_info=True)
        return f"{sport_emoji} {sport_label}分析功能暫時無法使用，請稍後再試。如需協助請聯繫客服 @yu_888yu"


# ══════════════════════════════════════════════
#  三種運動公開 API（向下相容舊介面）
# ══════════════════════════════════════════════

def analyze_football(matches: str) -> str:
    """
    足球賽事 AI 分析（升級版：gemini-2.5-flash 搜尋 + 分析）
    Args:
        matches: ESPN API 取得的足球賽事文字（作為補充參考）
    """
    return _analyze_with_search("足球", "⚽", matches)


def analyze_baseball(matches: str) -> str:
    """
    棒球賽事 AI 分析（升級版：gemini-2.5-flash 搜尋 + 分析）
    Args:
        matches: ESPN API 取得的棒球賽事文字（作為補充參考）
    """
    return _analyze_with_search("棒球", "⚾", matches)


def analyze_basketball(matches: str) -> str:
    """
    籃球賽事 AI 分析（升級版：gemini-2.5-flash 搜尋 + 分析）
    Args:
        matches: ESPN API 取得的籃球賽事文字（作為補充參考）
    """
    return _analyze_with_search("籃球", "🏀", matches)


def analyze_all_sports(football_matches: str, baseball_matches: str, basketball_matches: str) -> str:
    """
    三種運動綜合 AI 分析（升級版）
    """
    today, weekday = _get_today_str()
    client = _get_client()
    if client is None:
        return "分析功能暫時無法使用，請稍後再試。"

    # 合併所有賽事資訊
    all_matches = []
    if football_matches and football_matches.strip():
        all_matches.append(f"【足球】\n{football_matches}")
    if baseball_matches and baseball_matches.strip():
        all_matches.append(f"【棒球】\n{baseball_matches}")
    if basketball_matches and basketball_matches.strip():
        all_matches.append(f"【籃球】\n{basketball_matches}")

    espn_context = "\n\n".join(all_matches) if all_matches else ""

    prompt = f"""今天是 {today}（{weekday}）。

請搜尋今日足球、棒球、籃球的最新賽事資訊，提供三種運動的綜合分析報告。

{f'【ESPN API 參考資料】{chr(10)}{espn_context}' if espn_context else ''}

請用繁體中文，依照以下格式提供分析（總字數 500~800 字）：

⚽ 【足球分析】
今日焦點比賽 + 勝率預測 + 預測比分

⚾ 【棒球分析】
今日焦點比賽 + 勝率預測 + 預測比分

🏀 【籃球分析】
今日焦點比賽 + 勝率預測 + 預測比分

🔥 【今日最值得關注】
綜合三種運動，推薦 1~2 場最值得關注的比賽，說明理由。

⚠️ 分析僅供參考，請理性投注"""

    try:
        resp = client.chat.completions.create(
            model="gemini-2.5-flash",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一位全方位的體育數據分析師，擅長足球、棒球、籃球三種運動的賽事分析。"
                        "你能搜尋最新賽事資訊，用繁體中文提供客觀、有數據支撐的分析報告。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=1500,
            temperature=0.4,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"綜合分析錯誤: {e}", exc_info=True)
        # fallback：分別分析
        results = []
        for label, emoji, matches in [
            ("足球", "⚽", football_matches),
            ("棒球", "⚾", baseball_matches),
            ("籃球", "🏀", basketball_matches),
        ]:
            if matches and matches.strip():
                results.append(_analyze_fallback(label, emoji, matches))
        if not results:
            return f"今日（{today}）暫無足球、棒球、籃球賽事資訊可供分析。"
        return ("\n\n" + "─" * 28 + "\n\n").join(results)


# ══════════════════════════════════════════════
#  勝率統計面板（靈感來自 playsport.cc）
# ══════════════════════════════════════════════

def generate_win_rate_panel(sport: str, records: list) -> str:
    """
    生成勝率統計面板，格式參考 playsport.cc 的戰績總覽。
    """
    if not records:
        return f"📊 {sport} 暫無戰績資料"

    sport_emoji = {"足球": "⚽", "棒球": "⚾", "籃球": "🏀"}.get(sport, "🏆")
    lines = [f"{sport_emoji} 【{sport} 勝率統計面板】", ""]
    lines.append(f"{'聯盟':<12} {'勝':>4} {'負':>4} {'勝率':>7}")
    lines.append("─" * 32)

    for r in records:
        league = r.get("league", "未知")
        wins   = r.get("wins", 0)
        losses = r.get("losses", 0)
        total  = wins + losses
        rate   = f"{wins / total * 100:.0f}%" if total > 0 else "N/A"
        hot_tag = " 🔥" if total > 0 and wins / total >= 0.6 else ""
        lines.append(f"{league:<12} {wins:>4} {losses:>4} {rate:>7}{hot_tag}")

    lines.append("")
    lines.append("🔥 = 近期勝率 ≥ 60%（高手殺手指標）")
    return "\n".join(lines)


# ══════════════════════════════════════════════
#  測試入口
# ══════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    sport = sys.argv[1] if len(sys.argv) > 1 else "baseball"
    print(f"=== 測試 {sport} 分析 ===")
    if sport == "football":
        print(analyze_football(""))
    elif sport == "basketball":
        print(analyze_basketball(""))
    else:
        print(analyze_baseball(""))
