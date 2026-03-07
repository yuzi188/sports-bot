"""
AI 賽事預測模組 - 使用已有的 OpenAI API key
根據近期戰績、盤口等數據生成 AI 分析預測
"""

import os
from openai import OpenAI
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

client = OpenAI()


def generate_match_analysis(match_info: str) -> str:
    """
    AI 生成單場比賽分析
    match_info: 包含隊伍名稱、近期戰績、盤口等文字資訊
    """
    try:
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是專業體育分析師。根據提供的數據，用繁體中文給出簡短精準的賽事分析。"
                        "包含：1) 雙方近況 2) 關鍵因素 3) 預測結果。"
                        "保持簡潔，不超過 150 字。"
                    ),
                },
                {"role": "user", "content": match_info},
            ],
            max_tokens=300,
            temperature=0.7,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"分析暫時無法生成：{e}"


def generate_daily_preview(all_matches_text: str) -> str:
    """AI 生成每日賽事總覽預測"""
    try:
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是專業體育分析師。根據今日賽程，用繁體中文寫出精華預覽。"
                        "挑出 3-5 場焦點比賽，每場用 2-3 句話分析。"
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
        resp = client.chat.completions.create(
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
