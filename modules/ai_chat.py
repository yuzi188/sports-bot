"""
AI 客服聊天模組 - 使用 OpenAI gpt-4.1-mini
當用戶訊息不是比分查詢時，以人性化方式回應
"""

import logging
import os
from collections import defaultdict
from openai import OpenAI

logger = logging.getLogger(__name__)

# OpenAI 客戶端（自動從 OPENAI_API_KEY 環境變數讀取）
client = OpenAI()

# 系統 prompt：定義 AI 助理的人格與職責
SYSTEM_PROMPT = """你是「世界體育數據室」的 AI 助理魚姐，專精全球體育資訊。

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

Bot 的主要功能（需要時可以介紹）：
- /score 隊名 → 查即時比分
- /today → 今日所有賽事
- /live → 進行中的比賽
- /hot → 今日熱門賽事
- /leaders → 排行榜（全壘打/得分/射手）
- /analyze 隊名 → AI 賽事分析預測
- /odds 隊名 → 盤口資訊
- 直接輸入隊名也可以查詢！

注意：
- 如果用戶問的是即時比分，請引導他們用 /score 或直接輸入隊名
- 不要捏造比賽結果或假造數據，如果不確定就說不確定
- 保持對話自然，不要每次都重複介紹所有功能"""

# 對話記憶：每個用戶保留最近 10 輪對話（20 條訊息）
_conversation_history: dict = defaultdict(list)
MAX_HISTORY = 20  # 每用戶最多保留的訊息數


def get_ai_response(user_id: int, user_message: str) -> str:
    """
    取得 AI 回應
    
    Args:
        user_id: Telegram 用戶 ID（用於維護對話記憶）
        user_message: 用戶傳送的訊息
    
    Returns:
        AI 回應文字
    """
    try:
        # 取得該用戶的對話歷史
        history = _conversation_history[user_id]

        # 加入用戶新訊息
        history.append({"role": "user", "content": user_message})

        # 組合完整訊息列表（系統 prompt + 對話歷史）
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

        # 呼叫 OpenAI API
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            max_tokens=500,
            temperature=0.8,
        )

        ai_reply = response.choices[0].message.content.strip()

        # 將 AI 回應加入對話歷史
        history.append({"role": "assistant", "content": ai_reply})

        # 超過上限時移除最舊的對話（保留最近 MAX_HISTORY 條）
        if len(history) > MAX_HISTORY:
            _conversation_history[user_id] = history[-MAX_HISTORY:]

        logger.info(f"AI 回應用戶 {user_id}：{ai_reply[:50]}...")
        return ai_reply

    except Exception as e:
        logger.error(f"AI 客服錯誤: {e}", exc_info=True)
        return "抱歉，我現在有點忙不過來 😅 請稍後再試，或是直接輸入隊名查詢比分！"


def clear_history(user_id: int):
    """清除指定用戶的對話記憶"""
    if user_id in _conversation_history:
        del _conversation_history[user_id]
        logger.info(f"已清除用戶 {user_id} 的對話記憶")
