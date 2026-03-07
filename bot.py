"""
世界體育數據室 - Telegram 自動體育分析機器人
主程式
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
    """10:00 - 今日賽程預覽"""
    log("📋 開始生成今日賽程預覽...")
    
    try:
        # 取得今日賽事
        events = get_today_events()
        
        if not events:
            send_message(f"{'═' * 24}\n📋 今日賽程預覽\n{format_date_header()}\n{'═' * 24}\n\n😴 今日暫無重大賽事\n明日再見！\n\n📡 世界體育數據室")
            log("今日無賽事")
            return
        
        # 1. 發送比分板/賽程表
        scoreboard_msg = format_scoreboard_message(events)
        result = send_message(scoreboard_msg)
        if result.get("ok"):
            # 置頂賽程表
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
        
    except Exception as e:
        log(f"❌ 預覽生成失敗: {e}")
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
        header = f"{'═' * 24}\n🔍 今日焦點戰深度分析\n{format_date_header()}\n{'═' * 24}\n\n以下為今日最值得關注的比賽分析 👇"
        send_message(header)
        time.sleep(2)
        
        # 為每場焦點戰生成分析
        for i, match_info in enumerate(focus):
            match = match_info["match"]
            league_info = match_info["league_info"]
            sport = match_info["sport"]
            
            log(f"  分析 {i+1}/{len(focus)}: {match.get('name', '')}")
            
            # 生成深度分析
            analysis = generate_deep_analysis(match, sport, league_info["name"])
            
            if analysis:
                msg = format_analysis_message(match, league_info, analysis)
                send_message(msg)
                time.sleep(3)  # 間隔發送
            
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
        
        # 加上更新標記
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
        # 主要聯賽排名
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
        print("Usage: python bot.py [morning|afternoon|evening|night|standings|all]")
        print("\nRunning morning preview as default...")
        task_morning_preview()
