"""
排程管理器 V21.0 - LA1 SPORTS AI PLATFORM
新增：
  - 每日 10:00 AI 賽事分析推送到 @LA11118 頻道
  - 每日 18:00 焦點賽事預測投票推送
  - 每日 22:00 賽後復盤總結
  - 保留原有推播任務
"""

import sys
import os
import time
import threading
import logging
import schedule
from datetime import datetime
import pytz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import TIMEZONE, SCHEDULE, GAME_URL_TW, HUMAN_SUPPORT, BUSINESS_CONTACT, CHANNEL_ID
from bot import (
    task_morning_preview,
    task_afternoon_analysis,
    task_evening_focus,
    task_night_review,
    task_weekly_standings,
    task_group_video_promo,
    log,
)
from telegram_sender import test_connection, send_message, send_photo

logger = logging.getLogger(__name__)
tz = pytz.timezone(TIMEZONE)

DEFAULT_PHOTO = "https://i.imgur.com/8yKQF3K.png"


# ══════════════════════════════════════════════
#  V21 新增：AI 賽事分析自動推送
# ══════════════════════════════════════════════

def task_daily_ai_analysis():
    """每日 AI 賽事分析推送到頻道"""
    try:
        from modules.daily_analysis import fetch_all_today_games, generate_daily_analysis_with_gpt
        log("📊 [AI分析] 開始生成今日賽事分析...")

        all_games = fetch_all_today_games()
        if not all_games:
            log("📊 [AI分析] 今日無賽事資料，跳過推送")
            return

        analysis = generate_daily_analysis_with_gpt(all_games)
        if analysis:
            send_message(analysis)
            log("✅ [AI分析] 今日賽事分析已推送到頻道")
        else:
            log("⚠️ [AI分析] 分析生成失敗")
    except Exception as e:
        log(f"❌ [AI分析] 推送失敗: {e}")
        logger.error(f"task_daily_ai_analysis error: {e}", exc_info=True)


def task_prediction_polls():
    """每日焦點賽事預測投票推送"""
    try:
        import requests
        from config import BOT_TOKEN
        from modules.daily_analysis import fetch_all_today_games, generate_focus_matches

        log("🎯 [預測投票] 開始生成今日焦點賽事投票...")

        all_games = fetch_all_today_games()
        if not all_games:
            log("🎯 [預測投票] 今日無賽事，跳過")
            return

        focus = generate_focus_matches(all_games)
        if not focus:
            log("🎯 [預測投票] 無焦點賽事可供投票")
            return

        api_url = f"https://api.telegram.org/bot{BOT_TOKEN}"

        for match in focus:
            question = f"🎯 {match['league']}：{match['away_team']} vs {match['home_team']}，誰會贏？"
            options = [match['away_team'], match['home_team'], "平手/其他"]

            # 先發送說明文字
            desc = f"📺 {match['league']}\n⚔️ {match['away_team']} vs {match['home_team']}"
            if match.get("home_record") and match.get("away_record"):
                desc += f"\n📊 戰績：{match['away_team']} ({match['away_record']}) vs {match['home_team']} ({match['home_record']})"
            desc += "\n\n猜對可獲得 +10 積分！"
            send_message(desc)

            # 發送投票
            try:
                import json
                payload = {
                    "chat_id": CHANNEL_ID,
                    "question": question[:300],  # Telegram 限制
                    "options": json.dumps(options),
                    "is_anonymous": False,
                }
                resp = requests.post(f"{api_url}/sendPoll", data=payload, timeout=15)
                if resp.ok:
                    poll_data = resp.json().get("result", {}).get("poll", {})
                    poll_id = poll_data.get("id", "")

                    # 記錄投票到 prediction_game
                    try:
                        from modules.prediction_game import register_poll
                        register_poll(
                            poll_id=poll_id,
                            match_desc=f"{match['away_team']} vs {match['home_team']}",
                            sport=match['league'],
                            options=options,
                        )
                        log(f"✅ [預測投票] 已發送: {match['away_team']} vs {match['home_team']}")
                    except Exception as reg_err:
                        log(f"⚠️ [預測投票] 記錄投票失敗: {reg_err}")
                else:
                    log(f"⚠️ [預測投票] 發送投票失敗: {resp.text[:200]}")
            except Exception as poll_err:
                log(f"❌ [預測投票] 發送投票異常: {poll_err}")

            time.sleep(2)  # 避免發送太快

        log(f"✅ [預測投票] 共發送 {len(focus)} 場投票")
    except Exception as e:
        log(f"❌ [預測投票] 推送失敗: {e}")
        logger.error(f"task_prediction_polls error: {e}", exc_info=True)


def task_night_summary():
    """每日賽後復盤總結"""
    try:
        from modules.daily_analysis import fetch_all_today_games
        log("🌙 [復盤] 開始生成賽後復盤...")

        all_games = fetch_all_today_games()
        if not all_games:
            log("🌙 [復盤] 今日無賽事資料")
            return

        lines = ["🌙 今日賽事復盤\n"]
        total_games = 0

        for league, games in all_games.items():
            finished = [g for g in games if g["status"] in ("STATUS_FINAL", "STATUS_FINAL_OT")]
            if not finished:
                continue

            lines.append(f"\n📺 {league}")
            for g in finished:
                total_games += 1
                lines.append(f"  {g['away_team']} {g['away_score']} - {g['home_score']} {g['home_team']}")

        if total_games == 0:
            log("🌙 [復盤] 無已結束的比賽")
            return

        lines.append(f"\n\n📊 共 {total_games} 場比賽已結束")
        lines.append("🎯 明天繼續預測！ /predict")
        lines.append("📢 @LA11118")

        send_message("\n".join(lines))
        log("✅ [復盤] 賽後復盤已推送")
    except Exception as e:
        log(f"❌ [復盤] 推送失敗: {e}")
        logger.error(f"task_night_summary error: {e}", exc_info=True)


# ══════════════════════════════════════════════
#  原有推播任務
# ══════════════════════════════════════════════

def promo_post():
    """推播限時優惠活動"""
    text = f"🔥 LA1 限時活動\n\n首儲1000送1000\n\n立即開始：\n{GAME_URL_TW}"
    send_message(text)
    log("✅ 優惠推播已發送")


def agent_post():
    """推播代理招募"""
    text = f"🤝 代理招募中\n\n高額分潤 / 專屬後台 / 長期合作\n\n商務合作：{BUSINESS_CONTACT}"
    send_message(text)
    log("✅ 代理推播已發送")


def game_recommend_post():
    """推播遊戲推薦（含圖片和按鈕）"""
    caption = (
        "🎰 今日遊戲推薦\n\n"
        "🔥 熱門電子\n"
        "🎲 真人娛樂\n"
        "⚽ 體育投注\n\n"
        "👇 立即體驗"
    )
    keyboard = {
        "inline_keyboard": [
            [{"text": "🎮 立即進入台站", "url": GAME_URL_TW}],
            [{"text": "👑 聯繫客服", "url": f"https://t.me/{HUMAN_SUPPORT.lstrip('@')}"}],
        ]
    }
    send_photo(DEFAULT_PHOTO, caption, keyboard)
    log("✅ 遊戲推薦推播已發送")


# ══════════════════════════════════════════════
#  排程設定
# ══════════════════════════════════════════════

def setup_schedule():
    """設定排程"""
    schedule.clear()

    # ── V21 新增：AI 賽事分析自動推送 ──
    schedule.every().day.at("10:00").do(task_daily_ai_analysis)
    schedule.every().day.at("18:00").do(task_prediction_polls)
    schedule.every().day.at("22:00").do(task_night_summary)

    # ── 每4小時影片推播（原有）──
    schedule.every(4).hours.do(task_group_video_promo)

    # ── 每日推播任務（LA智能完善版2）──
    schedule.every().day.at("12:00").do(promo_post)
    schedule.every().day.at("15:00").do(game_recommend_post)
    schedule.every().day.at("21:00").do(agent_post)

    # ── 每週一排名 ──
    schedule.every().monday.at("09:00").do(task_weekly_standings)

    log("📅 V21.0 排程已設定：")
    log("  ── AI 賽事推播（V21 新增）──")
    log("  每日 10:00 - AI 今日賽事分析")
    log("  每日 18:00 - 焦點賽事預測投票")
    log("  每日 22:00 - 賽後復盤總結")
    log("  ── 群組推播 ──")
    log("  每 4 小時 - 影片 + 7個按鈕")
    log("  每日 12:00 - 優惠推播")
    log("  每日 15:00 - 遊戲推薦推播")
    log("  每日 21:00 - 代理推播")
    log("  每週一 09:00 - 聯賽排名")


def start_scheduler():
    """在背景 thread 啟動排程（供 main.py 呼叫）"""
    setup_schedule()

    def _run():
        while True:
            schedule.run_pending()
            time.sleep(30)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    log("✅ V21.0 排程器已在背景啟動")


def run():
    """獨立啟動排程（直接執行 scheduler.py 時使用）"""
    log("🤖 LA1 SPORTS AI PLATFORM 排程器啟動中...")

    if not test_connection():
        log("❌ Bot 連接失敗！")
        sys.exit(1)

    log("✅ Bot 連接成功")
    setup_schedule()
    log("⏳ 等待排程執行...")

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    run()
