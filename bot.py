"""
世界體育數據室 - Telegram 自動體育分析機器人
主程式 V17 - 三種運動 AI 分析整合版

新增：
  1. task_morning_preview 加入三種運動 AI 分析（足球/棒球/籃球）
  2. task_sports_ai_analysis 獨立任務（可單獨觸發）
  3. 改善錯誤處理：分類記錄錯誤類型
"""

import sys
import os
import time
import json
import traceback
from datetime import datetime
import pytz

# 確保可以導入本地模組
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import TIMEZONE, SPORTS, SCHEDULE
from espn_api import get_today_events, get_league_standings_text, get_scoreboard, parse_event
from ai_analyzer import (
    generate_match_analysis,
    generate_daily_preview,
    generate_post_game_review,
    generate_deep_analysis,
)
from formatter import (
    format_scoreboard_message,
    format_preview_message,
    format_analysis_message,
    format_review_message,
    format_standings_message,
    format_date_header,
    build_events_summary,
    select_focus_matches,
)
from telegram_sender import send_message, send_long_message, pin_message, test_connection

tz = pytz.timezone(TIMEZONE)


def log(msg: str):
    """記錄日誌"""
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {msg}")


def task_morning_preview():
    """10:00 - 今日賽程預覽 + 三種運動 AI 分析"""
    log("📋 開始生成今日賽程預覽...")

    try:
        # 取得今日賽事
        events = get_today_events()

        if not events:
            send_message(
                f"{'═' * 24}\n📋 今日賽程預覽\n{format_date_header()}\n{'═' * 24}\n\n"
                "😴 今日暫無重大賽事\n明日再見！\n\n📡 世界體育數據室"
            )
            log("今日無賽事")
            return

        # 1. 發送比分板/賽程表
        scoreboard_msg = format_scoreboard_message(events)
        result = send_message(scoreboard_msg)
        if result.get("ok"):
            pin_message(result["result"]["message_id"])
        log("✅ 賽程表已發送")

        time.sleep(2)

        # 2. 生成 AI 預覽
        summary = build_events_summary(events)
        ai_preview = generate_daily_preview(summary)
        if ai_preview:
            preview_msg = format_preview_message(ai_preview)
            send_message(preview_msg)
            log("✅ AI 預覽已發送")

        time.sleep(3)

        # 3. V17 新增：三種運動 AI 分析
        log("🤖 開始生成三種運動 AI 分析...")
        task_sports_ai_analysis()

    except Exception as e:
        log(f"❌ 預覽生成失敗: {e}")
        traceback.print_exc()


def task_sports_ai_analysis():
    """
    三種運動 AI 分析任務（V17 新增）
    可由 task_morning_preview 呼叫，也可單獨觸發。
    分析格式：今日焦點比賽 / 勝率預測 / 爆冷可能
    靈感來源：playsport.cc 的賽事分析呈現方式
    """
    log("⚽⚾🏀 開始三種運動 AI 分析...")

    try:
        from modules.football import get_matches as get_football_matches
        from modules.mlb import get_games as get_baseball_games
        from modules.nba import get_games as get_basketball_games
        from modules.sports_analyzer import analyze_football, analyze_baseball, analyze_basketball

        sep = "═" * 24
        now_str = datetime.now(tz).strftime("%Y/%m/%d")
        header = f"{sep}\n🤖 三種運動 AI 分析\n📅 {now_str}\n{sep}"
        send_message(header)
        time.sleep(2)

        # ── 足球分析 ──
        football_matches = get_football_matches()
        if football_matches:
            football_text = "\n".join(football_matches)
            log(f"  足球賽事 {len(football_matches)} 場，開始 AI 分析...")
            football_analysis = analyze_football(football_text)
            msg = f"{sep}\n⚽ 今日足球 AI 分析\n{sep}\n\n{football_analysis}\n\n{sep}\n📡 世界體育數據室\n⚠️ 分析僅供參考，請理性投注"
            send_long_message(msg)
            log("✅ 足球 AI 分析已發送")
            time.sleep(3)
        else:
            log("  今日無足球賽事，跳過")

        # ── 棒球分析 ──
        baseball_games = get_baseball_games()
        if baseball_games:
            baseball_text = "\n".join(baseball_games)
            log(f"  棒球賽事 {len(baseball_games)} 場，開始 AI 分析...")
            baseball_analysis = analyze_baseball(baseball_text)
            msg = f"{sep}\n⚾ 今日棒球 AI 分析\n{sep}\n\n{baseball_analysis}\n\n{sep}\n📡 世界體育數據室\n⚠️ 分析僅供參考，請理性投注"
            send_long_message(msg)
            log("✅ 棒球 AI 分析已發送")
            time.sleep(3)
        else:
            log("  今日無棒球賽事，跳過")

        # ── 籃球分析 ──
        basketball_games = get_basketball_games()
        if basketball_games:
            basketball_text = "\n".join(basketball_games)
            log(f"  籃球賽事 {len(basketball_games)} 場，開始 AI 分析...")
            basketball_analysis = analyze_basketball(basketball_text)
            msg = f"{sep}\n🏀 今日籃球 AI 分析\n{sep}\n\n{basketball_analysis}\n\n{sep}\n📡 世界體育數據室\n⚠️ 分析僅供參考，請理性投注"
            send_long_message(msg)
            log("✅ 籃球 AI 分析已發送")
            time.sleep(3)
        else:
            log("  今日無籃球賽事，跳過")

        if not any([football_matches, baseball_games, basketball_games]):
            send_message("😴 今日暫無足球、棒球、籃球賽事資訊可供分析。")

        log("✅ 三種運動 AI 分析全部完成")

    except ImportError as e:
        log(f"❌ 模組導入失敗: {e}")
    except Exception as e:
        log(f"❌ 三種運動 AI 分析失敗: {e}")
        traceback.print_exc()


def task_afternoon_analysis():
    """14:00 - 深度分析"""
    log("🔍 開始生成深度分析...")

    try:
        events = get_today_events()
        if not events:
            log("今日無賽事，跳過分析")
            return

        # 選出焦點比賽
        focus = select_focus_matches(events, max_matches=5)

        if not focus:
            log("無焦點比賽")
            return

        # 發送標題
        header = (
            f"{'═' * 24}\n🔍 今日焦點戰深度分析\n{format_date_header()}\n{'═' * 24}\n\n"
            "以下為今日最值得關注的比賽分析 👇"
        )
        send_message(header)
        time.sleep(2)

        # 為每場焦點戰生成分析
        for i, match_info in enumerate(focus):
            match = match_info["match"]
            league_info = match_info["league_info"]
            sport = match_info["sport"]

            log(f"  分析 {i+1}/{len(focus)}: {match.get('name', '')}")

            analysis = generate_deep_analysis(match, sport, league_info["name"])

            if analysis:
                msg = format_analysis_message(match, league_info, analysis)
                send_message(msg)
                time.sleep(3)

        log(f"✅ {len(focus)} 場焦點戰分析已發送")

    except Exception as e:
        log(f"❌ 分析生成失敗: {e}")
        traceback.print_exc()


def task_evening_focus():
    """18:00 - 傍晚焦點戰 + 即時更新"""
    log("⚡ 開始生成傍晚焦點戰...")

    try:
        events = get_today_events()
        if not events:
            log("今日無賽事")
            return

        # 更新比分板
        scoreboard_msg = format_scoreboard_message(events)

        update_header = f"{'═' * 24}\n⚡ 賽事即時更新\n{format_date_header()}\n{'═' * 24}"

        send_message(update_header + "\n\n" + scoreboard_msg)
        log("✅ 即時更新已發送")

        time.sleep(2)

        # 找進行中或即將開始的比賽做分析
        live_matches = []
        for key, data in events.items():
            for e in data["events"]:
                if e["state"] in ["in", "pre"]:
                    live_matches.append({
                        "match": e,
                        "league_info": data["info"],
                        "sport": data["sport"],
                    })

        # 分析最多 3 場
        for match_info in live_matches[:3]:
            match = match_info["match"]
            league_info = match_info["league_info"]

            analysis = generate_match_analysis(match, match_info["sport"], league_info["name"])
            if analysis:
                msg = format_analysis_message(match, league_info, analysis)
                send_message(msg)
                time.sleep(3)

        log("✅ 傍晚焦點戰已發送")

    except Exception as e:
        log(f"❌ 傍晚更新失敗: {e}")
        traceback.print_exc()


def task_night_review():
    """23:00 - 賽後復盤"""
    log("📝 開始生成賽後復盤...")

    try:
        events = get_today_events()
        if not events:
            log("今日無賽事")
            return

        # 建立結果摘要
        summary = build_events_summary(events)

        # 生成 AI 復盤
        ai_review = generate_post_game_review(summary)

        if ai_review:
            review_msg = format_review_message(ai_review)
            send_message(review_msg)
            log("✅ 賽後復盤已發送")

        time.sleep(2)

        # 發送最終比分板
        scoreboard_msg = format_scoreboard_message(events)
        final_header = f"{'═' * 24}\n📊 今日最終戰報\n{format_date_header()}\n{'═' * 24}"
        send_message(final_header + "\n\n" + scoreboard_msg)
        log("✅ 最終戰報已發送")

    except Exception as e:
        log(f"❌ 復盤生成失敗: {e}")
        traceback.print_exc()


def task_weekly_standings():
    """每週一發送各聯賽排名"""
    log("📊 開始生成週報排名...")

    try:
        key_leagues = [
            ("soccer", "eng.1"),
            ("soccer", "esp.1"),
            ("soccer", "ger.1"),
            ("soccer", "ita.1"),
            ("basketball", "nba"),
            ("baseball", "mlb"),
        ]

        header = f"{'═' * 24}\n📊 本週各聯賽排名總覽\n{format_date_header()}\n{'═' * 24}"
        send_message(header)
        time.sleep(2)

        for sport, league in key_leagues:
            league_info = SPORTS.get(sport, {}).get(league, {})
            if not league_info:
                continue

            standings = get_league_standings_text(sport, league, top_n=8)
            if standings:
                msg = format_standings_message(sport, league, league_info, standings)
                send_message(msg)
                time.sleep(3)

        log("✅ 排名已發送")

    except Exception as e:
        log(f"❌ 排名生成失敗: {e}")
        traceback.print_exc()


def run_task(task_name: str):
    """執行指定任務"""
    tasks = {
        "morning": task_morning_preview,
        "afternoon": task_afternoon_analysis,
        "evening": task_evening_focus,
        "night": task_night_review,
        "standings": task_weekly_standings,
        "sports_ai": task_sports_ai_analysis,   # V17 新增：獨立三種運動 AI 分析任務
        "all": run_all_tasks,
    }

    task_func = tasks.get(task_name)
    if task_func:
        log(f"🚀 執行任務: {task_name}")
        task_func()
        log(f"✅ 任務完成: {task_name}")
    else:
        print(f"Unknown task: {task_name}")
        print(f"Available tasks: {', '.join(tasks.keys())}")


def run_all_tasks():
    """依序執行所有任務（測試用）"""
    log("🚀 執行所有任務...")
    task_morning_preview()
    time.sleep(5)
    task_afternoon_analysis()
    time.sleep(5)
    task_evening_focus()
    time.sleep(5)
    task_night_review()
    log("✅ 所有任務完成")


if __name__ == "__main__":
    # 測試連接
    if not test_connection():
        print("❌ Bot connection failed!")
        sys.exit(1)

    # 執行指定任務
    if len(sys.argv) > 1:
        run_task(sys.argv[1])
    else:
        print("Usage: python bot.py [morning|afternoon|evening|night|standings|sports_ai|all]")
        print("\nRunning morning preview as default...")
        task_morning_preview()

def task_group_video_promo():
    """
    每4小時發送影片 + 7個按鈕到群組（V19.7 新增）
    """
    from config import GROUP_ID, BOT_TOKEN
    import requests
    
    log("🎬 開始執行群組影片推播任務...")
    
    # 影片與按鈕設定
    video_url = "https://files.manuscdn.com/user_upload_by_module/session_file/310419663032670396/zOYpATipTMNEkuCQ.mp4"
    
    # 建立按鈕 (Inline Keyboard)
    # 由於 bot.py 是獨立運行的腳本，直接使用 Telegram Bot API 發送
    game_url = "http://la1111.ofa168hk.com/"
    cs_url = "https://t.me/yu_888yu"
    
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "🇹🇼 台站｜立即註冊", "url": "http://La1111.meta1788.com"},
                {"text": "🇭🇰🇲🇾🇲🇴🇻🇳 U站｜USDT專區", "url": "http://la1111.ofa168hk.com"}
            ],
            [
                {"text": "🇰🇭 代理入口", "url": "http://agent.ofa168kh.com"}
            ],
            [
                {"text": "🆕 免費開戶註冊", "url": "http://La1111.meta1788.com"}
            ],
            [
                {"text": "🎁 優惠領取｜聯絡客服", "url": "https://t.me/yu_888yu"}
            ],
            [
                {"text": "🤝 商務合作", "url": "https://t.me/OFA168Abe1"}
            ],
            [
                {"text": "🎮 立即進入遊戲", "url": "http://la1111.ofa168hk.com/"}
            ],
            [
                {"text": "🎱 去 Bot 玩 539", "url": "https://t.me/LA1111_bot?start=539"}
            ]
        ]
    }
    
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
    payload = {
        "chat_id": GROUP_ID,
        "video": video_url,
        "caption": "🏆 LA1 智能體育服務平台\n\n🔥 最專業的體育分析，最即時的比分數據！\n立即點擊下方按鈕開始體驗 👇",
        "reply_markup": json.dumps(reply_markup)
    }
    
    try:
        resp = requests.post(api_url, json=payload, timeout=30)
        result = resp.json()
        if result.get("ok"):
            log("✅ 群組影片推播成功")
        else:
            log(f"❌ 群組影片推播失敗: {result.get('description')}")
    except Exception as e:
        log(f"❌ 群組影片推播異常: {e}")
