"""
AI 客服模組（LA智能完善版2 整合版）
V20.21:
- 優先使用 knowledge/faq.json FAQ 知識庫回覆
- FAQ 未命中時呼叫 OpenAI GPT 回覆
- OPENAI_API_KEY 未設定時降級為友好訊息，不崩潰
- faq.json / policies.json 不存在時自動建立預設內容，不崩潰
"""
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

BASE        = Path(__file__).resolve().parent
FAQ_PATH    = BASE / "knowledge" / "faq.json"
POLICY_PATH = BASE / "knowledge" / "policies.json"

# ── 預設 FAQ（faq.json 不存在時使用）──
_DEFAULT_FAQ = {
    "items": [
        {
            "intent": "register",
            "keywords": ["註冊", "開戶", "如何註冊", "如何開戶", "我要註冊", "加入"],
            "answer": "老闆您好 👋\n\n請使用以下入口註冊：\n\n🇹🇼 台站\n{GAME_URL_TW}\n\n🌏 U站（香港 / 馬來 / 澳門 / 越南）\n{GAME_URL_U}\n\n如需協助請聯繫客服：{HUMAN_SUPPORT}"
        },
        {
            "intent": "deposit",
            "keywords": ["儲值", "充值", "上分", "入金", "存款"],
            "answer": "老闆您好 👋\n\n儲值 / 上分問題請聯繫客服協助處理：\n\n👑 客服：{HUMAN_SUPPORT}"
        },
        {
            "intent": "withdraw",
            "keywords": ["提款", "提現", "託售", "託售點數", "出金"],
            "answer": "老闆您好 👋\n\n提款 / 託售點數相關問題請聯繫客服協助處理：\n\n👑 客服：{HUMAN_SUPPORT}"
        },
        {
            "intent": "cooperation",
            "keywords": ["代理", "合作", "商務", "加盟", "招商", "廠商"],
            "answer": "老闆您好 👋\n\n商務合作 / 代理合作請聯繫：\n\n🤝 {BUSINESS_CONTACT}"
        },
        {
            "intent": "games",
            "keywords": ["遊戲", "有什麼遊戲", "可以玩什麼", "遊戲種類", "遊戲推薦"],
            "answer": "老闆您好 👋\n\n平台提供多種熱門遊戲：\n\n🎰 電子遊戲\n⚽ 體育博彩\n🎲 真人娛樂\n🃏 棋牌遊戲\n\n入口如下：\n🇹🇼 台站：{GAME_URL_TW}\n🌏 U站：{GAME_URL_U}"
        },
        {
            "intent": "promotion",
            "keywords": ["優惠", "活動", "首儲", "紅利", "促銷", "有優惠嗎"],
            "answer": "老闆您好 👋\n\n目前平台活動：\n\n🔥 首儲1000送1000（限時）\n\n如需了解活動詳情，請聯繫客服：{HUMAN_SUPPORT}"
        },
        {
            "intent": "support",
            "keywords": ["客服", "真人客服", "找客服", "聯繫客服", "在嗎"],
            "answer": "老闆您好 👋\n\n真人客服聯繫方式：\n\n👑 {HUMAN_SUPPORT}"
        },
        {
            "intent": "app",
            "keywords": ["app", "下載", "要下載嗎"],
            "answer": "老闆您好 👋\n\n平台目前以網頁方式使用，無需下載 APP，直接開啟連結即可進入。\n\n🇹🇼 台站：{GAME_URL_TW}\n🌏 U站：{GAME_URL_U}"
        },
    ]
}

_DEFAULT_POLICIES = {
    "rules": [
        "一位會員僅可使用一組帳號進行操作。",
        "未滿18歲不得通過驗證。",
        "涉及帳戶、提款未到、儲值未到、修改銀行、驗證資料、退款等問題，一律轉真人客服。",
        "平台資訊以官方客服與公告為準，AI 不可承諾未確認的結果。",
        "如問題不明確，先禮貌詢問補充資訊。"
    ]
}


def _load_json_safe(path: Path, default: dict) -> dict:
    """安全讀取 JSON 檔案，不存在時自動建立並回傳預設值。"""
    if not path.exists():
        logger.warning(f"[ai_service] {path} 不存在，自動建立預設內容")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"[ai_service] 讀取 {path} 失敗: {e}，使用預設值")
        return default


# ── 載入知識庫（安全讀取，不崩潰）──
_faq_data    = _load_json_safe(FAQ_PATH, _DEFAULT_FAQ)
_policy_data = _load_json_safe(POLICY_PATH, _DEFAULT_POLICIES)

FAQ      = _faq_data.get("items", [])
POLICIES = _policy_data.get("rules", [])


# ── 延遲初始化 OpenAI 客戶端 ──
_openai_client = None


def _get_openai_client():
    """取得 OpenAI 客戶端，OPENAI_API_KEY 未設定時回傳 None（不崩潰）。"""
    global _openai_client
    if _openai_client is None:
        from config import OPENAI_API_KEY
        if not OPENAI_API_KEY:
            logger.warning("[ai_service] OPENAI_API_KEY 未設定，AI 功能降級為 FAQ 回覆")
            return None
        try:
            from openai import OpenAI
            _openai_client = OpenAI(api_key=OPENAI_API_KEY)
        except Exception as e:
            logger.error(f"[ai_service] OpenAI 初始化失敗: {e}")
            return None
    return _openai_client


HUMAN_KEYWORDS = [
    "提款未到", "提現未到", "儲值未到", "充值未到", "帳號異常", "登入不了",
    "忘記密碼", "改銀行", "修改銀行", "退款", "驗證", "審核", "補分",
    "沒到帳", "凍結", "封鎖",
]

BUSINESS_KEYWORDS = ["代理", "合作", "招商", "加盟", "商務", "廠商"]


def _render(text: str) -> str:
    """將 FAQ 回覆中的佔位符替換為實際 URL。"""
    from config import GAME_URL_TW, GAME_URL_U, HUMAN_SUPPORT, BUSINESS_CONTACT
    return text.format(
        GAME_URL_TW=GAME_URL_TW,
        GAME_URL_U=GAME_URL_U,
        HUMAN_SUPPORT=HUMAN_SUPPORT,
        BUSINESS_CONTACT=BUSINESS_CONTACT,
    )


def match_faq(user_text: str):
    """關鍵字比對 FAQ，命中則回傳回覆，否則回傳 None。"""
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
    """
    主要 AI 客服回覆函數。
    優先順序：商務合作 → 人工客服 → FAQ → GPT → 降級訊息
    """
    from config import HUMAN_SUPPORT, BUSINESS_CONTACT

    if need_business(user_text):
        return f"老闆您好 👋\n\n商務合作 / 代理合作請聯繫：\n\n🤝 {BUSINESS_CONTACT}"

    if need_human(user_text):
        return f"老闆您好 🙏\n\n此問題需要真人客服協助處理。\n\n👑 客服：{HUMAN_SUPPORT}"

    faq_answer = match_faq(user_text)
    if faq_answer:
        return faq_answer

    # ── 呼叫 GPT ──
    client = _get_openai_client()
    if client is None:
        return f"老闆您好，請問有什麼可以幫您的？如有帳號或遊戲問題，歡迎聯繫客服 {HUMAN_SUPPORT}"

    from config import OPENAI_MODEL, GAME_URL_TW, GAME_URL_U

    system_prompt = f"""你是 LA1 娛樂平台智能客服。

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
"""

    try:
        res = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            max_tokens=500,
            temperature=0.7,
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"[ai_service] GPT 呼叫失敗: {e}")
        return f"老闆您好 🙏\n\n系統目前繁忙，請稍後再試。\n如需即時協助，請聯繫真人客服：{HUMAN_SUPPORT}"
