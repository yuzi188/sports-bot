"""
ai_service.py - LA1 智能客服 AI 模組
V20.20 修復：knowledge/faq.json 和 policies.json 不存在時自動建立，不崩潰
"""
import json
import logging
from pathlib import Path
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL, GAME_URL_TW, GAME_URL_U, HUMAN_SUPPORT, BUSINESS_CONTACT

logger = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parent
KNOWLEDGE_DIR = BASE / "knowledge"
FAQ_PATH = KNOWLEDGE_DIR / "faq.json"
POLICY_PATH = KNOWLEDGE_DIR / "policies.json"

# ── 預設 FAQ 內容（當 faq.json 不存在時使用）──
_DEFAULT_FAQ = {
    "items": [
        {
            "keywords": ["儲值", "充值", "加值", "入金"],
            "answer": "老闆您好，請問您是要詢問哪種儲值方式呢？\n\n💡 常見儲值方式：\n• 銀行轉帳\n• 超商代碼支付（10-20分鐘自動上分）\n• USDT（需提供明細給客服手動上分）\n\n如需協助請聯繫客服：{HUMAN_SUPPORT}"
        },
        {
            "keywords": ["提款", "提現", "出金", "託售"],
            "answer": "老闆您好，關於提現 / 託售問題：\n\n📌 託售規則：\n• 單筆 1,000–5,000（整百）：不限銀行、不限次數\n• 單筆 5,100–30,000（整百）：每日一筆\n\n請聯繫客服協助：{HUMAN_SUPPORT}"
        },
        {
            "keywords": ["超商", "便利商店", "7-11", "全家"],
            "answer": "老闆您好，超商代碼支付約 10–20 分鐘會自動上分，請耐心等候即可。\n\n如超過 30 分鐘未到帳，請聯繫客服：{HUMAN_SUPPORT}"
        },
        {
            "keywords": ["usdt", "u幣", "泰達幣", "虛擬貨幣"],
            "answer": "老闆您好！儲值 USDT 需前往 U 站進行操作 🎰\n\n👉 {GAME_URL_U}\n\n儲值後請提供 TXID / 交易明細給客服上分：{HUMAN_SUPPORT}"
        },
        {
            "keywords": ["客服", "人工", "聯繫"],
            "answer": "老闆您好，VIP 客服專員：{HUMAN_SUPPORT}\n\n客服人員 7×24 小時在線為您服務！😊"
        },
        {
            "keywords": ["遊戲", "進入遊戲", "平台", "娛樂城"],
            "answer": "老闆您好，合作遊戲平台：\n\n🇹🇼 台站：{GAME_URL_TW}\n🌏 U站：{GAME_URL_U}"
        },
        {
            "keywords": ["代理", "合作", "招商", "加盟"],
            "answer": "老闆您好 👋\n\n商務合作 / 代理合作請聯繫：\n\n🤝 {BUSINESS_CONTACT}"
        }
    ]
}

# ── 預設 policies 內容（當 policies.json 不存在時使用）──
_DEFAULT_POLICIES = {
    "rules": [
        "一位會員僅可使用一組帳號",
        "本平台僅提供年滿 18 歲會員使用",
        "USDT 儲值需提供 TXID 給客服手動上分",
        "超商代碼支付約 10-20 分鐘自動上分",
        "託售單筆 1,000-5,000 不限次數；5,100-30,000 每日一筆"
    ]
}


def _load_json_safe(path: Path, default: dict) -> dict:
    """安全讀取 JSON 檔案，不存在時自動建立並回傳預設值"""
    if not path.exists():
        logger.warning(f"[ai_service] {path} 不存在，自動建立預設內容")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(default, f, ensure_ascii=False, indent=2)
            logger.info(f"[ai_service] 已建立 {path}")
        except Exception as e:
            logger.error(f"[ai_service] 建立 {path} 失敗: {e}")
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"[ai_service] 讀取 {path} 失敗: {e}，使用預設值")
        return default


# ── 安全載入知識庫（不存在時使用預設值，不崩潰）──
_faq_data = _load_json_safe(FAQ_PATH, _DEFAULT_FAQ)
FAQ = _faq_data.get("items", [])

_policy_data = _load_json_safe(POLICY_PATH, _DEFAULT_POLICIES)
POLICIES = _policy_data.get("rules", [])

# ── 初始化 OpenAI 客戶端（OPENAI_API_KEY 缺失時不崩潰）──
client = None
if OPENAI_API_KEY:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        logger.info("[ai_service] OpenAI 客戶端初始化成功")
    except Exception as e:
        logger.error(f"[ai_service] OpenAI 初始化失敗: {e}")
else:
    logger.warning("[ai_service] OPENAI_API_KEY 未設定，AI 功能將使用 FAQ 回覆")

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
        for kw in item.get("keywords", []):
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

    # 如果 OpenAI 客戶端未初始化，回傳友好提示
    if client is None:
        return f"老闆您好 👋\n\n請問有什麼可以幫您的？\n\n如有帳號或遊戲問題，歡迎聯繫客服：{HUMAN_SUPPORT}"

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
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ]
        )
        return res.choices[0].message.content
    except Exception as e:
        logger.error(f"[ai_service] OpenAI 呼叫失敗: {e}")
        return f"老闆您好 🙏\n\n系統目前繁忙，請稍後再試。\n如需即時協助，請聯繫真人客服：{HUMAN_SUPPORT}"
