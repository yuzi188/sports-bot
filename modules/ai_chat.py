"""
AI 客服聊天模組 V8 - 全接管版
AI 自行判斷用戶意圖，不需要特定指令
"""

import logging
import os
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

# 系統 prompt：AI 全接管，自行判斷意圖
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

重要原則：
- 不要等用戶問特定問題，主動理解用戶需求並給出最有幫助的回應
- 如果用戶說的是隊名或比賽相關，告訴他可以直接輸入隊名查詢
- 不要捏造比賽結果或假造數據，如果不確定就說不確定
- 保持對話自然，不要每次都重複介紹所有功能
- 商務合作請聯繫：https://t.me/OFA168Abe1"""

# 對話記憶：每個用戶保留最近 10 輪對話（20 條訊息）
_conversation_history: dict = defaultdict(list)
MAX_HISTORY = 20


def get_ai_response(user_id: int, user_message: str) -> str:
    """
    取得 AI 回應（全接管版）
    
    Args:
        user_id: Telegram 用戶 ID（用於維護對話記憶）
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
    讓 AI 判斷用戶意圖，決定要用哪個 Bot 功能還是直接聊天
    
    Returns:
        dict: {
            "action": "score"|"analyze"|"live"|"hot"|"leaders"|"today"|"chat",
            "query": "查詢關鍵字（如果有的話）"
        }
    """
    try:
        response = _get_client().chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是體育 Bot 的意圖分類器。根據用戶訊息，判斷應該執行哪個動作。"
                        "只回傳 JSON，格式：{\"action\": \"動作\", \"query\": \"查詢詞\"}\n"
                        "動作選項：\n"
                        "- score: 查詢特定隊伍比分（query=隊名）\n"
                        "- analyze: AI 分析特定隊伍（query=隊名）\n"
                        "- live: 查看進行中比賽（query=\"\"）\n"
                        "- hot: 查看熱門賽事（query=\"\"）\n"
                        "- leaders: 查看排行榜（query=\"\"）\n"
                        "- today: 查看今日賽程（query=\"\"）\n"
                        "- chat: 純聊天或無法判斷（query=\"\"）\n"
                        "範例：用戶說「洋基今天怎樣」→ {\"action\": \"score\", \"query\": \"洋基\"}\n"
                        "範例：用戶說「你好」→ {\"action\": \"chat\", \"query\": \"\"}"
                    ),
                },
                {"role": "user", "content": user_message},
            ],
            max_tokens=80,
            temperature=0.1,
        )

        import json
        result_text = response.choices[0].message.content.strip()
        # 清理可能的 markdown 格式
        result_text = result_text.replace("```json", "").replace("```", "").strip()
        result = json.loads(result_text)
        return result

    except Exception as e:
        logger.error(f"意圖判斷錯誤: {e}")
        return {"action": "chat", "query": ""}


def clear_history(user_id: int):
    """清除指定用戶的對話記憶"""
    if user_id in _conversation_history:
        del _conversation_history[user_id]
        logger.info(f"已清除用戶 {user_id} 的對話記憶")
