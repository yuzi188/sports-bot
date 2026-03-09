import requests
import json

BOT_TOKEN = "8796143383:AAFMOZcc5yJO0GjRpPuDH40F1HTn0x7RCus"
CHANNEL_ID = "@LA11118"
VIDEO_URL = "https://files.manuscdn.com/user_upload_by_module/session_file/310419663032670396/zOYpATipTMNEkuCQ.mp4"

reply_markup = {
    "inline_keyboard": [
        [
            {"text": "🇹🇼 台站｜立即註冊", "url": "http://La1111.meta1788.com"},
            {"text": "🇭🇰🇲🇾🇲🇴🇻🇳 U站｜USDT專區", "url": "http://la1111.ofa168kh.com"}
        ],
        [
            {"text": "🇰🇭 代理入口", "url": "http://agent.ofa168kh.com"}
        ],
        [
            {"text": "🆕 免費開戶註冊", "url": "http://La1111.meta1788.com"}
        ],
        [
            {"text": "🎁 優惠領取｜聯絡客服", "url": "https://t.me/yu_888yu"}
        ],
        [
            {"text": "🤝 商務合作", "url": "https://t.me/OFA168Abe1"}
        ],
        [
            {"text": "🎮 立即進入遊戲", "url": "http://la1111.ofa168kh.com/"}
        ]
    ]
}

caption = "🏆 LA1 智能體育服務平台\n\n🔥 最專業的體育分析，最即時的比分數據！\n立即點擊下方按鈕開始體驗 👇"

api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
payload = {
    "chat_id": CHANNEL_ID,
    "video": VIDEO_URL,
    "caption": caption,
    "reply_markup": json.dumps(reply_markup)
}

try:
    resp = requests.post(api_url, json=payload, timeout=30)
    result = resp.json()
    if result.get("ok"):
        print("✅ 頻道影片推播成功")
        print(f"Message ID: {result['result']['message_id']}")
    else:
        print(f"❌ 頻道影片推播失敗: {result.get('description')}")
except Exception as e:
    print(f"❌ 頻道影片推播異常: {e}")
