"""
539 彩票資料庫 - 整合版
使用獨立的 lottery.db，存放在 sports-bot 根目錄
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

# lottery.db 放在 sports-bot 根目錄（與 user_preferences.db 同層）
DB_PATH = Path(__file__).resolve().parent.parent.parent / "lottery.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def transaction():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """初始化 539 彩票資料庫表"""
    with transaction() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                balance INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                last_daily_claim_date TEXT,
                last_chat_bonus_date TEXT
            );

            CREATE TABLE IF NOT EXISTS draws (
                draw_id INTEGER PRIMARY KEY AUTOINCREMENT,
                draw_date TEXT NOT NULL UNIQUE,
                draw_time TEXT NOT NULL,
                winning_numbers TEXT,
                status TEXT NOT NULL DEFAULT 'OPEN',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS bets (
                bet_id INTEGER PRIMARY KEY AUTOINCREMENT,
                draw_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                numbers TEXT NOT NULL,
                cost INTEGER NOT NULL,
                match_count INTEGER,
                prize INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(draw_id) REFERENCES draws(draw_id),
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS transactions (
                tx_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                tx_type TEXT NOT NULL,
                amount INTEGER NOT NULL,
                balance_after INTEGER NOT NULL,
                note TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            );

            CREATE INDEX IF NOT EXISTS idx_bets_draw_user ON bets(draw_id, user_id);
            CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id);
            """
        )

    # 遷移：為舊資料庫加入 last_chat_bonus_date 欄位
    try:
        with transaction() as conn:
            conn.execute("ALTER TABLE users ADD COLUMN last_chat_bonus_date TEXT")
    except Exception:
        pass  # 欄位已存在
