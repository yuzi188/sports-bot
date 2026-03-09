"""
三種運動 AI 分析模組 V1 - 足球 / 棒球 / 籃球
靈感來源：playsport.cc 的勝率統計、焦點比賽、爆冷指數呈現方式

統一分析格式（每種運動皆相同）：
  1. 今日焦點比賽
  2. 勝率預測
  3. 爆冷可能

作者：sports-bot 自動整合
"""
import os
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

# ── 延遲初始化 OpenAI Client ──
_client = None

def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY 環境變數未設定")
        _client = OpenAI(api_key=api_key)
    return _client


# ══════════════════════════════════════════════
#  內部通用分析函數
# ══════════════════════════════════════════════

def _analyze(sport_label: str, sport_emoji: str, matches: str) -> str:
    """
    通用 AI 分析函數，供三種運動共用。

    Args:
        sport_label: 運動名稱（如「足球」「棒球」「籃球」）
        sport_emoji:  對應 emoji（如 ⚽ ⚾ 🏀）
        matches:      賽事資訊文字（來自 ESPN API 或手動輸入）

    Returns:
        AI 分析結果文字
    """
    if not matches or not matches.strip():
        return f"{sport_emoji} 今日暫無 {sport_label} 賽事資訊可供分析。"

    prompt = f"""你是一位專業的{sport_label}數據分析師，風格參考台灣運動彩券分析平台（playsport.cc）。

以下是今日{sport_label}賽事資訊：

{matches}

請依照以下格式提供分析（繁體中文，加入適當 emoji，總字數 300~500 字）：

{sport_emoji} 【今日焦點比賽】
挑出 1~3 場最值得關注的比賽，說明為何值得關注（隊伍狀態、歷史對決、積分差距等）。

📊 【勝率預測】
針對焦點比賽，分別給出主隊/客隊勝率百分比，並附上簡短理由（戰績、主客場優勢、近期狀態）。
格式範例：主隊 60% vs 客隊 40%

❄️ 【爆冷可能】
分析今日是否有潛在爆冷場次（弱隊有機會擊敗強隊的比賽），說明爆冷的條件與機率。
若無明顯爆冷場次，請說明理由。

---
注意：
- 勝率預測基於數據與近況，請保持客觀
- 爆冷指數參考：低（<20%）/ 中（20-40%）/ 高（>40%）
- 不要捏造數據，若資訊不足請如實說明"""

    try:
        resp = _get_client().chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"你是專業的{sport_label}分析師，擅長用繁體中文撰寫精準、易讀的賽事分析。"
                        "你的分析風格參考台灣運動彩券平台，客觀、有數據支撐，並帶有適度的預測觀點。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=700,
            temperature=0.7,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"{sport_label} AI 分析錯誤: {e}", exc_info=True)
        return f"老闆您好，{sport_label} AI 分析功能暫時無法使用。如需協助請聯繫客服 @yu_888yu"


# ══════════════════════════════════════════════
#  三種運動公開 API
# ══════════════════════════════════════════════

def analyze_football(matches: str) -> str:
    """
    足球賽事 AI 分析
    格式：今日焦點比賽 / 勝率預測 / 爆冷可能

    Args:
        matches: 足球賽事文字（每行一場，例如 "⚽ [英超] ⏰ 21:00 曼城 vs 利物浦"）
    """
    return _analyze("足球", "⚽", matches)


def analyze_baseball(matches: str) -> str:
    """
    棒球賽事 AI 分析
    格式：今日焦點比賽 / 勝率預測 / 爆冷可能

    Args:
        matches: 棒球賽事文字（每行一場，例如 "⚾ [MLB] ⏰ 08:05 洋基 vs 紅襪"）
    """
    return _analyze("棒球", "⚾", matches)


def analyze_basketball(matches: str) -> str:
    """
    籃球賽事 AI 分析
    格式：今日焦點比賽 / 勝率預測 / 爆冷可能

    Args:
        matches: 籃球賽事文字（每行一場，例如 "🏀 [NBA] ⏰ 10:30 湖人 vs 勇士"）
    """
    return _analyze("籃球", "🏀", matches)


def analyze_all_sports(football_matches: str, baseball_matches: str, basketball_matches: str) -> str:
    """
    三種運動綜合 AI 分析（每日總覽用）

    Returns:
        三段分析合併的完整文字
    """
    results = []

    if football_matches and football_matches.strip():
        results.append(analyze_football(football_matches))

    if baseball_matches and baseball_matches.strip():
        results.append(analyze_baseball(baseball_matches))

    if basketball_matches and basketball_matches.strip():
        results.append(analyze_basketball(basketball_matches))

    if not results:
        return "今日暫無足球、棒球、籃球賽事資訊可供分析。"

    return "\n\n" + ("─" * 28) + "\n\n".join(results)


# ══════════════════════════════════════════════
#  勝率統計面板（靈感來自 playsport.cc）
# ══════════════════════════════════════════════

def generate_win_rate_panel(sport: str, records: list[dict]) -> str:
    """
    生成勝率統計面板，格式參考 playsport.cc 的戰績總覽。

    Args:
        sport:   運動名稱
        records: 戰績列表，每筆包含 wins/losses/league 等欄位
                 範例：[{"league": "英超", "wins": 5, "losses": 3, "pushes": 0}]

    Returns:
        格式化的勝率面板文字
    """
    if not records:
        return f"📊 {sport} 暫無戰績資料"

    sport_emoji = {"足球": "⚽", "棒球": "⚾", "籃球": "🏀"}.get(sport, "🏆")
    lines = [f"{sport_emoji} 【{sport} 勝率統計面板】", ""]
    lines.append(f"{'聯盟':<12} {'勝':>4} {'負':>4} {'勝率':>7}")
    lines.append("─" * 32)

    for r in records:
        league = r.get("league", "未知")
        wins = r.get("wins", 0)
        losses = r.get("losses", 0)
        total = wins + losses
        rate = f"{wins / total * 100:.0f}%" if total > 0 else "N/A"
        # 高勝率標記（參考 playsport.cc 的「近期殺手」概念）
        hot_tag = " 🔥" if total > 0 and wins / total >= 0.6 else ""
        lines.append(f"{league:<12} {wins:>4} {losses:>4} {rate:>7}{hot_tag}")

    lines.append("")
    lines.append("🔥 = 近期勝率 ≥ 60%（高手殺手指標）")
    return "\n".join(lines)


# ══════════════════════════════════════════════
#  測試入口
# ══════════════════════════════════════════════

if __name__ == "__main__":
    test_football = """⚽ [英超] ⏰ 21:00 曼城 vs 利物浦
⚽ [西甲] ⏰ 22:15 巴薩 vs 皇馬
⚽ [歐冠] ⏰ 03:00 拜仁 vs 多特"""

    test_baseball = """⚾ [MLB] ⏰ 08:05 洋基 vs 紅襪
⚾ [MLB] ⏰ 10:10 道奇 vs 巨人"""

    test_basketball = """🏀 [NBA] ⏰ 09:30 湖人 vs 勇士
🏀 [NBA] ⏰ 12:00 塞爾提克 vs 熱火"""

    print("=== 足球分析 ===")
    print(analyze_football(test_football))
    print("\n=== 棒球分析 ===")
    print(analyze_baseball(test_baseball))
    print("\n=== 籃球分析 ===")
    print(analyze_basketball(test_basketball))
