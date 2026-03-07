"""
Telegram 訊息發送模組
"""

import requests
import time
from config import BOT_TOKEN, CHANNEL_ID


API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_message(text: str, parse_mode: str = None, disable_preview: bool = True) -> dict:
    """發送文字訊息到頻道"""
    url = f"{API_BASE}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "disable_web_page_preview": disable_preview,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    
    try:
        resp = requests.post(url, json=payload, timeout=10)
        result = resp.json()
        if not result.get("ok"):
            print(f"Send failed: {result.get('description', 'Unknown error')}")
            # 如果是訊息太長，分段發送
            if "message is too long" in result.get("description", "").lower():
                return send_long_message(text, parse_mode, disable_preview)
        return result
    except Exception as e:
        print(f"Send error: {e}")
        return {"ok": False, "error": str(e)}


def send_long_message(text: str, parse_mode: str = None, disable_preview: bool = True) -> dict:
    """分段發送長訊息"""
    max_len = 4000
    parts = []
    
    while text:
        if len(text) <= max_len:
            parts.append(text)
            break
        
        # 找到最近的換行符
        split_pos = text.rfind("\n", 0, max_len)
        if split_pos == -1:
            split_pos = max_len
        
        parts.append(text[:split_pos])
        text = text[split_pos:].lstrip("\n")
    
    last_result = {}
    for i, part in enumerate(parts):
        if i > 0:
            time.sleep(1)  # 避免發送太快
        last_result = send_message(part, parse_mode, disable_preview)
    
    return last_result


def send_photo(photo_url: str, caption: str = "", parse_mode: str = None) -> dict:
    """發送圖片到頻道"""
    url = f"{API_BASE}/sendPhoto"
    payload = {
        "chat_id": CHANNEL_ID,
        "photo": photo_url,
        "caption": caption,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    
    try:
        resp = requests.post(url, json=payload, timeout=10)
        return resp.json()
    except Exception as e:
        print(f"Send photo error: {e}")
        return {"ok": False, "error": str(e)}


def pin_message(message_id: int) -> dict:
    """置頂訊息"""
    url = f"{API_BASE}/pinChatMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "message_id": message_id,
        "disable_notification": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        return resp.json()
    except Exception as e:
        print(f"Pin error: {e}")
        return {"ok": False, "error": str(e)}


def test_connection() -> bool:
    """測試機器人連接"""
    url = f"{API_BASE}/getMe"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get("ok"):
            bot_info = data["result"]
            print(f"✅ Bot connected: @{bot_info.get('username', '')} ({bot_info.get('first_name', '')})")
            return True
        return False
    except Exception as e:
        print(f"Connection test failed: {e}")
        return False


if __name__ == "__main__":
    test_connection()
