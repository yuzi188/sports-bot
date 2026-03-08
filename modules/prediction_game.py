"""
投票預測遊戲模組 V1
Telegram Poll + SQLite 積分系統

功能：
  1. 頻道推播賽事時，自動發送 Telegram Poll 讓用戶預測勝負
  2. 猜對 +10 分，猜錯 +2 分（參與獎）
  3. 比賽結束後 Bot 自動公布結果並更新積分
  4. /rank  — 積分排行榜（Top 10）
  5. /myscore — 個人積分與預測戰績
  6. 積分與用戶喜好共用同一 SQLite 資料庫（data/user_preferences.db）

資料表：
  - prediction_polls   — Poll 記錄（poll_id, match_info, correct_option, status）
  - prediction_votes   — 用戶投票記錄（user_id, poll_id, chosen_option）
  - user_scores        — 用戶積分（user_id, total_score, correct, total）
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ── 共用資料庫路徑（與 user_preferences.py 相同）──
_DB_DIR  = Path(__file__).parent.parent / "data"
_DB_PATH = _DB_DIR / "user_preferences.db"

# ── 積分設定 ──
SCORE_CORRECT     = 10   # 猜對得分
SCORE_PARTICIPATE = 2    # 參與獎（猜錯）
SCORE_BONUS_UPSET = 5    # 爆冷加成（猜中冷門隊額外加分）

# ── Poll 狀態 ──
STATUS_OPEN   = "open"    # 投票中
STATUS_CLOSED = "closed"  # 已結算


def _get_conn() -> sqlite3.Connection:
    """取得 SQLite 連線"""
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_prediction_tables():
    """初始化投票預測遊戲所需的資料表"""
    with _get_conn() as conn:
        conn.executescript("""
            -- Poll 記錄
            CREATE TABLE IF NOT EXISTS prediction_polls (
                poll_id         TEXT    PRIMARY KEY,   -- Telegram poll_id
                message_id      INTEGER DEFAULT 0,     -- 頻道訊息 ID（用於後續更新）
                chat_id         TEXT    DEFAULT '',    -- 頻道/群組 ID
                match_desc      TEXT    NOT NULL,      -- 賽事描述（如「曼城 vs 利物浦」）
                option_0        TEXT    NOT NULL,      -- 選項 0（主隊或客隊）
                option_1        TEXT    NOT NULL,      -- 選項 1（另一隊）
                option_2        TEXT    DEFAULT '平局/延長', -- 選項 2（平局，足球用）
                sport           TEXT    DEFAULT '',    -- 運動類型
                correct_option  INTEGER DEFAULT -1,   -- 正確選項索引（-1=未結算）
                is_upset        INTEGER DEFAULT 0,     -- 是否爆冷（1=爆冷）
                status          TEXT    DEFAULT 'open',
                created_at      TEXT    DEFAULT (datetime('now')),
                settled_at      TEXT    DEFAULT NULL
            );

            -- 用戶投票記錄
            CREATE TABLE IF NOT EXISTS prediction_votes (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                poll_id         TEXT    NOT NULL,
                user_id         INTEGER NOT NULL,
                username        TEXT    DEFAULT '',
                chosen_option   INTEGER NOT NULL,   -- 0 / 1 / 2
                is_correct      INTEGER DEFAULT -1, -- -1=未結算, 1=正確, 0=錯誤
                score_awarded   INTEGER DEFAULT 0,
                voted_at        TEXT    DEFAULT (datetime('now')),
                UNIQUE(poll_id, user_id)
            );

            -- 用戶積分總表
            CREATE TABLE IF NOT EXISTS user_scores (
                user_id         INTEGER PRIMARY KEY,
                username        TEXT    DEFAULT '',
                total_score     INTEGER DEFAULT 0,
                correct_count   INTEGER DEFAULT 0,
                total_votes     INTEGER DEFAULT 0,
                updated_at      TEXT    DEFAULT (datetime('now'))
            );

            -- 索引
            CREATE INDEX IF NOT EXISTS idx_votes_poll
                ON prediction_votes(poll_id);
            CREATE INDEX IF NOT EXISTS idx_votes_user
                ON prediction_votes(user_id);
            CREATE INDEX IF NOT EXISTS idx_scores_rank
                ON user_scores(total_score DESC);
        """)
    logger.info("投票預測遊戲資料表已初始化")


# ══════════════════════════════════════════════
#  Poll 管理
# ══════════════════════════════════════════════

def register_poll(
    poll_id: str,
    match_desc: str,
    option_0: str,
    option_1: str,
    sport: str = "",
    option_2: str = "",
    chat_id: str = "",
    message_id: int = 0,
):
    """
    註冊一個新的預測 Poll。
    由 bot.py 在發送 Telegram Poll 後呼叫。

    Args:
        poll_id:    Telegram 回傳的 poll.id
        match_desc: 賽事描述，如「⚽ 曼城 vs 利物浦」
        option_0:   選項 0 文字（通常是主隊）
        option_1:   選項 1 文字（通常是客隊）
        sport:      運動類型（football/baseball/basketball）
        option_2:   選項 2 文字（平局，足球才有）
        chat_id:    頻道/群組 ID
        message_id: 訊息 ID
    """
    with _get_conn() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO prediction_polls
                (poll_id, message_id, chat_id, match_desc, option_0, option_1, option_2, sport)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (poll_id, message_id, chat_id, match_desc, option_0, option_1, option_2 or "平局/延長", sport))
    logger.info(f"Poll 已註冊：{poll_id} — {match_desc}")


def record_vote(poll_id: str, user_id: int, username: str, chosen_option: int):
    """
    記錄用戶投票。
    由 Telegram PollAnswerHandler 呼叫。

    Args:
        poll_id:        Telegram poll_id
        user_id:        用戶 Telegram ID
        username:       用戶名稱（顯示用）
        chosen_option:  用戶選擇的選項索引（0/1/2）
    """
    try:
        with _get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO prediction_votes
                    (poll_id, user_id, username, chosen_option)
                VALUES (?, ?, ?, ?)
            """, (poll_id, user_id, username, chosen_option))
            # 確保 user_scores 有此用戶的記錄
            conn.execute("""
                INSERT OR IGNORE INTO user_scores (user_id, username)
                VALUES (?, ?)
            """, (user_id, username))
        logger.info(f"投票記錄：user={user_id} poll={poll_id} option={chosen_option}")
    except Exception as e:
        logger.error(f"記錄投票失敗: {e}")


def settle_poll(poll_id: str, correct_option: int, is_upset: bool = False) -> dict:
    """
    結算 Poll，更新所有投票者的積分。

    Args:
        poll_id:        要結算的 poll_id
        correct_option: 正確答案的選項索引（0/1/2）
        is_upset:       是否爆冷（True 時猜對者額外 +5 分）

    Returns:
        {
            "match_desc": "...",
            "correct_option": 0,
            "correct_label": "曼城",
            "total_voters": 50,
            "correct_voters": 30,
            "wrong_voters": 20,
            "is_upset": False,
            "top_scorers": [{"username": "...", "score_awarded": 15}, ...]
        }
    """
    result = {
        "match_desc": "",
        "correct_option": correct_option,
        "correct_label": "",
        "total_voters": 0,
        "correct_voters": 0,
        "wrong_voters": 0,
        "is_upset": is_upset,
        "top_scorers": [],
    }

    try:
        with _get_conn() as conn:
            # 取得 Poll 資訊
            poll = conn.execute(
                "SELECT * FROM prediction_polls WHERE poll_id = ?", (poll_id,)
            ).fetchone()

            if not poll:
                logger.warning(f"找不到 Poll：{poll_id}")
                return result

            if poll["status"] == STATUS_CLOSED:
                logger.warning(f"Poll 已結算過：{poll_id}")
                return result

            # 取得選項文字
            option_map = {
                0: poll["option_0"],
                1: poll["option_1"],
                2: poll["option_2"],
            }
            result["match_desc"] = poll["match_desc"]
            result["correct_label"] = option_map.get(correct_option, "")

            # 取得所有投票
            votes = conn.execute(
                "SELECT * FROM prediction_votes WHERE poll_id = ?", (poll_id,)
            ).fetchall()

            result["total_voters"] = len(votes)
            top_scorers = []

            for vote in votes:
                user_id = vote["user_id"]
                is_correct = (vote["chosen_option"] == correct_option)
                base_score = SCORE_CORRECT if is_correct else SCORE_PARTICIPATE
                bonus = SCORE_BONUS_UPSET if (is_correct and is_upset) else 0
                score = base_score + bonus

                result["correct_voters" if is_correct else "wrong_voters"] += 1

                # 更新投票記錄
                conn.execute("""
                    UPDATE prediction_votes
                    SET is_correct = ?, score_awarded = ?
                    WHERE poll_id = ? AND user_id = ?
                """, (1 if is_correct else 0, score, poll_id, user_id))

                # 更新用戶積分
                conn.execute("""
                    UPDATE user_scores
                    SET total_score   = total_score + ?,
                        correct_count = correct_count + ?,
                        total_votes   = total_votes + 1,
                        updated_at    = datetime('now')
                    WHERE user_id = ?
                """, (score, 1 if is_correct else 0, user_id))

                if is_correct:
                    top_scorers.append({
                        "username": vote["username"] or f"用戶{user_id}",
                        "score_awarded": score,
                    })

            # 標記 Poll 為已結算
            conn.execute("""
                UPDATE prediction_polls
                SET status = ?, correct_option = ?, is_upset = ?, settled_at = datetime('now')
                WHERE poll_id = ?
            """, (STATUS_CLOSED, correct_option, 1 if is_upset else 0, poll_id))

            result["top_scorers"] = sorted(
                top_scorers, key=lambda x: x["score_awarded"], reverse=True
            )[:5]

        logger.info(
            f"Poll 結算完成：{poll_id} 正確選項={correct_option} "
            f"猜對={result['correct_voters']} 猜錯={result['wrong_voters']}"
        )

    except Exception as e:
        logger.error(f"結算 Poll 失敗 {poll_id}: {e}")

    return result


def format_settlement_message(settle_result: dict) -> str:
    """格式化結算公告訊息"""
    sep = "═" * 24
    dash = "─" * 20
    r = settle_result

    lines = [
        sep,
        "🏆 預測結果公布！",
        sep,
        "",
        f"📋 賽事：{r['match_desc']}",
        f"✅ 正確答案：**{r['correct_label']}**",
        "",
        dash,
        f"📊 投票統計",
        dash,
        f"  總投票人數：{r['total_voters']} 人",
        f"  猜對人數：  {r['correct_voters']} 人 🎉",
        f"  猜錯人數：  {r['wrong_voters']} 人",
    ]

    if r["is_upset"]:
        lines.extend([
            "",
            "❄️ **爆冷！** 猜對者額外獲得 +5 分爆冷加成！",
        ])

    lines.extend([
        "",
        dash,
        "💰 積分獎勵",
        dash,
        f"  猜對：+{SCORE_CORRECT} 分" + (f"（+{SCORE_BONUS_UPSET} 爆冷加成）" if r["is_upset"] else ""),
        f"  猜錯：+{SCORE_PARTICIPATE} 分（參與獎）",
    ])

    if r["top_scorers"]:
        lines.extend(["", dash, "🌟 本場猜對玩家", dash])
        for i, s in enumerate(r["top_scorers"], 1):
            lines.append(f"  {i}. {s['username']}（+{s['score_awarded']} 分）")

    lines.extend([
        "",
        sep,
        "📡 世界體育數據室",
        "🎮 繼續預測，累積積分！",
    ])
    return "\n".join(lines)


# ══════════════════════════════════════════════
#  積分查詢
# ══════════════════════════════════════════════

def get_leaderboard(top_n: int = 10) -> list[dict]:
    """
    取得積分排行榜（Top N）。

    Returns:
        [{"rank": 1, "username": "...", "total_score": 150, "correct_count": 12, "total_votes": 15, "win_rate": 80.0}, ...]
    """
    with _get_conn() as conn:
        rows = conn.execute("""
            SELECT user_id, username, total_score, correct_count, total_votes
            FROM user_scores
            WHERE total_votes > 0
            ORDER BY total_score DESC, correct_count DESC
            LIMIT ?
        """, (top_n,)).fetchall()

        result = []
        for i, row in enumerate(rows, 1):
            win_rate = round(row["correct_count"] / row["total_votes"] * 100, 1) if row["total_votes"] > 0 else 0.0
            result.append({
                "rank":          i,
                "username":      row["username"] or f"用戶{row['user_id']}",
                "total_score":   row["total_score"],
                "correct_count": row["correct_count"],
                "total_votes":   row["total_votes"],
                "win_rate":      win_rate,
            })
        return result


def get_user_score(user_id: int) -> dict | None:
    """
    取得個人積分資料。

    Returns:
        {"total_score": 80, "correct_count": 7, "total_votes": 10, "win_rate": 70.0, "rank": 3}
        或 None（若無記錄）
    """
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM user_scores WHERE user_id = ?", (user_id,)
        ).fetchone()

        if not row or row["total_votes"] == 0:
            return None

        # 計算排名
        rank_row = conn.execute("""
            SELECT COUNT(*) + 1 AS rank
            FROM user_scores
            WHERE total_score > ? AND total_votes > 0
        """, (row["total_score"],)).fetchone()

        win_rate = round(row["correct_count"] / row["total_votes"] * 100, 1) if row["total_votes"] > 0 else 0.0

        return {
            "total_score":   row["total_score"],
            "correct_count": row["correct_count"],
            "total_votes":   row["total_votes"],
            "win_rate":      win_rate,
            "rank":          rank_row["rank"] if rank_row else 1,
        }


def format_leaderboard_message(leaderboard: list[dict]) -> str:
    """格式化積分排行榜訊息（靈感來自 playsport.cc 的勝率排行）"""
    sep = "═" * 24
    dash = "─" * 20

    if not leaderboard:
        return f"{sep}\n🏆 積分排行榜\n{sep}\n\n目前尚無積分記錄\n快來參與預測投票！\n\n{sep}\n📡 世界體育數據室"

    lines = [
        sep,
        "🏆 預測積分排行榜 Top 10",
        sep,
        "",
        f"{'名次':<4} {'玩家':<12} {'積分':>6} {'勝率':>7}",
        dash,
    ]

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for entry in leaderboard:
        rank = entry["rank"]
        medal = medals.get(rank, f"#{rank} ")
        name = entry["username"][:10]  # 截斷過長名稱
        score = entry["total_score"]
        win_rate = entry["win_rate"]
        lines.append(f"{medal:<4} {name:<12} {score:>5}分  {win_rate:>5.1f}%")

    lines.extend([
        "",
        dash,
        f"💰 猜對 +{SCORE_CORRECT}分 ｜ 參與 +{SCORE_PARTICIPATE}分 ｜ 爆冷加成 +{SCORE_BONUS_UPSET}分",
        "",
        sep,
        "📡 世界體育數據室",
        "🎮 /myscore 查詢個人積分",
    ])
    return "\n".join(lines)


def format_personal_score_message(user_id: int, username: str) -> str:
    """格式化個人積分訊息"""
    sep = "═" * 24
    dash = "─" * 20
    score_data = get_user_score(user_id)

    if not score_data:
        return (
            f"{sep}\n📊 我的預測積分\n{sep}\n\n"
            "您尚未參與任何預測投票！\n\n"
            "頻道推播賽事時，記得點擊投票參與預測 🎯\n\n"
            f"{sep}\n📡 世界體育數據室"
        )

    # 根據勝率給予稱號（靈感來自 playsport.cc 的會員等級）
    win_rate = score_data["win_rate"]
    if win_rate >= 70:
        title = "🔥 預測大師"
    elif win_rate >= 55:
        title = "⭐ 資深預測員"
    elif win_rate >= 40:
        title = "📈 進階預測員"
    else:
        title = "🌱 新手預測員"

    lines = [
        sep,
        "📊 我的預測積分",
        sep,
        "",
        f"👤 {username}",
        f"🏅 稱號：{title}",
        "",
        dash,
        f"  🏆 總積分：    {score_data['total_score']} 分",
        f"  🎯 預測場次：  {score_data['total_votes']} 場",
        f"  ✅ 猜對場次：  {score_data['correct_count']} 場",
        f"  📊 預測勝率：  {win_rate:.1f}%",
        f"  🥇 目前排名：  第 {score_data['rank']} 名",
        "",
        dash,
        "💡 積分說明：",
        f"  猜對 +{SCORE_CORRECT}分 ｜ 參與 +{SCORE_PARTICIPATE}分 ｜ 爆冷加成 +{SCORE_BONUS_UPSET}分",
        "",
        sep,
        "📡 世界體育數據室",
        "🏆 /rank 查看排行榜",
    ]
    return "\n".join(lines)


# ══════════════════════════════════════════════
#  Poll 建立輔助函數（供 bot.py 使用）
# ══════════════════════════════════════════════

def build_poll_options(home_team: str, away_team: str, sport: str) -> list[str]:
    """
    根據運動類型建立 Poll 選項。
    足球有平局選項，棒球/籃球無平局。
    """
    if sport == "football":
        return [home_team, away_team, "平局"]
    else:
        return [home_team, away_team]


def build_poll_question(match_desc: str, sport: str) -> str:
    """建立 Poll 問題文字"""
    sport_emoji = {
        "football":   "⚽",
        "baseball":   "⚾",
        "basketball": "🏀",
    }.get(sport, "🏆")
    return f"{sport_emoji} 預測今日比賽勝者：\n{match_desc}"


def get_open_polls() -> list[dict]:
    """取得所有尚未結算的 Poll（供定時任務使用）"""
    with _get_conn() as conn:
        rows = conn.execute("""
            SELECT poll_id, match_desc, sport, option_0, option_1, option_2,
                   chat_id, message_id, created_at
            FROM prediction_polls
            WHERE status = 'open'
            ORDER BY created_at DESC
        """).fetchall()
        return [dict(r) for r in rows]


def get_poll_vote_stats(poll_id: str) -> dict:
    """取得 Poll 投票統計（用於顯示目前投票分布）"""
    with _get_conn() as conn:
        poll = conn.execute(
            "SELECT option_0, option_1, option_2 FROM prediction_polls WHERE poll_id = ?",
            (poll_id,)
        ).fetchone()

        if not poll:
            return {}

        stats = conn.execute("""
            SELECT chosen_option, COUNT(*) as cnt
            FROM prediction_votes
            WHERE poll_id = ?
            GROUP BY chosen_option
        """, (poll_id,)).fetchall()

        vote_map = {row["chosen_option"]: row["cnt"] for row in stats}
        total = sum(vote_map.values())

        return {
            "option_0": {"label": poll["option_0"], "count": vote_map.get(0, 0)},
            "option_1": {"label": poll["option_1"], "count": vote_map.get(1, 0)},
            "option_2": {"label": poll["option_2"], "count": vote_map.get(2, 0)},
            "total":    total,
        }


# ── 模組載入時自動初始化資料表 ──
try:
    init_prediction_tables()
except Exception as _e:
    logger.warning(f"投票預測資料表初始化失敗（可能是只讀環境）：{_e}")
