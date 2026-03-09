import time
import requests
from config import BOT_TOKEN, CHANNEL_ID

API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

def _post(endpoint: str, payload: dict):
    url = f"{API_BASE}/{endpoint}"
    for _ in range(5):
        try:
            r = requests.post(url, json=payload, timeout=15)
            if r.status_code == 200:
                return True
            if r.status_code == 429:
                retry_after = 3
                try:
                    retry_after = int(r.json().get("parameters", {}).get("retry_after", 3))
                except Exception:
                    pass
                time.sleep(retry_after)
                continue
            time.sleep(2)
        except Exception:
            time.sleep(2)
    return False

def send_message(text: str):
    if not CHANNEL_ID:
        return False
    return _post("sendMessage", {
        "chat_id": CHANNEL_ID,
        "text": text,
        "disable_web_page_preview": True
    })

def send_photo(photo_url: str, caption: str, reply_markup=None):
    if not CHANNEL_ID:
        return False
    payload = {
        "chat_id": CHANNEL_ID,
        "photo": photo_url,
        "caption": caption
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return _post("sendPhoto", payload)
