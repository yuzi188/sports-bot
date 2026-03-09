"""
539 彩票資料庫操作 - 整合版
"""
from __future__ import annotations

from modules.lottery.db import transaction, get_conn
from modules.lottery.utils import today_str


def ensure_user(user_id: int, username: str | None, full_name: str, starting_coins: int, now_iso: str) -> bool:
    """確保用戶存在，不存在則建立並發放初始 L幣。回傳 True 表示新建。"""
    with transaction() as conn:
        row = conn.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if row:
            conn.execute(
                "UPDATE users SET username = ?, full_name = ? WHERE user_id = ?",
                (username, full_name, user_id),
            )
            return False

        conn.execute(
            """INSERT INTO users (user_id, username, full_name, balance, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, username, full_name, starting_coins, now_iso),
        )
        conn.execute(
            """INSERT INTO transactions (user_id, tx_type, amount, balance_after, note, created_at)
               VALUES (?, 'WELCOME', ?, ?, ?, ?)""",
            (user_id, starting_coins, starting_coins, "新用戶初始 L幣", now_iso),
        )
        return True


def get_user(user_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()


def get_or_create_today_draw(now_iso: str, draw_time: str):
    draw_date = today_str()
    with transaction() as conn:
        row = conn.execute("SELECT * FROM draws WHERE draw_date = ?", (draw_date,)).fetchone()
        if row:
            return row
        conn.execute(
            """INSERT INTO draws (draw_date, draw_time, status, created_at)
               VALUES (?, ?, 'OPEN', ?)""",
            (draw_date, draw_time, now_iso),
        )
        return conn.execute("SELECT * FROM draws WHERE draw_date = ?", (draw_date,)).fetchone()


def get_draw_by_date(draw_date: str):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM draws WHERE draw_date = ?", (draw_date,)).fetchone()


def count_user_bets(draw_id: int, user_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM bets WHERE draw_id = ? AND user_id = ?",
            (draw_id, user_id),
        ).fetchone()
        return int(row["c"])


def place_bet(draw_id: int, user_id: int, numbers_text: str, cost: int, note: str, now_iso: str):
    with transaction() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not user:
            raise ValueError("找不到玩家資料")
        if user["balance"] < cost:
            raise ValueError("L幣不足")

        new_balance = user["balance"] - cost
        conn.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
        conn.execute(
            """INSERT INTO bets (draw_id, user_id, numbers, cost, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (draw_id, user_id, numbers_text, cost, now_iso),
        )
        conn.execute(
            """INSERT INTO transactions (user_id, tx_type, amount, balance_after, note, created_at)
               VALUES (?, 'BET', ?, ?, ?, ?)""",
            (user_id, -cost, new_balance, note, now_iso),
        )
        return new_balance


def claim_daily_bonus(user_id: int, amount: int, claim_date: str, now_iso: str):
    """每日簽到。回傳新餘額，若已簽到過回傳 None。"""
    with transaction() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not user:
            raise ValueError("找不到玩家資料")
        if user["last_daily_claim_date"] == claim_date:
            return None
        new_balance = user["balance"] + amount
        conn.execute(
            "UPDATE users SET balance = ?, last_daily_claim_date = ? WHERE user_id = ?",
            (new_balance, claim_date, user_id),
        )
        conn.execute(
            """INSERT INTO transactions (user_id, tx_type, amount, balance_after, note, created_at)
               VALUES (?, 'DAILY', ?, ?, ?, ?)""",
            (user_id, amount, new_balance, "每日簽到", now_iso),
        )
        return new_balance


def claim_chat_bonus(user_id: int, username: str | None, full_name: str,
                     amount: int, starting_coins: int, now_iso: str) -> int | None:
    """
    每日群組說話獎勵。回傳新餘額，若今日已領過回傳 None。
    會自動 ensure_user。
    """
    ensure_user(user_id, username, full_name, starting_coins, now_iso)
    claim_date = today_str()
    with transaction() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not user:
            return None
        # sqlite3.Row 不支援 .get()，用 try/except 取得欄位
        try:
            last_chat_date = user["last_chat_bonus_date"]
        except (IndexError, KeyError):
            last_chat_date = None
        if last_chat_date == claim_date:
            return None  # 今日已領過
        new_balance = user["balance"] + amount
        conn.execute(
            "UPDATE users SET balance = ?, last_chat_bonus_date = ? WHERE user_id = ?",
            (new_balance, claim_date, user_id),
        )
        conn.execute(
            """INSERT INTO transactions (user_id, tx_type, amount, balance_after, note, created_at)
               VALUES (?, 'CHAT_BONUS', ?, ?, ?, ?)""",
            (user_id, amount, new_balance, "每日群組發言獎勵", now_iso),
        )
        return new_balance


def recent_bets(user_id: int, limit: int = 10):
    with get_conn() as conn:
        return conn.execute(
            """SELECT b.*, d.draw_date FROM bets b
               JOIN draws d ON b.draw_id = d.draw_id
               WHERE b.user_id = ?
               ORDER BY b.bet_id DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()


def leaderboard(limit: int = 10):
    with get_conn() as conn:
        return conn.execute(
            """SELECT full_name, username, balance FROM users
               ORDER BY balance DESC, user_id ASC LIMIT ?""",
            (limit,),
        ).fetchall()


def all_open_draw_bets(draw_id: int):
    with get_conn() as conn:
        return conn.execute(
            """SELECT b.*, u.username, u.full_name FROM bets b
               JOIN users u ON u.user_id = b.user_id
               WHERE b.draw_id = ?""",
            (draw_id,),
        ).fetchall()


def settle_draw(draw_id: int, winning_numbers_text: str, prize_table: dict, now_iso: str):
    winning_set = {int(x) for x in winning_numbers_text.split()}
    winners: list[dict] = []

    with transaction() as conn:
        draw = conn.execute("SELECT * FROM draws WHERE draw_id = ?", (draw_id,)).fetchone()
        if not draw:
            raise ValueError("draw not found")
        if draw["status"] == "DRAWN":
            return []

        bets = conn.execute(
            """SELECT b.*, u.balance, u.username, u.full_name
               FROM bets b JOIN users u ON u.user_id = b.user_id
               WHERE b.draw_id = ?""",
            (draw_id,),
        ).fetchall()

        for bet in bets:
            picked = {int(x) for x in bet["numbers"].split()}
            match_count = len(picked & winning_set)
            prize = prize_table.get(match_count, 0)
            conn.execute(
                "UPDATE bets SET match_count = ?, prize = ? WHERE bet_id = ?",
                (match_count, prize, bet["bet_id"]),
            )
            if prize > 0:
                new_balance = bet["balance"] + prize
                conn.execute(
                    "UPDATE users SET balance = ? WHERE user_id = ?",
                    (new_balance, bet["user_id"]),
                )
                conn.execute(
                    """INSERT INTO transactions (user_id, tx_type, amount, balance_after, note, created_at)
                       VALUES (?, 'PRIZE', ?, ?, ?, ?)""",
                    (bet["user_id"], prize, new_balance, f"539 對中 {match_count} 個", now_iso),
                )
                winners.append(
                    {
                        "user_id": bet["user_id"],
                        "username": bet["username"],
                        "full_name": bet["full_name"],
                        "match_count": match_count,
                        "prize": prize,
                    }
                )

        conn.execute(
            """UPDATE draws
               SET winning_numbers = ?, status = 'DRAWN'
               WHERE draw_id = ?""",
            (winning_numbers_text, draw_id),
        )

    return winners
