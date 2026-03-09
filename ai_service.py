import json
from pathlib import Path
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL, GAME_URL_TW, GAME_URL_U, HUMAN_SUPPORT, BUSINESS_CONTACT

BASE = Path(__file__).resolve().parent
FAQ_PATH = BASE / "knowledge" / "faq.json"
POLICY_PATH = BASE / "knowledge" / "policies.json"

with open(FAQ_PATH, "r", encoding="utf-8") as f:
    FAQ = json.load(f)["items"]

with open(POLICY_PATH, "r", encoding="utf-8") as f:
    POLICIES = json.load(f)["rules"]

client = OpenAI(api_key=OPENAI_API_KEY)

HUMAN_KEYWORDS = [
    "提款未到", "提現未到", "儲值未到", "充值未到", "帳號異常", "登入不了",
    "忘記密碼", "改銀行", "修改銀行", "退款", "驗證", "審核", "補分", "沒到帳", "凍結", "封鎖"
]

BUSINESS_KEYWORDS = ["代理", "合作", "招商", "加盟", "商務", "廠商"]

def _render(text: str) -> str:
    return text.format(
        GAME_URL_TW=GAME_URL_TW,
        GAME_URL_U=GAME_URL_U,
        HUMAN_SUPPORT=HUMAN_SUPPORT,
        BUSINESS_CONTACT=BUSINESS_CONTACT
    )

def match_faq(user_text: str):
    msg = user_text.lower().strip()
    for item in FAQ:
        for kw in item["keywords"]:
            if kw.lower() in msg:
                return _render(item["answer"])
    return None

def need_human(user_text: str) -> bool:
    msg = user_text.lower()
    return any(k.lower() in msg for k in HUMAN_KEYWORDS)

def need_business(user_text: str) -> bool:
    msg = user_text.lower()
    return any(k.lower() in msg for k in BUSINESS_KEYWORDS)

async def ai_reply(user_text: str) -> str:
    if need_business(user_text):
        return f"老闆您好 👋\n\n商務合作 / 代理合作請聯繫：\n\n🤝 {BUSINESS_CONTACT}"

    if need_human(user_text):
        return f"老闆您好 🙏\n\n此問題需要真人客服協助處理。\n\n👑 客服：{HUMAN_SUPPORT}"

    faq_answer = match_faq(user_text)
    if faq_answer:
        return faq_answer

    system_prompt = f'''
你是 LA1 娛樂平台智能客服。

要求：
1. 自動識別用戶語言並用相同語言回答
2. 中文時稱呼用戶為「老闆」，英文可用 Boss
3. 簡短、清楚、像真人客服
4. 不要亂編資料
5. 涉及帳戶、提款未到、儲值未到、驗證、退款、修改銀行時，請建議聯繫真人客服：{HUMAN_SUPPORT}
6. 商務合作、代理合作請引導：{BUSINESS_CONTACT}

平台入口：
🇹🇼 台站：{GAME_URL_TW}
🌏 U站：{GAME_URL_U}

平台規則：
{chr(10).join("- " + p for p in POLICIES)}
'''

    try:
        res = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role":"system","content":system_prompt},
                {"role":"user","content":user_text}
            ]
        )
        return res.choices[0].message.content
    except Exception:
        return f"老闆您好 🙏\n\n系統目前繁忙，請稍後再試。\n如需即時協助，請聯繫真人客服：{HUMAN_SUPPORT}"
