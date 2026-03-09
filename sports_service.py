from modules.football_api import get_matches, get_live_scores
from modules.team_form import get_team_form
from modules.odds_analysis import analyze_odds
from modules.upset_alert import detect_upset
from ai_service import ai_reply

async def build_sports_digest():
    matches = get_matches()
    forms = get_team_form()
    odds = analyze_odds()
    upsets = detect_upset()
    live_scores = get_live_scores()

    text = "⚽ AI體育分析\n\n"
    text += "📊 即時比分\n" + "\n".join(f"• {x}" for x in live_scores) + "\n\n"
    text += "🔥 今日焦點\n" + "\n".join(f"• {x}" for x in matches) + "\n\n"
    text += "📈 球隊近況\n" + "\n".join(f"• {x}" for x in forms) + "\n\n"
    text += "🎯 勝率參考\n" + "\n".join(f"• {x}" for x in odds)

    if upsets:
        text += "\n\n🚨 爆冷預警\n" + "\n".join(f"• {x}" for x in upsets)

    ai_summary = await ai_reply("請用繁體中文簡短整理今日體育焦點、爆冷與推薦方向。")
    text += "\n\n🧠 AI摘要\n" + ai_summary
    return text
