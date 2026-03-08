"""
AI 賽事預測模組 V8 - 使用已有的 OpenAI API key
根據近期戰績、盤口等數據生成 AI 分析預測
新增：勝率預測、比分預測
"""

import os
from openai import OpenAI
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 延遲初始化，避免啟動時環境變數尚未載入
_client = None

def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        _client = OpenAI(api_key=api_key)
    return _client


def generate_win_probability(match_info: str) -> str:
    """
    AI 預測勝率與比分 (V8 新功能)
    match_info: 包含隊伍名稱、近期戰績等文字資訊
    """
    try:
        resp = _get_client().chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是專業體育數據分析師。根據提供的比賽資訊，用繁體中文給出："
                        "1) 主隊勝率（百分比）"
                        "2) 客隊勝率（百分比）"
                        "3) AI 預測比分（例如：洋基 5 - 3 紅襪）"
                        "4) 一句話關鍵分析。"
                        "格式範例：\n🏆 勝率預測\n主隊 XX% vs 客隊 XX%\n📊 預測比分：X - X\n💡 關鍵：..."
                        "保持簡潔，不超過 80 字。"
                    ),
                },
                {"role": "user", "content": match_info},
            ],
            max_tokens=150,
            temperature=0.6,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"勝率預測暫時無法生成：{e}"


def generate_match_analysis(match_info: str) -> str:
    """
    AI 生成單場比賽分析（含勝率預測）
    match_info: 包含隊伍名稱、近期戰績、盤口等文字資訊
    """
    try:
        resp = _get_client().chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是專業體育分析師。根據提供的數據，用繁體中文給出簡短精準的賽事分析。"
                        "包含：1) 雙方近況 2) 關鍵因素 3) 預測結果（含勝率百分比和預測比分）。"
                        "保持簡潔，不超過 200 字。"
                    ),
                },
                {"role": "user", "content": match_info},
            ],
            max_tokens=350,
            temperature=0.7,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"分析暫時無法生成：{e}"


def generate_daily_preview(all_matches_text: str) -> str:
    """AI 生成每日賽事總覽預測"""
    try:
        resp = _get_client().chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是專業體育分析師。根據今日賽程，用繁體中文寫出精華預覽。"
                        "挑出 3-5 場焦點比賽，每場用 2-3 句話分析，並附上勝率預測（百分比）。"
                        "格式清晰，使用 emoji 增加可讀性。不超過 500 字。"
                    ),
                },
                {"role": "user", "content": f"今日賽程：\n{all_matches_text}"},
            ],
            max_tokens=600,
            temperature=0.7,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"預覽暫時無法生成：{e}"


def generate_post_review(results_text: str) -> str:
    """AI 生成賽後復盤"""
    try:
        resp = _get_client().chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是專業體育分析師。根據今日比賽結果，用繁體中文寫出賽後復盤。"
                        "挑出 3-5 場精彩比賽，分析勝負關鍵。"
                        "格式清晰，使用 emoji。不超過 500 字。"
                    ),
                },
                {"role": "user", "content": f"今日比賽結果：\n{results_text}"},
            ],
            max_tokens=600,
            temperature=0.7,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"復盤暫時無法生成：{e}"
