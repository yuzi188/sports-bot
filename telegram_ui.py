from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import GAME_URL_TW, GAME_URL_U, HUMAN_SUPPORT, AGENT_URL_KH, BUSINESS_CONTACT

def main_menu():
    keyboard = [
        [InlineKeyboardButton("🎮 台站入口", url=GAME_URL_TW)],
        [InlineKeyboardButton("🌏 U站入口", url=GAME_URL_U)],
        [InlineKeyboardButton("👑 真人客服", url=f"https://t.me/{HUMAN_SUPPORT.lstrip('@')}")],
        [InlineKeyboardButton("🇰🇭 代理入口", url=AGENT_URL_KH)],
        [InlineKeyboardButton("🤝 商務合作", url=f"https://t.me/{BUSINESS_CONTACT.lstrip('@')}")]
    ]
    return InlineKeyboardMarkup(keyboard)
