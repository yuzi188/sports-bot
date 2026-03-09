"""
簽到積分系統 V1.0

功能：
  - 每日簽到領積分（連續簽到加成）
  - 積分排行榜（整合 prediction_game 積分）
  - 個人積分查詢
  - 積分來源：簽到、預測猜對、群組互動
"""

import sqlite3
import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "checkin.db")


def _ensure_dir():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def _get_conn() -> sqlite3.Connection:
    _ensure_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_checkin_db():
    """初始化簽到資料庫"""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS checkin_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT DEFAULT '',
            full_name TEXT DEFAULT '',
            checkin_date TEXT NOT NULL,
            streak INTEGER DEFAULT 1,
            points_earned INTEGER DEFAULT 10,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_checkin_user_date
            ON checkin_records(user_id, checkin_date);

        CREATE TABLE IF NOT EXISTS user_points (
            user_id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            full_name TEXT DEFAULT '',
            total_points INTEGER DEFAULT 0,
            checkin_streak INTEGER DEFAULT 0,
            last_checkin_date TEXT DEFAULT '',
            total_checkins INTEGER DEFAULT 0,
            total_predictions INTEGER DEFAULT 0,
            correct_predictions INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()
    logger.info("[簽到系統] 資料庫初始化完成")


def do_checkin(user_id: int, username: str = "", full_name: str = "") -> dict:
    """
    執行簽到。

    Returns:
        dict: {
            "success": bool,
            "already_checked": bool,
            "points_earned": int,
            "streak": int,
            "total_points": int,
            "message": str
        }
    """
    conn = _get_conn()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")

    try:
        # 檢查今天是否已簽到
        existing = conn.execute(
            "SELECT * FROM checkin_records WHERE user_id=? AND checkin_date=?",
            (user_id, today)
        ).fetchone()

        if existing:
            # 取得總積分
            user = conn.execute(
                "SELECT total_points, checkin_streak FROM user_points WHERE user_id=?",
                (user_id,)
            ).fetchone()
            total = user["total_points"] if user else 0
            streak = user["checkin_streak"] if user else 0
            return {
                "success": False,
                "already_checked": True,
                "points_earned": 0,
                "streak": streak,
                "total_points": total,
                "message": "今天已經簽到過了喔！明天再來吧"
            }

        # 計算連續簽到
        user = conn.execute(
            "SELECT * FROM user_points WHERE user_id=?",
            (user_id,)
        ).fetchone()

        if user and user["last_checkin_date"] == yesterday:
            streak = user["checkin_streak"] + 1
        else:
            streak = 1

        # 計算積分（連續簽到加成）
        base_points = 10
        if streak >= 30:
            bonus = 20  # 30天+ 額外20分
        elif streak >= 14:
            bonus = 15  # 14天+ 額外15分
        elif streak >= 7:
            bonus = 10  # 7天+ 額外10分
        elif streak >= 3:
            bonus = 5   # 3天+ 額外5分
        else:
            bonus = 0
        points_earned = base_points + bonus

        # 寫入簽到記錄
        conn.execute(
            "INSERT INTO checkin_records (user_id, username, full_name, checkin_date, streak, points_earned) VALUES (?,?,?,?,?,?)",
            (user_id, username, full_name, today, streak, points_earned)
        )

        # 更新用戶積分
        if user:
            new_total = user["total_points"] + points_earned
            conn.execute("""
                UPDATE user_points SET
                    username=?, full_name=?,
                    total_points=?, checkin_streak=?,
                    last_checkin_date=?, total_checkins=total_checkins+1,
                    updated_at=datetime('now')
                WHERE user_id=?
            """, (username, full_name, new_total, streak, today, user_id))
        else:
            new_total = points_earned
            conn.execute("""
                INSERT INTO user_points
                    (user_id, username, full_name, total_points, checkin_streak, last_checkin_date, total_checkins)
                VALUES (?,?,?,?,?,?,1)
            """, (user_id, username, full_name, new_total, streak, today))

        conn.commit()

        return {
            "success": True,
            "already_checked": False,
            "points_earned": points_earned,
            "streak": streak,
            "total_points": new_total,
            "message": "簽到成功！"
        }

    except Exception as e:
        logger.error(f"[簽到系統] 簽到失敗: {e}", exc_info=True)
        return {
            "success": False,
            "already_checked": False,
            "points_earned": 0,
            "streak": 0,
            "total_points": 0,
            "message": f"簽到失敗：{e}"
        }
    finally:
        conn.close()


def add_points(user_id: int, points: int, username: str = "", full_name: str = "",
               source: str = "other") -> int:
    """
    增加積分（通用介面，供預測猜對、互動獎勵等使用）。

    Returns:
        int: 新的總積分
    """
    conn = _get_conn()
    try:
        user = conn.execute(
            "SELECT * FROM user_points WHERE user_id=?", (user_id,)
        ).fetchone()

        if user:
            new_total = user["total_points"] + points
            updates = ["total_points=?", "updated_at=datetime('now')"]
            params = [new_total]
            if username:
                updates.append("username=?")
                params.append(username)
            if full_name:
                updates.append("full_name=?")
                params.append(full_name)
            if source == "prediction":
                updates.append("correct_predictions=correct_predictions+1")
            params.append(user_id)
            conn.execute(
                f"UPDATE user_points SET {', '.join(updates)} WHERE user_id=?",
                params
            )
        else:
            new_total = max(points, 0)
            conn.execute("""
                INSERT INTO user_points
                    (user_id, username, full_name, total_points)
                VALUES (?,?,?,?)
            """, (user_id, username, full_name, new_total))

        conn.commit()
        return new_total
    except Exception as e:
        logger.error(f"[簽到系統] 增加積分失敗: {e}")
        return 0
    finally:
        conn.close()


def get_points_leaderboard(top_n: int = 10) -> list[dict]:
    """取得積分排行榜"""
    conn = _get_conn()
    try:
        rows = conn.execute("""
            SELECT user_id, username, full_name, total_points,
                   checkin_streak, total_checkins, correct_predictions
            FROM user_points
            ORDER BY total_points DESC
            LIMIT ?
        """, (top_n,)).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"[簽到系統] 排行榜查詢失敗: {e}")
        return []
    finally:
        conn.close()


def get_user_points_info(user_id: int) -> dict | None:
    """取得個人積分資訊"""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM user_points WHERE user_id=?", (user_id,)
        ).fetchone()
        if row:
            # 計算排名
            rank = conn.execute(
                "SELECT COUNT(*) as cnt FROM user_points WHERE total_points > ?",
                (row["total_points"],)
            ).fetchone()["cnt"] + 1
            result = dict(row)
            result["rank"] = rank
            return result
        return None
    except Exception as e:
        logger.error(f"[簽到系統] 個人積分查詢失敗: {e}")
        return None
    finally:
        conn.close()


def format_checkin_message(result: dict) -> str:
    """格式化簽到結果訊息"""
    if result["already_checked"]:
        return (
            "📋 今日已簽到\n\n"
            f"🔥 連續簽到：{result['streak']} 天\n"
            f"💰 目前積分：{result['total_points']} 分\n\n"
            "明天記得再來簽到喔！"
        )

    if result["success"]:
        streak = result["streak"]
        # 連續簽到 emoji
        if streak >= 30:
            streak_emoji = "👑"
            streak_text = f"連續 {streak} 天（傳說級！）"
        elif streak >= 14:
            streak_emoji = "🔥"
            streak_text = f"連續 {streak} 天（超強！）"
        elif streak >= 7:
            streak_emoji = "⭐"
            streak_text = f"連續 {streak} 天（厲害！）"
        elif streak >= 3:
            streak_emoji = "✨"
            streak_text = f"連續 {streak} 天"
        else:
            streak_emoji = "📌"
            streak_text = f"第 {streak} 天"

        msg = (
            "✅ 簽到成功！\n\n"
            f"{streak_emoji} {streak_text}\n"
            f"💰 獲得 +{result['points_earned']} 積分\n"
            f"🏦 目前總積分：{result['total_points']} 分\n"
        )

        # 連續簽到提示
        if streak == 2:
            msg += "\n💡 連續簽到 3 天可獲得額外 5 分加成！"
        elif streak == 6:
            msg += "\n💡 明天就連續 7 天了，額外 10 分加成！"
        elif streak == 13:
            msg += "\n💡 明天就連續 14 天了，額外 15 分加成！"
        elif streak == 29:
            msg += "\n💡 明天就連續 30 天了，額外 20 分加成！"

        return msg

    return f"簽到失敗：{result['message']}"


def format_leaderboard(leaderboard: list[dict]) -> str:
    """格式化積分排行榜"""
    if not leaderboard:
        return "🏆 積分排行榜\n\n目前還沒有人上榜，快來簽到和預測吧！"

    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 LA1 積分排行榜 Top 10\n"]

    for i, user in enumerate(leaderboard):
        rank_icon = medals[i] if i < 3 else f"#{i+1}"
        name = user.get("username") or user.get("full_name") or f"用戶{user['user_id']}"
        if name.startswith("@"):
            display_name = name
        else:
            display_name = name[:10]

        pts = user["total_points"]
        streak = user.get("checkin_streak", 0)
        streak_icon = "🔥" if streak >= 7 else ""

        lines.append(f"{rank_icon} {display_name} — {pts} 分 {streak_icon}")

    lines.append("\n💡 簽到 /checkin | 預測 /predict | 我的積分 /myscore")
    return "\n".join(lines)


def format_user_score(info: dict) -> str:
    """格式化個人積分資訊"""
    if not info:
        return "📊 你還沒有積分記錄\n\n快來 /checkin 簽到開始累積吧！"

    name = info.get("username") or info.get("full_name") or "你"
    return (
        f"📊 {name} 的積分資訊\n\n"
        f"🏅 排名：第 {info['rank']} 名\n"
        f"💰 總積分：{info['total_points']} 分\n"
        f"📅 簽到天數：{info['total_checkins']} 天\n"
        f"🔥 連續簽到：{info['checkin_streak']} 天\n"
        f"🎯 預測猜對：{info['correct_predictions']} 次\n"
        f"\n💡 每日簽到 /checkin | 積分排行 /rank"
    )
