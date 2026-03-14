import requests
import json

BOT_TOKEN = "8796143383:AAFMOZcc5yJO0GjRpPuDH40F1HTn0x7RCus"
CHANNEL_ID = "@LA11118"
PHOTO_URL = "https://files.manuscdn.com/user_upload_by_module/session_file/310419663032670396/uMIZnqkFFmBSSHII.jpg"

caption = """【WBC連勝王挑戰開啟】

場場開轟，連勝封神！

賽事期間連續過關達標
即可領取專屬彩金獎勵
💰 最高 888U，一棒帶走！

連贏越多，獎勵越高！
敢挑戰嗎？王者等你加冕！
連勝不斷，榮耀屬於強者！

📅 活動時間：3/5 – 3/18
🎯 僅限賽前投注 WBC 讓分盤口

👉 立即加入
📢 LA1 官方頻道：@LA11118
👥 LA1 VIP客服：@yu_888yu"""

reply_markup = {
    "inline_keyboard": [
        [
            {"text": "🇹🇼 台站｜立即註冊", "url": "http://La1111.meta1788.com/"},
            {"text": "🇭🇰 U站｜USDT專區", "url": "http://la1111.ofa168kh.com/"}
        ],
        [
            {"text": "🇰🇭 代理入口", "url": "http://la1111.ofa168kh.com/"}
        ]
    ]
}

api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
payload = {
    "chat_id": CHANNEL_ID,
    "photo": PHOTO_URL,
    "caption": caption,
    "reply_markup": json.dumps(reply_markup)
}

try:
    resp = requests.post(api_url, json=payload, timeout=30)
    result = resp.json()
    if result.get("ok"):
        print("✅ 頻道活動貼文發送成功")
        print(f"Message ID: {result['result']['message_id']}")
    else:
        print(f"❌ 頻道活動貼文發送失敗: {result.get('description')}")
except Exception as e:
    print(f"❌ 頻道活動貼文發送異常: {e}")
