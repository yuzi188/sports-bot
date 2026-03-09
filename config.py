import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip()

GAME_URL_TW = os.getenv("GAME_URL_TW", "https://La1111.meta1788.com").strip()
GAME_URL_U = os.getenv("GAME_URL_U", "http://la1111.ofa168hk.com/").strip()
AGENT_URL_KH = os.getenv("AGENT_URL_KH", "https://agent.ofa168kh.com").strip()

HUMAN_SUPPORT = os.getenv("HUMAN_SUPPORT", "@yu_888yu").strip()
BUSINESS_CONTACT = os.getenv("BUSINESS_CONTACT", "@OFA168Abe1").strip()

TIMEZONE = os.getenv("TIMEZONE", "Asia/Taipei").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

def validate_config():
    missing = []
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")
    if missing:
        raise RuntimeError("Missing required environment variables: " + ", ".join(missing))
