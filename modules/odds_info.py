"""
賠率資訊模組 - 從 ESPN 免費 API 提取賠率/盤口資訊
ESPN 部分賽事會附帶 odds 資訊（免費）
"""

import requests
from datetime import datetime
import pytz
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ESPN_BASE, TIMEZONE
from smart_search import translate_name

tz = pytz.timezone(TIMEZONE)


def get_odds_for_event(event: dict) -> dict:
    """從 ESPN event 中提取賠率資訊"""
    comp = event.get("competitions", [{}])[0]
    odds_list = comp.get("odds", [])

    if not odds_list:
        return {}

    odds = odds_list[0]
    result = {}

    # 盤口
    details = odds.get("details", "")
    if details:
        result["spread"] = details

    # 大小分
    over_under = odds.get("overUnder")
    if over_under:
        result["over_under"] = str(over_under)

    # 提供者
    provider = odds.get("provider", {}).get("name", "")
    if provider:
        result["provider"] = provider

    return result


def format_odds(odds: dict) -> str:
    """格式化賠率資訊"""
    if not odds:
        return ""

    lines = []
    if odds.get("spread"):
        lines.append(f"💰 盤口：{odds['spread']}")
    if odds.get("over_under"):
        lines.append(f"📏 大小分：{odds['over_under']}")
    if odds.get("provider"):
        lines.append(f"📊 來源：{odds['provider']}")

    return "\n".join(lines)
