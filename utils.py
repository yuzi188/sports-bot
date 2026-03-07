"""
V5.2 工具模組 - 統一的 logger、send_message、format_message
"""

import logging
import requests
import time
import pytz
from config import BOT_TOKEN, CHANNEL_ID, TIMEZONE

TZ = pytz.timezone(TIMEZONE)

# Logger
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("sports_bot")

API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_message(text: str, channel: str = None, parse_mode: str = None):
    """發送訊息到頻道"""
    chat_id = channel or CHANNEL_ID
    url = f"{API_BASE}/sendMessage"

    # 如果訊息太長，分段發送
    if len(text) > 4000:
        return _send_long(text, chat_id, parse_mode)

    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        resp = requests.post(url, json=payload, timeout=15)
        result = resp.json()
        if not result.get("ok"):
            desc = result.get("description", "")
            logger.error(f"Send failed: {desc}")
            if "too long" in desc.lower():
                return _send_long(text, chat_id, parse_mode)
        return result
    except Exception as e:
        logger.error(f"Send error: {e}")
        return {"ok": False}


def _send_long(text: str, chat_id: str, parse_mode: str = None):
    """分段發送長訊息"""
    parts = []
    while text:
        if len(text) <= 4000:
            parts.append(text)
            break
        pos = text.rfind("\n", 0, 4000)
        if pos == -1:
            pos = 4000
        parts.append(text[:pos])
        text = text[pos:].lstrip("\n")

    last = {}
    for i, part in enumerate(parts):
        if i > 0:
            time.sleep(1)
        payload = {
            "chat_id": chat_id,
            "text": part,
            "disable_web_page_preview": True,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        try:
            resp = requests.post(f"{API_BASE}/sendMessage", json=payload, timeout=15)
            last = resp.json()
        except Exception as e:
            logger.error(f"Send part error: {e}")
    return last


def format_message(title: str, items, analysis: str = "") -> str:
    """統一格式化訊息"""
    sep = "═" * 24
    dash = "─" * 20

    lines = [sep, f"{title}", sep, ""]

    if isinstance(items, list):
        for item in items:
            if isinstance(item, str):
                lines.append(item)
            elif isinstance(item, dict):
                lines.append(_format_item(item))
            lines.append("")
    elif isinstance(items, str):
        lines.append(items)
        lines.append("")

    if analysis:
        lines.extend([dash, "🤖 AI 分析", dash, "", analysis, ""])

    lines.extend([sep, "📡 世界體育數據室", "⚠️ 分析僅供參考"])
    return "\n".join(lines)


def _format_item(item: dict) -> str:
    """格式化單個項目"""
    parts = []
    for k, v in item.items():
        parts.append(f"{k}: {v}")
    return " | ".join(parts)
