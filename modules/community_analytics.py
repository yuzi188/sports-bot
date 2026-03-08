"""
群體行為學習分析系統 V1
Community Analytics Module

功能：
  1. 熱門度分析   — 統計全體用戶查詢頻率，生成「熱門關注指數」
  2. 群體預測分析 — 大眾預測 vs 實際結果，計算群體預測準確率
  3. 爆冷事件記錄 — 自動偵測並標記爆冷事件（多數人猜錯）
  4. 內容優化引擎 — 根據互動率自動調整推播風格（詳細/簡短/數據型）
  5. 每週洞察報告 — 定期發布「本週玩家趨勢報告」到頻道
  6. /insights    — 即時查看當前趨勢指標

資料庫：共用 data/user_preferences.db
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

_DB_DIR  = Path(__file__).parent.parent / "data"
_DB_PATH = _DB_DIR / "user_preferences.db"

# ── 爆冷判定閾值：大眾投票率超過此比例猜錯才算爆冷 ──
UPSET_THRESHOLD = 0.65   # 65% 以上的人猜錯才算爆冷

# ── 互動風格類型 ──
STYLE_DETAILED = "detailed"
STYLE_BRIEF    = "brief"
STYLE_DATA     = "data"


def _get_conn() -> sqlite3.Connection:
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_community_tables():
    """初始化群體分析所需資料表"""
    with _get_conn() as conn:
        conn.executescript("""
            -- 全體查詢熱門度統計
            CREATE TABLE IF NOT EXISTS community_query_stats (
                query_value     TEXT    NOT NULL,
                query_type      TEXT    NOT NULL,   -- 'team' | 'sport' | 'league'
                sport           TEXT    DEFAULT '',
                total_users     INTEGER DEFAULT 0,  -- 查詢過的不重複用戶數
                total_queries   INTEGER DEFAULT 0,  -- 總查詢次數
                last_queried    TEXT    DEFAULT (datetime('now')),
                PRIMARY KEY (query_value, query_type)
            );

            -- 群體預測準確率統計（每場比賽結算後更新）
            CREATE TABLE IF NOT EXISTS community_prediction_stats (
                poll_id             TEXT    PRIMARY KEY,
                match_desc          TEXT    NOT NULL,
                sport               TEXT    DEFAULT '',
                total_voters        INTEGER DEFAULT 0,
                correct_voters      INTEGER DEFAULT 0,
                wrong_voters        INTEGER DEFAULT 0,
                crowd_accuracy      REAL    DEFAULT 0.0,  -- 群體準確率 %
                majority_option     INTEGER DEFAULT -1,   -- 多數人選的選項
                correct_option      INTEGER DEFAULT -1,   -- 正確選項
                is_upset            INTEGER DEFAULT 0,    -- 是否爆冷
                upset_magnitude     REAL    DEFAULT 0.0,  -- 爆冷程度（多數人猜錯的比例）
                settled_at          TEXT    DEFAULT NULL
            );

            -- 爆冷事件記錄
            CREATE TABLE IF NOT EXISTS upset_events (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                poll_id         TEXT    NOT NULL,
                match_desc      TEXT    NOT NULL,
                sport           TEXT    DEFAULT '',
                majority_option TEXT    NOT NULL,   -- 多數人猜的選項
                correct_option  TEXT    NOT NULL,   -- 實際正確選項
                upset_magnitude REAL    DEFAULT 0.0,
                total_voters    INTEGER DEFAULT 0,
                occurred_at     TEXT    DEFAULT (datetime('now'))
            );

            -- 互動風格效果追蹤
            CREATE TABLE IF NOT EXISTS content_style_metrics (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                style           TEXT    NOT NULL,   -- 'detailed' | 'brief' | 'data'
                sport           TEXT    DEFAULT '',
                message_type    TEXT    DEFAULT '', -- 'analysis' | 'preview' | 'review'
                interaction_count INTEGER DEFAULT 0, -- 收到的後續互動次數（回覆/查詢）
                sent_at         TEXT    DEFAULT (datetime('now'))
            );

            -- 每週洞察報告記錄
            CREATE TABLE IF NOT EXISTS weekly_insights_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                week_start  TEXT    NOT NULL,
                week_end    TEXT    NOT NULL,
                report_text TEXT    NOT NULL,
                sent_at     TEXT    DEFAULT (datetime('now'))
            );

            -- 索引
            CREATE INDEX IF NOT EXISTS idx_community_query_total
                ON community_query_stats(total_queries DESC);
            CREATE INDEX IF NOT EXISTS idx_upset_events_sport
                ON upset_events(sport, occurred_at DESC);
            CREATE INDEX IF NOT EXISTS idx_style_metrics_style
                ON content_style_metrics(style, sent_at DESC);
        """)
    logger.info("群體行為分析資料表已初始化")


# ══════════════════════════════════════════════
#  1. 熱門度分析
# ══════════════════════════════════════════════

def record_community_query(user_id: int, query_value: str, query_type: str, sport: str = ""):
    """
    記錄全體查詢熱門度（由 user_preferences.record_query 呼叫）。
    同時更新 community_query_stats（不重複用戶計數）。
    """
    if not query_value or not query_value.strip():
        return
    query_value = query_value.strip()

    try:
        with _get_conn() as conn:
            # 檢查此用戶今日是否已查詢過此關鍵字（避免重複計入 total_users）
            today = datetime.utcnow().strftime("%Y-%m-%d")
            already_counted = conn.execute("""
                SELECT COUNT(*) as cnt FROM query_history
                WHERE user_id = ? AND query_value = ? AND query_type = ?
                  AND queried_at >= ? AND queried_at < datetime(?, '+1 day')
                  AND id < (SELECT MAX(id) FROM query_history WHERE user_id = ? AND query_value = ?)
            """, (user_id, query_value, query_type, today, today, user_id, query_value)).fetchone()

            is_new_user_today = (not already_counted or already_counted["cnt"] == 0)

            conn.execute("""
                INSERT INTO community_query_stats
                    (query_value, query_type, sport, total_users, total_queries, last_queried)
                VALUES (?, ?, ?, ?, 1, datetime('now'))
                ON CONFLICT(query_value, query_type) DO UPDATE SET
                    total_queries = total_queries + 1,
                    total_users   = total_users + CASE WHEN ? THEN 1 ELSE 0 END,
                    sport         = CASE WHEN excluded.sport != '' THEN excluded.sport ELSE sport END,
                    last_queried  = excluded.last_queried
            """, (query_value, query_type, sport, 1 if is_new_user_today else 0, 1 if is_new_user_today else 0))
    except Exception as e:
        logger.error(f"記錄群體查詢失敗: {e}")


def get_trending_topics(top_n: int = 10, days: int = 7) -> list[dict]:
    """
    取得近 N 天的熱門查詢排行（熱門關注指數）。

    Returns:
        [{"query_value": "湖人", "sport": "basketball", "total_users": 120,
          "total_queries": 340, "heat_index": 87.5}, ...]
    """
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    with _get_conn() as conn:
        rows = conn.execute("""
            SELECT cqs.query_value, cqs.query_type, cqs.sport,
                   cqs.total_users, cqs.total_queries
            FROM community_query_stats cqs
            WHERE cqs.last_queried >= ?
            ORDER BY cqs.total_queries DESC
            LIMIT ?
        """, (since, top_n)).fetchall()

        if not rows:
            return []

        max_queries = rows[0]["total_queries"] if rows else 1
        result = []
        for row in rows:
            heat_index = round(row["total_queries"] / max_queries * 100, 1)
            result.append({
                "query_value":   row["query_value"],
                "query_type":    row["query_type"],
                "sport":         row["sport"],
                "total_users":   row["total_users"],
                "total_queries": row["total_queries"],
                "heat_index":    heat_index,
            })
        return result


def get_trending_by_sport(sport: str, top_n: int = 5, days: int = 7) -> list[dict]:
    """取得特定運動的熱門隊伍/聯賽"""
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    with _get_conn() as conn:
        rows = conn.execute("""
            SELECT query_value, total_users, total_queries
            FROM community_query_stats
            WHERE sport = ? AND last_queried >= ?
            ORDER BY total_queries DESC
            LIMIT ?
        """, (sport, since, top_n)).fetchall()
        return [dict(r) for r in rows]


# ══════════════════════════════════════════════
#  2. 群體預測分析 & 3. 爆冷事件記錄
# ══════════════════════════════════════════════

def record_community_prediction_result(
    poll_id: str,
    match_desc: str,
    sport: str,
    total_voters: int,
    vote_distribution: dict,   # {0: count, 1: count, 2: count}
    correct_option: int,
    option_labels: dict,       # {0: "曼城", 1: "利物浦", 2: "平局"}
):
    """
    記錄群體預測結果，計算準確率並偵測爆冷事件。
    由 prediction_game.settle_poll 結算後呼叫。

    Args:
        poll_id:           Poll ID
        match_desc:        賽事描述
        sport:             運動類型
        total_voters:      總投票人數
        vote_distribution: 各選項得票數
        correct_option:    正確選項索引
        option_labels:     選項文字對照
    """
    if total_voters == 0:
        return

    try:
        # 計算多數人選的選項
        majority_option = max(vote_distribution, key=lambda k: vote_distribution.get(k, 0))
        majority_count  = vote_distribution.get(majority_option, 0)
        correct_count   = vote_distribution.get(correct_option, 0)
        wrong_count     = total_voters - correct_count

        crowd_accuracy  = round(correct_count / total_voters * 100, 1)
        is_upset        = (majority_option != correct_option)
        upset_magnitude = round(majority_count / total_voters, 3) if is_upset else 0.0

        with _get_conn() as conn:
            # 更新群體預測統計
            conn.execute("""
                INSERT OR REPLACE INTO community_prediction_stats
                    (poll_id, match_desc, sport, total_voters, correct_voters, wrong_voters,
                     crowd_accuracy, majority_option, correct_option, is_upset, upset_magnitude, settled_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (poll_id, match_desc, sport, total_voters, correct_count, wrong_count,
                  crowd_accuracy, majority_option, correct_option,
                  1 if is_upset else 0, upset_magnitude))

            # 若為爆冷事件，記錄到 upset_events
            if is_upset and upset_magnitude >= UPSET_THRESHOLD:
                conn.execute("""
                    INSERT INTO upset_events
                        (poll_id, match_desc, sport, majority_option, correct_option,
                         upset_magnitude, total_voters)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    poll_id, match_desc, sport,
                    option_labels.get(majority_option, str(majority_option)),
                    option_labels.get(correct_option, str(correct_option)),
                    upset_magnitude, total_voters
                ))
                logger.info(
                    f"🔥 爆冷事件記錄：{match_desc} "
                    f"多數猜={option_labels.get(majority_option)} "
                    f"實際={option_labels.get(correct_option)} "
                    f"爆冷程度={upset_magnitude:.1%}"
                )

        logger.info(f"群體預測結果記錄：{match_desc} 準確率={crowd_accuracy}% 爆冷={is_upset}")

    except Exception as e:
        logger.error(f"記錄群體預測結果失敗: {e}")


def get_community_prediction_accuracy(days: int = 30) -> dict:
    """
    計算近 N 天的群體整體預測準確率。

    Returns:
        {"total_polls": 50, "crowd_accuracy": 58.3, "upset_count": 8,
         "by_sport": {"football": 55.0, "baseball": 62.0, "basketball": 60.0}}
    """
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    with _get_conn() as conn:
        overall = conn.execute("""
            SELECT COUNT(*) as total,
                   AVG(crowd_accuracy) as avg_accuracy,
                   SUM(is_upset) as upset_count
            FROM community_prediction_stats
            WHERE settled_at >= ?
        """, (since,)).fetchone()

        by_sport = conn.execute("""
            SELECT sport, COUNT(*) as cnt, AVG(crowd_accuracy) as avg_acc
            FROM community_prediction_stats
            WHERE settled_at >= ? AND sport != ''
            GROUP BY sport
        """, (since,)).fetchall()

        return {
            "total_polls":    overall["total"] or 0,
            "crowd_accuracy": round(overall["avg_accuracy"] or 0, 1),
            "upset_count":    overall["upset_count"] or 0,
            "by_sport":       {r["sport"]: round(r["avg_acc"], 1) for r in by_sport},
        }


def get_recent_upset_events(top_n: int = 5) -> list[dict]:
    """取得最近的爆冷事件"""
    with _get_conn() as conn:
        rows = conn.execute("""
            SELECT match_desc, sport, majority_option, correct_option,
                   upset_magnitude, total_voters, occurred_at
            FROM upset_events
            ORDER BY occurred_at DESC
            LIMIT ?
        """, (top_n,)).fetchall()
        return [dict(r) for r in rows]


# ══════════════════════════════════════════════
#  4. 內容優化引擎
# ══════════════════════════════════════════════

def record_content_interaction(style: str, sport: str, message_type: str, interaction_count: int = 1):
    """
    記錄某種風格的訊息收到的互動次數。
    每當用戶在收到某種風格的訊息後，在 30 分鐘內有後續查詢，即視為互動。

    Args:
        style:             'detailed' | 'brief' | 'data'
        sport:             運動類型
        message_type:      'analysis' | 'preview' | 'review'
        interaction_count: 互動次數（通常為 1）
    """
    try:
        with _get_conn() as conn:
            conn.execute("""
                INSERT INTO content_style_metrics
                    (style, sport, message_type, interaction_count)
                VALUES (?, ?, ?, ?)
            """, (style, sport, message_type, interaction_count))
    except Exception as e:
        logger.error(f"記錄內容互動失敗: {e}")


def get_optimal_content_style(sport: str = "", days: int = 30) -> str:
    """
    根據近 N 天的互動數據，推薦最佳內容風格。

    Returns:
        'detailed' | 'brief' | 'data'
    """
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        with _get_conn() as conn:
            if sport:
                rows = conn.execute("""
                    SELECT style, SUM(interaction_count) as total_interactions
                    FROM content_style_metrics
                    WHERE sport = ? AND sent_at >= ?
                    GROUP BY style
                    ORDER BY total_interactions DESC
                    LIMIT 1
                """, (sport, since)).fetchone()
            else:
                rows = conn.execute("""
                    SELECT style, SUM(interaction_count) as total_interactions
                    FROM content_style_metrics
                    WHERE sent_at >= ?
                    GROUP BY style
                    ORDER BY total_interactions DESC
                    LIMIT 1
                """, (since,)).fetchone()

            if rows and rows["style"]:
                return rows["style"]
    except Exception as e:
        logger.error(f"取得最佳風格失敗: {e}")

    return STYLE_DETAILED  # 預設詳細風格


def get_style_performance_report(days: int = 30) -> dict:
    """
    取得各風格的互動率報告。

    Returns:
        {"detailed": {"total": 150, "pct": 55.6},
         "brief":    {"total": 80,  "pct": 29.6},
         "data":     {"total": 40,  "pct": 14.8}}
    """
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        with _get_conn() as conn:
            rows = conn.execute("""
                SELECT style, SUM(interaction_count) as total
                FROM content_style_metrics
                WHERE sent_at >= ?
                GROUP BY style
            """, (since,)).fetchall()

            total_all = sum(r["total"] for r in rows) or 1
            return {
                r["style"]: {
                    "total": r["total"],
                    "pct":   round(r["total"] / total_all * 100, 1),
                }
                for r in rows
            }
    except Exception as e:
        logger.error(f"取得風格報告失敗: {e}")
        return {}


# ══════════════════════════════════════════════
#  5. 每週洞察報告
# ══════════════════════════════════════════════

def generate_weekly_insights_report() -> str:
    """
    生成本週玩家趨勢報告。
    整合：熱門度、群體預測準確率、爆冷事件、最佳內容風格。
    """
    now = datetime.utcnow()
    week_start = (now - timedelta(days=7)).strftime("%Y/%m/%d")
    week_end   = now.strftime("%Y/%m/%d")

    sep  = "═" * 24
    dash = "─" * 20

    lines = [
        sep,
        "📊 本週玩家趨勢報告",
        f"📅 {week_start} ～ {week_end}",
        sep,
        "",
    ]

    # ── 1. 熱門關注指數 ──
    trending = get_trending_topics(top_n=5, days=7)
    lines.append("🔥 本週熱門關注排行")
    lines.append(dash)
    if trending:
        sport_emoji = {
            "football": "⚽", "baseball": "⚾",
            "basketball": "🏀", "hockey": "🏒", "nfl": "🏈",
        }
        for i, t in enumerate(trending, 1):
            emoji = sport_emoji.get(t["sport"], "🏆")
            bar_len = int(t["heat_index"] / 10)
            bar = "█" * bar_len + "░" * (10 - bar_len)
            lines.append(
                f"  {i}. {emoji} {t['query_value']:<10} "
                f"[{bar}] {t['heat_index']:.0f}分"
                f"（{t['total_users']} 人關注）"
            )
    else:
        lines.append("  本週尚無足夠查詢數據")
    lines.append("")

    # ── 2. 群體預測準確率 ──
    pred_stats = get_community_prediction_accuracy(days=7)
    lines.append("🎯 本週群體預測分析")
    lines.append(dash)
    if pred_stats["total_polls"] > 0:
        lines.append(f"  總預測場次：{pred_stats['total_polls']} 場")
        lines.append(f"  群體準確率：{pred_stats['crowd_accuracy']:.1f}%")
        lines.append(f"  爆冷事件：  {pred_stats['upset_count']} 次")
        if pred_stats["by_sport"]:
            lines.append("")
            lines.append("  各運動準確率：")
            sport_name = {"football": "⚽足球", "baseball": "⚾棒球", "basketball": "🏀籃球"}
            for sport, acc in pred_stats["by_sport"].items():
                lines.append(f"    {sport_name.get(sport, sport)}: {acc:.1f}%")
    else:
        lines.append("  本週尚無預測投票數據")
    lines.append("")

    # ── 3. 最新爆冷事件 ──
    upsets = get_recent_upset_events(top_n=3)
    if upsets:
        lines.append("❄️ 本週爆冷事件")
        lines.append(dash)
        for u in upsets:
            sport_emoji_map = {"football": "⚽", "baseball": "⚾", "basketball": "🏀"}
            emoji = sport_emoji_map.get(u["sport"], "🏆")
            lines.append(f"  {emoji} {u['match_desc']}")
            lines.append(
                f"     多數人猜：{u['majority_option']}  "
                f"實際結果：{u['correct_option']}  "
                f"爆冷程度：{u['upset_magnitude']:.0%}"
            )
        lines.append("")

    # ── 4. 最佳內容風格 ──
    style_report = get_style_performance_report(days=7)
    optimal_style = get_optimal_content_style(days=7)
    style_label = {
        STYLE_DETAILED: "📊 詳細分析",
        STYLE_BRIEF:    "⚡ 快速比分",
        STYLE_DATA:     "📈 數據型",
    }
    lines.append("📱 本週內容互動分析")
    lines.append(dash)
    if style_report:
        for style, data in sorted(style_report.items(), key=lambda x: x[1]["pct"], reverse=True):
            marker = " ← 最受歡迎" if style == optimal_style else ""
            lines.append(f"  {style_label.get(style, style)}: {data['pct']:.1f}%{marker}")
        lines.append(f"\n  🤖 下週推播將優先採用：{style_label.get(optimal_style, optimal_style)}")
    else:
        lines.append("  本週尚無足夠互動數據")
    lines.append("")

    lines.extend([
        sep,
        "📡 世界體育數據室",
        "💡 /insights 查看即時趨勢 ｜ /rank 查看積分排行",
    ])

    report_text = "\n".join(lines)

    # 儲存報告記錄
    try:
        with _get_conn() as conn:
            conn.execute("""
                INSERT INTO weekly_insights_log (week_start, week_end, report_text)
                VALUES (?, ?, ?)
            """, (week_start, week_end, report_text))
    except Exception as e:
        logger.error(f"儲存週報失敗: {e}")

    return report_text


# ══════════════════════════════════════════════
#  /insights 即時趨勢指令
# ══════════════════════════════════════════════

def generate_insights_snapshot() -> str:
    """
    生成即時趨勢快照（供 /insights 指令使用）。
    顯示近 7 天的熱門度、預測準確率、爆冷事件。
    """
    sep  = "═" * 24
    dash = "─" * 20

    lines = [
        sep,
        "📡 即時社群趨勢洞察",
        f"🕐 {datetime.utcnow().strftime('%Y/%m/%d %H:%M')} UTC",
        sep,
        "",
    ]

    # 熱門度 Top 5
    trending = get_trending_topics(top_n=5, days=7)
    lines.append("🔥 近7天熱門關注（Top 5）")
    lines.append(dash)
    if trending:
        sport_emoji = {
            "football": "⚽", "baseball": "⚾",
            "basketball": "🏀", "hockey": "🏒", "nfl": "🏈",
        }
        for i, t in enumerate(trending, 1):
            emoji = sport_emoji.get(t["sport"], "🏆")
            lines.append(
                f"  {i}. {emoji} {t['query_value']}"
                f"（{t['total_users']} 人 / {t['total_queries']} 次）"
            )
    else:
        lines.append("  尚無足夠數據")
    lines.append("")

    # 群體預測準確率
    pred = get_community_prediction_accuracy(days=7)
    lines.append("🎯 近7天群體預測")
    lines.append(dash)
    if pred["total_polls"] > 0:
        accuracy_bar_len = int(pred["crowd_accuracy"] / 10)
        accuracy_bar = "█" * accuracy_bar_len + "░" * (10 - accuracy_bar_len)
        lines.append(f"  準確率：[{accuracy_bar}] {pred['crowd_accuracy']:.1f}%")
        lines.append(f"  預測場次：{pred['total_polls']} 場")
        lines.append(f"  爆冷事件：{pred['upset_count']} 次")
    else:
        lines.append("  尚無預測投票數據")
    lines.append("")

    # 最近爆冷
    upsets = get_recent_upset_events(top_n=2)
    if upsets:
        lines.append("❄️ 最近爆冷事件")
        lines.append(dash)
        for u in upsets:
            lines.append(f"  🔥 {u['match_desc']}")
            lines.append(f"     {u['majority_option']} → 實際：{u['correct_option']}")
        lines.append("")

    # 最佳風格
    optimal = get_optimal_content_style(days=7)
    style_label = {
        STYLE_DETAILED: "📊 詳細分析",
        STYLE_BRIEF:    "⚡ 快速比分",
        STYLE_DATA:     "📈 數據型",
    }
    lines.append("📱 當前最受歡迎推播風格")
    lines.append(dash)
    lines.append(f"  {style_label.get(optimal, optimal)}")
    lines.append("")

    lines.extend([
        sep,
        "📡 世界體育數據室",
        "📊 每週一發布完整趨勢報告",
    ])

    return "\n".join(lines)


# ══════════════════════════════════════════════
#  管理員統計
# ══════════════════════════════════════════════

def get_admin_stats() -> dict:
    """取得管理員用的系統統計數據"""
    try:
        with _get_conn() as conn:
            total_queries = conn.execute(
                "SELECT SUM(total_queries) as t FROM community_query_stats"
            ).fetchone()["t"] or 0

            total_polls = conn.execute(
                "SELECT COUNT(*) as t FROM community_prediction_stats"
            ).fetchone()["t"] or 0

            total_upsets = conn.execute(
                "SELECT COUNT(*) as t FROM upset_events"
            ).fetchone()["t"] or 0

            total_users = conn.execute(
                "SELECT COUNT(*) as t FROM user_settings"
            ).fetchone()["t"] or 0

            return {
                "total_users":   total_users,
                "total_queries": total_queries,
                "total_polls":   total_polls,
                "total_upsets":  total_upsets,
                "db_path":       str(_DB_PATH),
            }
    except Exception as e:
        logger.error(f"取得管理員統計失敗: {e}")
        return {}


# ── 模組載入時自動初始化資料表 ──
try:
    init_community_tables()
except Exception as _e:
    logger.warning(f"群體分析資料表初始化失敗（可能是只讀環境）：{_e}")
