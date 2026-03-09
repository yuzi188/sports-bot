"""
config.py - LA1 Bot 配置
V20.20 修復：validate_config 不再因 OPENAI_API_KEY 缺失而 raise RuntimeError
"""
import os
import logging

logger = logging.getLogger(__name__)

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

# ESPN API 基礎 URL
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"


def validate_config():
    """
    驗證必要設定。
    - BOT_TOKEN 缺失：raise RuntimeError（Bot 無法運作）
    - OPENAI_API_KEY 缺失：僅印警告，不崩潰（AI 功能降級為 FAQ 回覆）
    """
    if not BOT_TOKEN:
        raise RuntimeError("Missing required environment variable: BOT_TOKEN")
    if not OPENAI_API_KEY:
        logger.warning("⚠️  OPENAI_API_KEY 未設定，AI 功能將降級使用 FAQ 回覆")
    else:
        logger.info("✅ OPENAI_API_KEY 已設定")
