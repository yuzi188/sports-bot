"""
AI 賽事分析模組 - 使用 OpenAI API 生成專業分析
"""

import os
from openai import OpenAI

# 延遲初始化，避免啟動時環境變數尚未載入
_client = None

def get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        _client = OpenAI(api_key=api_key)
    return _client

MODEL = "gpt-4.1-mini"


def generate_match_analysis(match_data: dict, sport_type: str, league_name: str) -> str:
    """使用 AI 生成單場比賽分析"""
    home = match_data.get("home", {})
    away = match_data.get("away", {})
    odds = match_data.get("odds", {})
    state = match_data.get("state", "pre")
    
    if state == "pre":
        prompt = f"""你是一位專業的體育分析師，請用繁體中文為以下即將進行的比賽撰寫賽前分析。

比賽：{match_data.get('name', '')}
聯賽：{league_name}
場地：{match_data.get('venue', '')}
時間：{match_data.get('date', '')}

主隊：{home.get('name', '')}
- 戰績：{home.get('record', '未知')}
- 主場戰績：{home.get('home_record', '未知')}

客隊：{away.get('name', '')}
- 戰績：{away.get('record', '未知')}
- 客場戰績：{away.get('away_record', '未知')}

盤口：{odds.get('details', '未知')}
大小分：{odds.get('overUnder', '未知')}

請提供：
1. 雙方近況簡評（2-3句）
2. 關鍵對位分析（2-3句）
3. 預測結果與信心指數（百分比）

格式要求：
- 使用繁體中文
- 簡潔有力，每段不超過3句
- 加入適當的 emoji
- 總字數控制在 200 字以內"""
    
    elif state == "post":
        prompt = f"""你是一位專業的體育分析師，請用繁體中文為以下已結束的比賽撰寫賽後復盤。

比賽：{match_data.get('name', '')}
聯賽：{league_name}
結果：{home.get('name', '')} {home.get('score', '0')} - {away.get('score', '0')} {away.get('name', '')}
狀態：{match_data.get('status_detail', '')}

請提供：
1. 比賽結果評析（2-3句）
2. 關鍵轉折點（1-2句）
3. 對後續賽程的影響（1-2句）

格式要求：
- 使用繁體中文
- 簡潔有力
- 加入適當的 emoji
- 總字數控制在 200 字以內"""
    
    else:  # in progress
        prompt = f"""你是一位專業的體育分析師，請用繁體中文為以下進行中的比賽提供即時分析。

比賽：{match_data.get('name', '')}
聯賽：{league_name}
目前比分：{home.get('name', '')} {home.get('score', '0')} - {away.get('score', '0')} {away.get('name', '')}
進度：{match_data.get('status_detail', '')}

請提供簡短的即時分析（100字以內），包含目前局勢和可能走向。"""

    try:
        response = get_client().chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "你是一位專業的體育數據分析師，擅長用簡潔有力的繁體中文撰寫賽事分析。你的分析基於數據，客觀公正。"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"AI analysis error: {e}")
        return ""


def generate_daily_preview(events_summary: str) -> str:
    """生成每日賽程預覽"""
    prompt = f"""你是一位體育頻道的主編，請根據以下今日賽程資訊，撰寫一份精彩的每日賽程預覽。

今日賽程：
{events_summary}

要求：
1. 開頭用一句話概括今日賽事亮點
2. 列出各聯賽的焦點比賽（最多5場）
3. 每場焦點戰附上簡短看點（1句話）
4. 結尾加上觀賽建議

格式要求：
- 繁體中文
- 使用 emoji 增加可讀性
- 總字數 300-500 字
- 適合 Telegram 頻道閱讀"""

    try:
        response = get_client().chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "你是一位專業的體育媒體主編，擅長撰寫吸引人的賽事預覽。使用繁體中文。"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=800,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"AI preview error: {e}")
        return ""


def generate_post_game_review(results_summary: str) -> str:
    """生成賽後復盤總結"""
    prompt = f"""你是一位體育頻道的主編，請根據以下今日比賽結果，撰寫一份賽後復盤總結。

今日結果：
{results_summary}

要求：
1. 開頭用一句話總結今日最大看點
2. 分析 2-3 場焦點戰的結果
3. 提及任何意外結果或重要紀錄
4. 展望明日賽程

格式要求：
- 繁體中文
- 使用 emoji 增加可讀性
- 總字數 300-500 字
- 適合 Telegram 頻道閱讀"""

    try:
        response = get_client().chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "你是一位專業的體育媒體主編，擅長撰寫精彩的賽後復盤。使用繁體中文。"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=800,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"AI review error: {e}")
        return ""


def generate_deep_analysis(match_data: dict, sport_type: str, league_name: str, extra_context: str = "") -> str:
    """生成深度分析文章"""
    home = match_data.get("home", {})
    away = match_data.get("away", {})
    odds = match_data.get("odds", {})
    
    prompt = f"""你是一位頂級體育分析師，請為以下比賽撰寫一篇深度分析文章。

比賽：{match_data.get('name', '')}
聯賽：{league_name}
場地：{match_data.get('venue', '')}

主隊：{home.get('name', '')}
- 總戰績：{home.get('record', '未知')}
- 統計數據：{home.get('stats', {})}

客隊：{away.get('name', '')}
- 總戰績：{away.get('record', '未知')}
- 統計數據：{away.get('stats', {})}

盤口資訊：{odds.get('details', '未知')}
大小分：{odds.get('overUnder', '未知')}

{f'額外背景：{extra_context}' if extra_context else ''}

請撰寫深度分析，包含：
1. 📊 數據對比（用表格或數字呈現）
2. 🔑 關鍵因素分析（3-4個要點）
3. 💡 戰術觀察
4. 🎯 預測與建議

格式要求：
- 繁體中文
- 500-800 字
- 專業但易讀
- 適合 Telegram 頻道"""

    try:
        response = get_client().chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "你是一位頂級體育數據分析師，擅長撰寫深度分析文章。你的分析結合數據和戰術觀察，專業但易於理解。使用繁體中文。"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1200,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"AI deep analysis error: {e}")
        return ""


if __name__ == "__main__":
    # 測試
    test_match = {
        "name": "Liverpool at Manchester City",
        "venue": "Etihad Stadium",
        "date": "2026-03-08T17:30Z",
        "state": "pre",
        "home": {"name": "Manchester City", "record": "15-8-5", "home_record": "9-3-2"},
        "away": {"name": "Liverpool", "record": "20-5-3", "away_record": "9-3-2"},
        "odds": {"details": "Liverpool -0.5", "overUnder": "3.5"},
    }
    result = generate_match_analysis(test_match, "soccer", "英超 Premier League")
    print(result)
