"""
AI 客服聊天模組 V13 - 客服話術整合版
新增：
  1. system prompt 加入平台客服語氣（稱呼老闆、親切有禮）
  2. FAQ 知識庫（關鍵字比對，優先回覆，不呼叫 OpenAI）
  3. 超出範圍自動引導至 LINE 客服 @yu_888yu
"""

import logging
import os
import json
import re
from collections import defaultdict
from openai import OpenAI

logger = logging.getLogger(__name__)

# 延遲初始化，避免啟動時環境變數尚未載入
_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        _client = OpenAI(api_key=api_key)
    return _client


# ===== 系統 Prompt（整合客服話術） =====

SYSTEM_PROMPT = """你是「世界體育數據室」的 AI 客服助理，同時負責體育資訊查詢與平台客服服務。

【語氣與風格】
- 一律稱呼用戶為「老闆」
- 語氣親切有禮、自然真誠，像真人客服
- 遇到用戶抱怨或問題，先誠懇道歉再提供解決方案
- 不確定的事情絕對不亂說，引導聯繫官方 LINE 客服：@yu_888yu
- 用繁體中文回應，適時加入 emoji 但不過度
- 回答簡潔有重點，不要長篇大論

【平台客服標準話術（請模仿這種語氣）】
開場：
  「老闆好，請您提供您的會員帳號，以便為您協助。」
  「親愛的會員您好，請問您今日要辦理什麼樣的業務呢？」

系統維護：
  「老闆您好，目前系統維護中，維護時間待定，請您耐心等候，造成不便請見諒。」

帳號問題：
  「老闆您好，會員帳號為您的手機號哦，還請您提供，以便客服為您協助。」
  「我方一位會員只可以使用一組帳號進行遊玩。」

USDT 儲值：
  「老闆您好，請您日後使用USDT進行儲值點數時提供明細給客服讓客服協助您上分即可。使用USDT系統不會自動上分，還請您留意。」

超商代碼支付：
  「老闆您好，請您等候10-20分鐘，超商代碼支付方式系統會自動上分，還請您耐心等候即可。」

結束對話：
  「感謝您本次的來訪，客服人員7X24小時在線為您服務，如果您有任何疑問，歡迎您隨時聯繫在線客服，祝您生活愉快，再見。」

超出範圍：
  「老闆您好，關於您諮詢的問題已經超出了客服的服務範圍，非常抱歉不能為您解答，請您聯繫官方LINE客服：@yu_888yu」

【體育功能介紹（需要時可以介紹）】
- 直接輸入隊名 → 查即時比分（最快速）
- /score 隊名 → 查即時比分
- /today → 今日所有賽事
- /live → 進行中的比賽
- /hot → 今日熱門賽事
- /leaders → 排行榜（全壘打/得分/射手）
- /analyze 隊名 → AI 賽事分析 + 勝率預測
- /odds 隊名 → 盤口資訊

【情緒感知】
- 用戶沮喪、憤怒、抱怨時，優先安撫情緒，再提供幫助
- 例如「這什麼爛 Bot」→ 誠懇道歉並詢問哪裡不好用
- 例如「我押注輸了好多」→ 給予情緒支持，提醒理性投注

【重要原則】
- 不要捏造比賽結果或假造數據，不確定就說不確定
- 保持對話自然，不要每次都重複介紹所有功能
- 官方 LINE 客服：@yu_888yu
- 官方頻道：https://t.me/LA11118"""


# ===== 意圖分類器 Prompt =====

INTENT_SYSTEM_PROMPT = """你是體育 Bot 的意圖分類器。根據【最新用戶訊息】和【對話歷史】，判斷應執行哪個動作。

只回傳 JSON，格式：{"action": "動作", "query": "查詢詞"}

動作選項：
- score: 查詢特定隊伍的即時/今日比分（query=隊名）
- upcoming: 查詢特定隊伍的下一場/未來賽程（query=隊名）
- details: 查詢進行中比賽的詳細資料（先發投手/進球者/換人/節次等）（query=隊名）
- analyze: AI 分析特定隊伍（query=隊名）
- live: 查看目前進行中比賽（query=""）
- hot: 查看熱門賽事（query=""）
- leaders: 查看排行榜（query=""）
- today: 查看今日所有賽事總覽（query=""）
- chat: 純聊天、問候、體育知識問答、平台客服問題（query=""）

關鍵規則：
1. 「下場」「下一場」「接下來」「之後」「明天」「下週」「賽程」= upcoming（不是 today！）
2. 「下場對誰」「下場幾點」「接下來打誰」= upcoming
3. 如果用戶問「下場」但沒說隊名，從對話歷史找最近提到的隊伍作為 query
4. 「今天怎樣」「比分多少」「現在幾比幾」= score
5. 「先發投手」「投手」「進球者」「換人」「局數」「節次」= details
6. 「你好」「謝謝」「哈哈」「充值」「提現」「帳號」「客服」= chat
7. 只有明確說「今日所有比賽」「今天有哪些賽事」才用 today

範例：
- 「日本下場對誰」→ {"action": "upcoming", "query": "日本"}
- 「他們下場幾點打」（歷史有日本）→ {"action": "upcoming", "query": "日本"}
- 「洋基今天怎樣」→ {"action": "score", "query": "洋基"}
- 「先發投手是誰」→ {"action": "details", "query": ""}
- 「今天有哪些比賽」→ {"action": "today", "query": ""}
- 「你好」→ {"action": "chat", "query": ""}
- 「充值問題」→ {"action": "chat", "query": ""}"""


# ===== FAQ 知識庫（關鍵字比對，優先回覆，不呼叫 OpenAI） =====

# 格式：(關鍵字列表, 回覆訊息)
# 比對規則：訊息中包含任一關鍵字即觸發
_FAQ_DB = [
    # ── 帳號問題 ──
    (
        ["帳號", "帳戶", "會員帳號", "忘記帳號", "帳號是什麼"],
        "老闆您好，會員帳號為您的手機號哦，還請您提供，以便客服為您協助。\n\n"
        "如需進一步協助，請聯繫官方 LINE 客服：@yu_888yu 🙏",
    ),
    (
        ["一個帳號", "多個帳號", "兩個帳號", "重複帳號", "開新帳號"],
        "老闆您好，我方一位會員只可以使用一組帳號進行遊玩，還請您留意。\n\n"
        "如有其他問題，歡迎聯繫官方 LINE 客服：@yu_888yu 🙏",
    ),
    # ── 託售點數 ──
    (
        ["託售", "託售點數", "賣點數", "點數託售"],
        "老闆您好，託售點數規則如下：\n\n"
        "📌 單筆 1,000~5,000（整百金額）：無限制銀行，無限筆數\n"
        "📌 單筆 5,100~30,000（整百金額）：限一筆\n\n"
        "✅ 支援銀行：\n"
        "中國信託(822)、國泰世華(013)、第一銀行(007)、台新銀行(812)、"
        "彰化銀行(009)、台北富邦(012)、合作金庫(006)、土地銀行(005)、"
        "元大銀行(806)、玉山銀行(808)、華南銀行(008)、臺企銀行(050)、新光銀行(103)\n\n"
        "如需協助，請聯繫官方 LINE 客服：@yu_888yu 🙏",
    ),
    # ── 充值 / 儲值 ──
    (
        ["充值", "儲值", "加值", "入金", "存款", "儲值方式"],
        "老闆您好，請問您是要詢問哪種儲值方式呢？\n\n"
        "💡 常見儲值方式：\n"
        "• 銀行轉帳\n"
        "• 超商代碼支付（10-20分鐘自動上分）\n"
        "• USDT（需提供明細給客服手動上分）\n\n"
        "如需詳細協助，請聯繫官方 LINE 客服：@yu_888yu 🙏",
    ),
    (
        ["usdt", "USDT", "泰達幣", "加密貨幣儲值"],
        "老闆您好，請您日後使用 USDT 進行儲值點數時，提供明細給客服讓客服協助您上分即可。\n\n"
        "⚠️ 使用 USDT 系統不會自動上分，還請您留意。\n\n"
        "如需協助，請聯繫官方 LINE 客服：@yu_888yu 🙏",
    ),
    (
        ["超商", "超商代碼", "便利商店", "7-11", "全家", "萊爾富"],
        "老闆您好，請您等候 10-20 分鐘，超商代碼支付方式系統會自動上分，還請您耐心等候即可。\n\n"
        "如超過時間仍未上分，請聯繫官方 LINE 客服：@yu_888yu 🙏",
    ),
    # ── 提現 / 出金 ──
    (
        ["提現", "出金", "提款", "領錢", "提領", "出款"],
        "老闆您好，關於提現問題，請提供您的會員帳號以便客服為您協助。\n\n"
        "如需即時協助，請聯繫官方 LINE 客服：@yu_888yu 🙏",
    ),
    # ── 系統維護 ──
    (
        ["維護", "系統維護", "當機", "無法使用", "系統異常", "打不開"],
        "老闆您好，目前系統可能正在維護中，維護時間待定，請您耐心等候，造成不便請見諒。\n\n"
        "如需即時狀態更新，請聯繫官方 LINE 客服：@yu_888yu 🙏",
    ),
    (
        ["信用卡", "刷卡", "visa", "VISA", "mastercard"],
        "老闆您好，目前信用卡通道暫時維護中，請您先行使用其他點數儲值渠道。\n\n"
        "如需協助，請聯繫官方 LINE 客服：@yu_888yu 🙏",
    ),
    # ── 驗證 / 實名認證 ──
    (
        ["驗證", "實名認證", "身份驗證", "KYC", "認證"],
        "老闆您好，關於帳號驗證問題，請聯繫官方 LINE 客服由專人為您協助：@yu_888yu 🙏",
    ),
    # ── 密碼問題 ──
    (
        ["密碼", "忘記密碼", "重設密碼", "修改密碼", "密碼錯誤"],
        "老闆您好，關於密碼問題，請聯繫官方 LINE 客服由專人為您協助重設：@yu_888yu 🙏",
    ),
    # ── 客服聯繫 ──
    (
        ["客服", "聯繫客服", "找客服", "人工客服", "line客服", "LINE客服"],
        "老闆您好，官方 LINE 客服：@yu_888yu\n\n"
        "客服人員 7×24 小時在線為您服務，歡迎隨時聯繫！🙏",
    ),
    # ── 官方頻道 ──
    (
        ["官方頻道", "頻道", "最新消息", "公告"],
        "老闆您好，官方頻道：https://t.me/LA11118\n\n"
        "訂閱頻道可獲取最新體育資訊與平台公告！📢",
    ),
    # ── 遊戲平台 ──
    (
        ["遊戲", "進入遊戲", "遊戲平台", "娛樂城", "平台"],
        "老闆您好，合作遊戲平台：http://la1111.ofa168hk.com/\n\n"
        "點擊下方【🎮 遊戲】按鈕即可進入！",
    ),
    # ── 上分 / 點數問題 ──
    (
        ["上分", "沒上分", "點數沒到", "點數未到", "點數問題", "沒收到點數"],
        "老闆您好，關於點數未到帳問題：\n\n"
        "• 超商代碼：請等候 10-20 分鐘，系統自動上分\n"
        "• USDT：需提供轉帳明細給客服手動上分\n"
        "• 銀行轉帳：如超過 30 分鐘未到帳，請聯繫客服\n\n"
        "如需即時協助，請聯繫官方 LINE 客服：@yu_888yu 🙏",
    ),
]

# 超出範圍的回覆
_OUT_OF_SCOPE_REPLY = (
    "老闆您好，關於您諮詢的問題已經超出了客服的服務範圍，"
    "非常抱歉不能為您解答，請您聯繫官方 LINE 客服：@yu_888yu 🙏"
)

# 超出範圍的觸發關鍵字（這些問題 AI 也不應該回答）
_OUT_OF_SCOPE_KEYWORDS = [
    "退款", "退費", "詐騙", "被騙", "法律", "訴訟", "報警", "警察",
    "黑名單", "封號原因", "帳號被封", "申訴",
]


def _check_faq(user_message: str) -> str | None:
    """
    檢查訊息是否符合 FAQ 知識庫中的任一條目。
    符合則回傳對應回覆，否則回傳 None。
    """
    msg_lower = user_message.lower()

    # 先檢查超出範圍的關鍵字
    for kw in _OUT_OF_SCOPE_KEYWORDS:
        if kw in msg_lower:
            logger.info(f"FAQ 超出範圍觸發：{kw}")
            return _OUT_OF_SCOPE_REPLY

    # 再比對 FAQ 知識庫
    for keywords, reply in _FAQ_DB:
        for kw in keywords:
            if kw.lower() in msg_lower:
                logger.info(f"FAQ 命中：{kw}")
                return reply

    return None


# ===== 對話記憶 =====

_conversation_history: dict = defaultdict(list)
MAX_HISTORY = 20  # 每用戶最多保留的訊息數


def get_ai_response(user_id: int, user_message: str) -> str:
    """
    取得 AI 回應。

    流程：
    1. 先檢查 FAQ 知識庫（關鍵字比對，不呼叫 OpenAI）
    2. FAQ 未命中才呼叫 OpenAI gpt-4.1-mini
    3. 對話歷史記憶（最多 20 條）

    Args:
        user_id: Telegram 用戶 ID
        user_message: 用戶傳送的訊息

    Returns:
        回覆文字
    """
    # ── Step 1：FAQ 知識庫優先比對 ──
    faq_reply = _check_faq(user_message)
    if faq_reply:
        # FAQ 命中：記錄到歷史但不呼叫 OpenAI
        history = _conversation_history[user_id]
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": faq_reply})
        if len(history) > MAX_HISTORY:
            _conversation_history[user_id] = history[-MAX_HISTORY:]
        return faq_reply

    # ── Step 2：呼叫 OpenAI ──
    try:
        history = _conversation_history[user_id]
        history.append({"role": "user", "content": user_message})
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

        response = _get_client().chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            max_tokens=500,
            temperature=0.8,
        )

        ai_reply = response.choices[0].message.content.strip()
        history.append({"role": "assistant", "content": ai_reply})

        if len(history) > MAX_HISTORY:
            _conversation_history[user_id] = history[-MAX_HISTORY:]

        logger.info(f"AI 回應用戶 {user_id}：{ai_reply[:50]}...")
        return ai_reply

    except Exception as e:
        logger.error(f"AI 客服錯誤: {e}", exc_info=True)
        return (
            "老闆您好，我現在有點忙不過來 😅 請稍後再試，"
            "或聯繫官方 LINE 客服：@yu_888yu 🙏"
        )


def should_use_bot_function(user_id: int, user_message: str) -> dict:
    """
    讓 AI 判斷用戶意圖，決定要用哪個 Bot 功能還是直接聊天。

    V13 更新：整合客服話術，chat 意圖包含平台客服問題

    Returns:
        dict: {
            "action": "score"|"details"|"upcoming"|"analyze"|"live"|"hot"|"leaders"|"today"|"chat",
            "query": "查詢關鍵字（如果有的話）"
        }
    """
    try:
        # 取得最近 6 條對話歷史（3 輪），提供足夠上下文但不超量
        history = _conversation_history.get(user_id, [])
        recent_history = history[-6:] if len(history) > 6 else history

        # 組合訊息：系統 prompt + 歷史 + 最新訊息
        messages = [{"role": "system", "content": INTENT_SYSTEM_PROMPT}]
        messages.extend(recent_history)
        messages.append({"role": "user", "content": user_message})

        response = _get_client().chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            max_tokens=80,
            temperature=0.1,
        )

        result_text = response.choices[0].message.content.strip()
        # 清理可能的 markdown 格式
        result_text = result_text.replace("```json", "").replace("```", "").strip()
        result = json.loads(result_text)

        logger.info(f"意圖判斷 [{user_id}] '{user_message}' → {result}")
        return result

    except Exception as e:
        logger.error(f"意圖判斷錯誤: {e}")
        return {"action": "chat", "query": ""}


def add_to_history(user_id: int, role: str, content: str):
    """
    手動加入訊息到對話歷史（供 interactive_bot 在查詢後記錄上下文使用）

    Args:
        user_id: 用戶 ID
        role: "user" 或 "assistant"
        content: 訊息內容
    """
    history = _conversation_history[user_id]
    history.append({"role": role, "content": content})
    if len(history) > MAX_HISTORY:
        _conversation_history[user_id] = history[-MAX_HISTORY:]


def clear_history(user_id: int):
    """清除指定用戶的對話記憶"""
    if user_id in _conversation_history:
        del _conversation_history[user_id]
        logger.info(f"已清除用戶 {user_id} 的對話記憶")
