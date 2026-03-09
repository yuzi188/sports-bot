"""
539 彩票設定 - 整合版
從環境變數讀取，不使用獨立的 config.py
"""
import os


class LotterySettings:
    """539 彩票設定（整合到 sports-bot 架構）"""

    timezone: str = os.getenv("TIMEZONE", "Asia/Taipei")
    draw_hour: int = int(os.getenv("DRAW_HOUR", "20"))
    draw_minute: int = int(os.getenv("DRAW_MINUTE", "30"))
    bet_cutoff_minutes: int = int(os.getenv("BET_CUTOFF_MINUTES", "10"))
    starting_coins: int = int(os.getenv("STARTING_COINS", "100"))
    daily_bonus: int = int(os.getenv("DAILY_BONUS", "20"))
    chat_bonus: int = int(os.getenv("CHAT_BONUS", "10"))  # 每日群組說話獎勵
    bet_price: int = int(os.getenv("BET_PRICE", "10"))
    prize_match_2: int = int(os.getenv("PRIZE_MATCH_2", "20"))
    prize_match_3: int = int(os.getenv("PRIZE_MATCH_3", "200"))
    prize_match_4: int = int(os.getenv("PRIZE_MATCH_4", "2000"))
    prize_match_5: int = int(os.getenv("PRIZE_MATCH_5", "20000"))
    max_bets_per_draw: int = int(os.getenv("MAX_BETS_PER_DRAW", "50"))

    @property
    def prize_table(self) -> dict:
        return {
            2: self.prize_match_2,
            3: self.prize_match_3,
            4: self.prize_match_4,
            5: self.prize_match_5,
        }


lottery_settings = LotterySettings()
