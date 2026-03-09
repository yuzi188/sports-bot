"""
539 彩票工具函數 - 整合版
"""
from __future__ import annotations

from datetime import datetime, timedelta
import pytz

from modules.lottery.lottery_config import lottery_settings


def tz_now() -> datetime:
    return datetime.now(pytz.timezone(lottery_settings.timezone))


def today_str() -> str:
    return tz_now().strftime("%Y-%m-%d")


def parse_numbers(parts: list[str]) -> list[int]:
    if len(parts) != 5:
        raise ValueError("請輸入 5 個號碼，例如 /539 03 08 12 25 37")

    nums: list[int] = []
    for p in parts:
        if not p.isdigit():
            raise ValueError("號碼必須是數字")
        n = int(p)
        if not (1 <= n <= 39):
            raise ValueError("號碼必須介於 1 到 39")
        nums.append(n)

    if len(set(nums)) != 5:
        raise ValueError("5 個號碼不能重複")

    return sorted(nums)


def numbers_to_text(numbers: list[int]) -> str:
    return " ".join(f"{n:02d}" for n in sorted(numbers))


def next_draw_datetime() -> datetime:
    now = tz_now()
    target = now.replace(
        hour=lottery_settings.draw_hour,
        minute=lottery_settings.draw_minute,
        second=0,
        microsecond=0,
    )
    if now >= target:
        target = target + timedelta(days=1)
    return target


def is_bet_open() -> tuple[bool, str]:
    now = tz_now()
    draw_dt = now.replace(
        hour=lottery_settings.draw_hour,
        minute=lottery_settings.draw_minute,
        second=0,
        microsecond=0,
    )
    cutoff = draw_dt - timedelta(minutes=lottery_settings.bet_cutoff_minutes)
    if now >= draw_dt:
        return False, "今日已開獎，請等待下一期。"
    if now >= cutoff:
        return False, f'本期已截止下注，截止時間為 {cutoff.strftime("%H:%M")}'
    return True, ""
