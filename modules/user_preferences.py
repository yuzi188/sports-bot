"""
用戶喜好記憶學習模組 V1
使用 SQLite 儲存用戶偏好資料，支援：

1. 球隊/運動查詢頻率統計（自動學習）
2. 語言偏好記憶
3. 互動習慣偏好（詳細分析 vs 簡短比分）
4. 主動推薦相關賽事
5. /myfav 指令查看個人偏好摘要

資料庫位置：{BOT_DIR}/data/user_preferences.db
"""

import sqlite3
import json
import logging
import os
from datetime import datetime, timedelta
from collections import Counter
from pathlib import Path

logger = logging.getLogger(__name__)

# ── 資料庫路徑 ──
_DB_DIR = Path(__file__).parent.parent / "data"
_DB_PATH = _DB_DIR / "user_preferences.db"

# ── 互動習慣類型 ──
STYLE_DETAILED = "detailed"   # 喜歡詳細分析
STYLE_BRIEF    = "brief"      # 喜歡簡短比分
STYLE_AUTO     = "auto"       # 自動判斷（預設）

# ── 運動類型標籤 ──
SPORT_LABELS = {
    "football":   "⚽ 足球",
    "baseball":   "⚾ 棒球",
    "basketball": "🏀 籃球",
    "hockey":     "🏒 冰球",
    "nfl":        "🏈 美式足球",
}


def _get_conn() -> sqlite3.Connection:
    """取得 SQLite 連線（自動建立資料庫目錄）"""
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化資料庫，建立所有必要的資料表"""
    with _get_conn() as conn:
        conn.executescript("""
            -- 用戶基本設定
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id              INTEGER PRIMARY KEY,
                language             TEXT    DEFAULT 'zh_tw',
                style                TEXT    DEFAULT 'auto',
                welcome_video_sent   INTEGER DEFAULT 0,   -- 1=已發送歡迎影片, 0=尚未發送
                last_welcome_date    TEXT    DEFAULT NULL,  -- 最後一次發送歡迎影片的日期 (YYYY-MM-DD)
                created_at           TEXT    DEFAULT (datetime('now')),
                updated_at           TEXT    DEFAULT (datetime('now'))
            );

            -- 查詢歷史（用於學習喜好）
            CREATE TABLE IF NOT EXISTS query_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                query_type  TEXT    NOT NULL,  -- 'team' | 'sport' | 'command'
                query_value TEXT    NOT NULL,  -- 隊名 / 運動類型 / 指令名稱
                queried_at  TEXT    DEFAULT (datetime('now'))
            );

            -- 用戶最愛球隊（自動統計 + 手動加入）
            CREATE TABLE IF NOT EXISTS favorite_teams (
                user_id     INTEGER NOT NULL,
                team_name   TEXT    NOT NULL,
                sport       TEXT    DEFAULT '',
                query_count INTEGER DEFAULT 1,
                is_manual   INTEGER DEFAULT 0,  -- 1=手動加入, 0=自動統計
                last_queried TEXT   DEFAULT (datetime('now')),
                PRIMARY KEY (user_id, team_name)
            );

            -- 用戶最愛運動類型
            CREATE TABLE IF NOT EXISTS favorite_sports (
                user_id     INTEGER NOT NULL,
                sport       TEXT    NOT NULL,
                query_count INTEGER DEFAULT 1,
                last_queried TEXT   DEFAULT (datetime('now')),
                PRIMARY KEY (user_id, sport)
            );

            -- 推薦記錄（避免重複推薦）
            CREATE TABLE IF NOT EXISTS recommendation_log (
                user_id     INTEGER NOT NULL,
                content     TEXT    NOT NULL,
                sent_at     TEXT    DEFAULT (datetime('now'))
            );

            -- 建立索引加速查詢
            CREATE INDEX IF NOT EXISTS idx_query_history_user
                ON query_history(user_id, queried_at);
            CREATE INDEX IF NOT EXISTS idx_favorite_teams_user
                ON favorite_teams(user_id, query_count DESC);
            CREATE INDEX IF NOT EXISTS idx_favorite_sports_user
                ON favorite_sports(user_id, query_count DESC);
        """)
    # V19.3 遷移：若舊表缺少 welcome_video_sent 欄位，自動補加
    try:
        with _get_conn() as conn:
            conn.execute(
                "ALTER TABLE user_settings ADD COLUMN welcome_video_sent INTEGER DEFAULT 0"
            )
        logger.info("已新增 welcome_video_sent 欄位")
    except Exception:
        pass  # 欄位已存在，忽略錯誤

    # V19.5 遷移：若舊表缺少 last_welcome_date 欄位，自動補加
    try:
        with _get_conn() as conn:
            conn.execute(
                "ALTER TABLE user_settings ADD COLUMN last_welcome_date TEXT DEFAULT NULL"
            )
        logger.info("已新增 last_welcome_date 欄位")
    except Exception:
        pass  # 欄位已存在，忽略錯誤

    logger.info(f"用戶喜好資料庫已初始化：{_DB_PATH}")


# ══════════════════════════════════════════════
#  用戶設定（語言 / 互動習慣）
# ══════════════════════════════════════════════

def get_user_settings(user_id: int) -> dict:
    """
    取得用戶設定，若不存在則建立預設設定。

    Returns:
        {"language": "zh_tw", "style": "auto"}
    """
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT language, style FROM user_settings WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        if row:
            return {"language": row["language"], "style": row["style"]}
        # 建立預設設定
        conn.execute(
            "INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)",
            (user_id,)
        )
        return {"language": "zh_tw", "style": STYLE_AUTO}


def set_user_language(user_id: int, language: str):
    """儲存用戶語言偏好"""
    with _get_conn() as conn:
        conn.execute("""
            INSERT INTO user_settings (user_id, language, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(user_id) DO UPDATE SET
                language = excluded.language,
                updated_at = excluded.updated_at
        """, (user_id, language))
    logger.info(f"用戶 {user_id} 語言設定為 {language}")


def set_user_style(user_id: int, style: str):
    """
    儲存用戶互動習慣偏好。
    style: 'detailed'（詳細分析）/ 'brief'（簡短比分）/ 'auto'（自動判斷）
    """
    if style not in (STYLE_DETAILED, STYLE_BRIEF, STYLE_AUTO):
        logger.warning(f"非法 style 值：{style}")
        return
    with _get_conn() as conn:
        conn.execute("""
            INSERT INTO user_settings (user_id, style, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(user_id) DO UPDATE SET
                style = excluded.style,
                updated_at = excluded.updated_at
        """, (user_id, style))
    logger.info(f"用戶 {user_id} 互動習慣設定為 {style}")


# ══════════════════════════════
#  歡迎影片發送狀態（V19.3 新增）
# ══════════════════════════════

def has_seen_welcome_video(user_id: int) -> bool:
    """
    檢查用戶是否已收到歡迎影片。
    用於 /start 判斷是否為第一次進入。

    Returns:
        True  = 已發送過影片（不重複發送）
        False = 尚未發送（應發送影片）
    """
    try:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT welcome_video_sent FROM user_settings WHERE user_id = ?",
                (user_id,)
            ).fetchone()
            if row is None:
                return False  # 新用戶，尚未建立記錄
            return bool(row["welcome_video_sent"])
    except Exception as e:
        logger.warning(f"has_seen_welcome_video 查詢失敗: {e}")
        return False  # 出錯時保守，假設尚未發送


def mark_welcome_video_sent(user_id: int):
    """
    標記用戶已收到歡迎影片。
    如果用戶不在資料庫中，同時建立記錄。
    """
    try:
        with _get_conn() as conn:
            conn.execute("""
                INSERT INTO user_settings (user_id, welcome_video_sent, updated_at)
                VALUES (?, 1, datetime('now'))
                ON CONFLICT(user_id) DO UPDATE SET
                    welcome_video_sent = 1,
                    updated_at = datetime('now')
            """, (user_id,))
        logger.info(f"[歡迎影片] 已標記 user_id={user_id} 為已發送")
    except Exception as e:
        logger.warning(f"mark_welcome_video_sent 失敗: {e}")


def should_send_daily_welcome(user_id: int) -> bool:
    """
    判斷用戶今天是否應發送歡迎影片。

    邏輯：
    - 如果 last_welcome_date 為 NULL 或不是今天 → True（應發送）
    - 如果 last_welcome_date 已是今天 → False（不重複）

    Returns:
        True  = 今天尚未發送（應發送影片）
        False = 今天已發送過（不重複）
    """
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT last_welcome_date FROM user_settings WHERE user_id = ?",
                (user_id,)
            ).fetchone()
            if row is None:
                return True  # 新用戶，尚未建立記錄
            return row["last_welcome_date"] != today  # 不是今天就發送
    except Exception as e:
        logger.warning(f"should_send_daily_welcome 查詢失敗: {e}")
        return True  # 出錯時保守，假設應發送


def mark_daily_welcome_sent(user_id: int):
    """
    標記用戶今天已收到歡迎影片。
    如果用戶不在資料庫中，同時建立記錄。
    """
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        with _get_conn() as conn:
            conn.execute("""
                INSERT INTO user_settings (user_id, last_welcome_date, updated_at)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(user_id) DO UPDATE SET
                    last_welcome_date = excluded.last_welcome_date,
                    updated_at = datetime('now')
            """, (user_id, today))
        logger.info(f"[每日歡迎] 已標記 user_id={user_id} 今天（{today}）已發送")
    except Exception as e:
        logger.warning(f"mark_daily_welcome_sent 失敗: {e}")


# ══════════════════════════════
#  查詢歷史記錄（自動學習）
# ═══════════════════════════════════════════════

def record_query(user_id: int, query_type: str, query_value: str, sport: str = ""):
    """
    記錄用戶查詢，自動更新最愛球隊/運動統計。

    Args:
        user_id:     用戶 ID
        query_type:  'team' | 'sport' | 'command'
        query_value: 隊名 / 運動類型 / 指令名稱
        sport:       運動類型（query_type='team' 時使用）
    """
    if not query_value or not query_value.strip():
        return
    query_value = query_value.strip()

    try:
        with _get_conn() as conn:
            # 記錄查詢歷史
            conn.execute(
                "INSERT INTO query_history (user_id, query_type, query_value) VALUES (?, ?, ?)",
                (user_id, query_type, query_value)
            )

            if query_type == "team":
                # 更新最愛球隊統計
                conn.execute("""
                    INSERT INTO favorite_teams (user_id, team_name, sport, query_count, last_queried)
                    VALUES (?, ?, ?, 1, datetime('now'))
                    ON CONFLICT(user_id, team_name) DO UPDATE SET
                        query_count = query_count + 1,
                        sport = CASE WHEN excluded.sport != '' THEN excluded.sport ELSE sport END,
                        last_queried = excluded.last_queried
                """, (user_id, query_value, sport))

            elif query_type == "sport":
                # 更新最愛運動統計
                conn.execute("""
                    INSERT INTO favorite_sports (user_id, sport, query_count, last_queried)
                    VALUES (?, ?, 1, datetime('now'))
                    ON CONFLICT(user_id, sport) DO UPDATE SET
                        query_count = query_count + 1,
                        last_queried = excluded.last_queried
                """, (user_id, query_value))

    except Exception as e:
        logger.error(f"記錄查詢失敗 user={user_id}: {e}")


def infer_sport_from_query(query: str) -> str:
    """從查詢文字推斷運動類型"""
    query_lower = query.lower()
    sport_keywords = {
        "football":   ["足球", "英超", "西甲", "德甲", "意甲", "法甲", "歐冠", "世界盃", "soccer"],
        "baseball":   ["棒球", "mlb", "洋基", "道奇", "紅襪", "太空人", "巨人", "wbc"],
        "basketball": ["籃球", "nba", "湖人", "勇士", "塞爾提克", "熱火", "尼克", "公牛"],
        "hockey":     ["冰球", "nhl", "企鵝", "楓葉", "閃電"],
        "nfl":        ["美式足球", "nfl", "超級盃"],
    }
    for sport, keywords in sport_keywords.items():
        if any(kw in query_lower for kw in keywords):
            return sport
    return ""


# ══════════════════════════════════════════════
#  喜好查詢
# ══════════════════════════════════════════════

def get_top_teams(user_id: int, top_n: int = 5) -> list[dict]:
    """
    取得用戶最常查詢的球隊（Top N）。

    Returns:
        [{"team_name": "洋基", "sport": "baseball", "query_count": 12}, ...]
    """
    with _get_conn() as conn:
        rows = conn.execute("""
            SELECT team_name, sport, query_count
            FROM favorite_teams
            WHERE user_id = ?
            ORDER BY query_count DESC, last_queried DESC
            LIMIT ?
        """, (user_id, top_n)).fetchall()
        return [dict(r) for r in rows]


def get_top_sports(user_id: int, top_n: int = 3) -> list[dict]:
    """
    取得用戶最常查詢的運動類型（Top N）。

    Returns:
        [{"sport": "baseball", "query_count": 25}, ...]
    """
    with _get_conn() as conn:
        rows = conn.execute("""
            SELECT sport, query_count
            FROM favorite_sports
            WHERE user_id = ?
            ORDER BY query_count DESC
            LIMIT ?
        """, (user_id, top_n)).fetchall()
        return [dict(r) for r in rows]


def get_user_style(user_id: int) -> str:
    """
    取得用戶互動習慣偏好。
    若為 'auto'，根據查詢歷史自動判斷：
    - 若常用 /analyze、/allanalyze → 'detailed'
    - 否則 → 'brief'
    """
    settings = get_user_settings(user_id)
    style = settings.get("style", STYLE_AUTO)

    if style != STYLE_AUTO:
        return style

    # 自動判斷：統計最近 30 天的指令使用
    try:
        with _get_conn() as conn:
            row = conn.execute("""
                SELECT
                    SUM(CASE WHEN query_value IN ('analyze', 'allanalyze', 'football', 'baseball', 'basketball')
                             THEN 1 ELSE 0 END) AS analysis_count,
                    SUM(CASE WHEN query_value IN ('score', 'live', 'hot', 'today')
                             THEN 1 ELSE 0 END) AS score_count
                FROM query_history
                WHERE user_id = ?
                  AND query_type = 'command'
                  AND queried_at >= datetime('now', '-30 days')
            """, (user_id,)).fetchone()

            if row and row["analysis_count"] and row["score_count"]:
                return STYLE_DETAILED if row["analysis_count"] >= row["score_count"] else STYLE_BRIEF
    except Exception as e:
        logger.error(f"自動判斷互動習慣失敗: {e}")

    return STYLE_BRIEF  # 預設簡短


def get_user_language(user_id: int) -> str:
    """取得用戶語言設定（從 SQLite，優先於 context.user_data）"""
    settings = get_user_settings(user_id)
    return settings.get("language", "zh_tw")


# ══════════════════════════════════════════════
#  主動推薦功能
# ══════════════════════════════════════════════

def generate_recommendation(user_id: int, available_matches: list[str]) -> str | None:
    """
    根據用戶喜好，從今日賽事中找出相關比賽並生成推薦訊息。

    Args:
        user_id:           用戶 ID
        available_matches: 今日所有賽事文字列表（來自 football/mlb/nba 模組）

    Returns:
        推薦訊息文字，若無相關賽事則回傳 None
    """
    if not available_matches:
        return None

    top_teams = get_top_teams(user_id, top_n=5)
    top_sports = get_top_sports(user_id, top_n=3)

    if not top_teams and not top_sports:
        return None  # 無歷史記錄，不推薦

    # 建立關鍵字列表（球隊名稱 + 運動類型關鍵字）
    keywords = [t["team_name"] for t in top_teams]
    sport_keywords_map = {
        "football":   ["⚽", "英超", "西甲", "德甲", "意甲", "法甲", "歐冠"],
        "baseball":   ["⚾", "MLB", "WBC"],
        "basketball": ["🏀", "NBA"],
        "hockey":     ["🏒", "NHL"],
        "nfl":        ["🏈", "NFL"],
    }
    for s in top_sports:
        sport = s["sport"]
        keywords.extend(sport_keywords_map.get(sport, []))

    # 過濾出相關賽事
    matched = []
    for match_line in available_matches:
        if any(kw in match_line for kw in keywords):
            matched.append(match_line)

    if not matched:
        return None

    # 避免重複推薦（檢查最近 6 小時內是否已推薦過相同內容）
    content_key = "|".join(matched[:3])
    try:
        with _get_conn() as conn:
            recent = conn.execute("""
                SELECT COUNT(*) as cnt FROM recommendation_log
                WHERE user_id = ? AND content = ?
                  AND sent_at >= datetime('now', '-6 hours')
            """, (user_id, content_key)).fetchone()
            if recent and recent["cnt"] > 0:
                return None  # 最近已推薦過，跳過

            # 記錄本次推薦
            conn.execute(
                "INSERT INTO recommendation_log (user_id, content) VALUES (?, ?)",
                (user_id, content_key)
            )
    except Exception as e:
        logger.error(f"推薦記錄失敗: {e}")

    # 組合推薦訊息
    lines = ["🎯 根據您的喜好，今日有以下相關賽事：", ""]
    for m in matched[:5]:  # 最多推薦 5 場
        lines.append(f"  {m}")
    lines.extend([
        "",
        "💡 輸入隊名可查詢即時比分，或使用 /football /baseball /basketball 查看 AI 分析",
    ])

    return "\n".join(lines)


def should_send_recommendation(user_id: int) -> bool:
    """
    判斷是否應該主動推薦（避免過度打擾）。
    條件：用戶有查詢歷史，且距離上次推薦超過 4 小時。
    """
    try:
        with _get_conn() as conn:
            # 檢查是否有查詢歷史
            history_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM query_history WHERE user_id = ?",
                (user_id,)
            ).fetchone()
            if not history_count or history_count["cnt"] < 3:
                return False  # 查詢次數太少，不推薦

            # 檢查最近推薦時間
            last_rec = conn.execute("""
                SELECT sent_at FROM recommendation_log
                WHERE user_id = ?
                ORDER BY sent_at DESC LIMIT 1
            """, (user_id,)).fetchone()

            if not last_rec:
                return True  # 從未推薦過

            last_time = datetime.fromisoformat(last_rec["sent_at"])
            return datetime.utcnow() - last_time > timedelta(hours=4)

    except Exception as e:
        logger.error(f"推薦判斷失敗: {e}")
        return False


# ══════════════════════════════════════════════
#  /myfav 指令：個人喜好摘要
# ══════════════════════════════════════════════

def format_user_preference_summary(user_id: int) -> str:
    """
    生成用戶個人喜好摘要，供 /myfav 指令使用。
    格式參考 playsport.cc 的會員戰績總覽頁面。
    """
    settings = get_user_settings(user_id)
    top_teams = get_top_teams(user_id, top_n=5)
    top_sports = get_top_sports(user_id, top_n=3)
    style = get_user_style(user_id)

    lang_labels = {
        "zh_tw": "🇹🇼 繁體中文",
        "zh_cn": "🇨🇳 簡體中文",
        "en":    "🇺🇸 English",
        "km":    "🇰🇭 ភាសាខ្មែរ",
        "vi":    "🇻🇳 Tiếng Việt",
        "th":    "🇹🇭 ภาษาไทย",
    }
    style_labels = {
        STYLE_DETAILED: "📊 詳細分析派",
        STYLE_BRIEF:    "⚡ 快速比分派",
        STYLE_AUTO:     "🤖 自動判斷",
    }

    sep = "═" * 24
    dash = "─" * 20
    lines = [
        sep,
        "👤 我的體育偏好總覽",
        sep,
        "",
        f"🌐 語言偏好：{lang_labels.get(settings['language'], settings['language'])}",
        f"📱 互動習慣：{style_labels.get(style, style)}",
        "",
    ]

    # 最愛運動
    if top_sports:
        lines.append("🏆 最愛運動類型：")
        for i, s in enumerate(top_sports, 1):
            sport_label = SPORT_LABELS.get(s["sport"], s["sport"])
            lines.append(f"  {i}. {sport_label}（查詢 {s['query_count']} 次）")
        lines.append("")

    # 最愛球隊
    if top_teams:
        lines.append("⭐ 最常查詢球隊：")
        lines.append(f"{'球隊':<12} {'查詢次數':>6}")
        lines.append(dash)
        for t in top_teams:
            sport_emoji = {
                "football": "⚽", "baseball": "⚾",
                "basketball": "🏀", "hockey": "🏒", "nfl": "🏈"
            }.get(t["sport"], "🏆")
            lines.append(f"{sport_emoji} {t['team_name']:<10} {t['query_count']:>6} 次")
        lines.append("")
    else:
        lines.append("📝 尚無查詢記錄，開始查詢球隊後將自動學習您的喜好！")
        lines.append("")

    lines.extend([
        "💡 使用說明：",
        "• 每次查詢球隊，系統自動記錄偏好",
        "• 有相關賽事時，Bot 會主動推薦給您",
        "• /style 切換詳細分析 / 快速比分模式",
        "",
        sep,
        "📡 世界體育數據室",
    ])

    return "\n".join(lines)


# ══════════════════════════════════════════════
#  資料管理
# ══════════════════════════════════════════════

def clear_user_data(user_id: int):
    """清除指定用戶的所有喜好資料（GDPR 合規）"""
    with _get_conn() as conn:
        conn.execute("DELETE FROM user_settings WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM query_history WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM favorite_teams WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM favorite_sports WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM recommendation_log WHERE user_id = ?", (user_id,))
    logger.info(f"已清除用戶 {user_id} 的所有喜好資料")


def get_stats() -> dict:
    """取得資料庫統計（管理員用）"""
    with _get_conn() as conn:
        total_users = conn.execute("SELECT COUNT(*) as cnt FROM user_settings").fetchone()["cnt"]
        total_queries = conn.execute("SELECT COUNT(*) as cnt FROM query_history").fetchone()["cnt"]
        return {
            "total_users": total_users,
            "total_queries": total_queries,
            "db_path": str(_DB_PATH),
        }


# ── 模組載入時自動初始化資料庫 ──
try:
    init_db()
except Exception as _e:
    logger.warning(f"資料庫初始化失敗（可能是只讀環境）：{_e}")
