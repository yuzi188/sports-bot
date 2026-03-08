"""
AI 客服聊天模組 V9 - 上下文感知版
修復：意圖分類器傳入對話歷史，正確理解「下場」「接下來」等追問
"""

import logging
import os
import json
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


# ===== 系統 Prompt =====

SYSTEM_PROMPT = """你是「世界體育數據室」的 AI 助理 🐟，負責全面接管所有用戶對話。

你的個性與風格：
- 親切友善，像真人客服一樣自然
- 用繁體中文回應，語氣輕鬆但專業
- 適時加入 emoji 增加活潑感，但不要過度
- 回答簡潔有重點，不要長篇大論

你能做的事：
1. 回答各種體育問題（NBA、MLB、足球、棒球、網球等）
2. 介紹 Bot 的功能和使用方式
3. 跟用戶閒聊，聊體育也可以聊其他話題
4. 提供體育知識、球隊歷史、球員資訊等
5. 當用戶想查比分或賽事時，主動告知可以直接輸入隊名或用指令查詢

Bot 的主要功能（需要時可以介紹）：
- 直接輸入隊名 → 查即時比分（最快速）
- /score 隊名 → 查即時比分
- /today → 今日所有賽事
- /live → 進行中的比賽
- /hot → 今日熱門賽事
- /leaders → 排行榜（全壘打/得分/射手）
- /analyze 隊名 → AI 賽事分析 + 勝率預測
- /odds 隊名 → 盤口資訊

情緒感知與安撫：
- 當用戶表現出沮喪、憤怒、失落、抱怨時，優先安撫情緒，再提供幫助
- 例如用戶說「今天輸了好慘」→ 先表達同理心，再聊比賽
- 例如用戶說「這什麼爛 Bot」→ 不要反駁，誠懇道歉並詢問哪裡不好用
- 例如用戶說「我押注輸了好多」→ 給予情緒支持，提醒理性投注
- 語氣要像朋友一樣真誠，不要太制式化
- 當用戶心情好時，一起開心；心情不好時，陪伴安慰

重要原則：
- 不要等用戶問特定問題，主動理解用戶需求並給出最有幫助的回應
- 如果用戶說的是隊名或比賽相關，告訴他可以直接輸入隊名查詢
- 不要捏造比賽結果或假造數據，如果不確定就說不確定
- 保持對話自然，不要每次都重複介紹所有功能
- 商務合作請聯繫：https://t.me/OFA168Abe1"""

# 意圖分類器的 system prompt（獨立、簡潔）
INTENT_SYSTEM_PROMPT = """你是體育 Bot 的意圖分類器。根據【最新用戶訊息】和【對話歷史】，判斷應執行哪個動作。

只回傳 JSON，格式：{"action": "動作", "query": "查詢詞"}

動作選項：
- score: 查詢特定隊伍的即時/今日比分（query=隊名）
- upcoming: 查詢特定隊伍的下一場/未來賽程（query=隊名）
- analyze: AI 分析特定隊伍（query=隊名）
- live: 查看目前進行中比賽（query=""）
- hot: 查看熱門賽事（query=""）
- leaders: 查看排行榜（query=""）
- today: 查看今日所有賽事總覽（query=""）
- chat: 純聊天、問候、體育知識問答（query=""）

關鍵規則：
1. 「下場」「下一場」「接下來」「之後」「明天」「下週」「賽程」= upcoming（不是 today！）
2. 「下場對誰」「下場幾點」「接下來打誰」= upcoming
3. 如果用戶問「下場」但沒說隊名，從對話歷史找最近提到的隊伍作為 query
4. 「今天怎樣」「比分多少」「現在幾比幾」= score
5. 「你好」「謝謝」「哈哈」= chat
6. 只有明確說「今日所有比賽」「今天有哪些賽事」才用 today

範例：
- 「日本下場對誰」→ {"action": "upcoming", "query": "日本"}
- 「他們下場幾點打」（歷史有日本）→ {"action": "upcoming", "query": "日本"}
- 「洋基今天怎樣」→ {"action": "score", "query": "洋基"}
- 「下一場是什麼時候」（歷史有洋基）→ {"action": "upcoming", "query": "洋基"}
- 「今天有哪些比賽」→ {"action": "today", "query": ""}
- 「你好」→ {"action": "chat", "query": ""}"""


# ===== 對話記憶 =====

_conversation_history: dict = defaultdict(list)
MAX_HISTORY = 20  # 每用戶最多保留的訊息數


def get_ai_response(user_id: int, user_message: str) -> str:
    """
    取得 AI 回應（全接管版，含對話記憶）

    Args:
        user_id: Telegram 用戶 ID
        user_message: 用戶傳送的訊息

    Returns:
        AI 回應文字
    """
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
        return "抱歉，我現在有點忙不過來 😅 請稍後再試，或是直接輸入隊名查詢比分！"


def should_use_bot_function(user_id: int, user_message: str) -> dict:
    """
    讓 AI 判斷用戶意圖，決定要用哪個 Bot 功能還是直接聊天。

    V10 新增：details 意圖識別（先發投手/進球/換人等詳細查詢）

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
