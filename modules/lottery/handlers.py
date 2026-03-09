"""
539 彩票指令 handler - UI 整合版
包含數字鍵盤 UI、底部選單、互動下注流程
"""
from __future__ import annotations

import random
import logging
from datetime import timedelta

from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove
)
from telegram.ext import ContextTypes

from modules.lottery.lottery_config import lottery_settings
from modules.lottery.repository import (
    ensure_user,
    get_user,
    get_or_create_today_draw,
    count_user_bets,
    place_bet,
    claim_daily_bonus,
    recent_bets,
    leaderboard,
    get_draw_by_date,
)
from modules.lottery.utils import (
    tz_now,
    today_str,
    parse_numbers,
    numbers_to_text,
    is_bet_open,
    next_draw_datetime,
)

logger = logging.getLogger(__name__)

# ── 底部選單按鈕 ──
LOTTERY_MENU = [
    ["🎱下注", "📋查詢下注"],
    ["💰查詢L幣", "🏆排行榜"],
    ["📖遊戲規則", "🔙退出彩票"]
]

def get_menu_keyboard():
    return ReplyKeyboardMarkup(LOTTERY_MENU, resize_keyboard=True)

# ── 數字鍵盤 UI ──
def get_number_keyboard(selected_nums: list[int] = None):
    """
    產生 1-39 的數字鍵盤 (7x6 佈局)
    selected_nums: 已選中的號碼列表，用於高亮顯示
    """
    if selected_nums is None:
        selected_nums = []
    
    keyboard = []
    num = 1
    # 7 行 x 6 列 = 42 個位置，顯示 1-39
    for r in range(7):
        row = []
        for c in range(6):
            if num <= 39:
                label = f"✅ {num}" if num in selected_nums else str(num)
                row.append(InlineKeyboardButton(label, callback_data=f"lot_num_{num}"))
                num += 1
        if row:
            keyboard.append(row)
    
    # 底部功能按鈕
    keyboard.append([
        InlineKeyboardButton("🎲 快速隨機", callback_data="lot_quick"),
        InlineKeyboardButton("❌ 清除重選", callback_data="lot_clear")
    ])
    keyboard.append([
        InlineKeyboardButton("🚫 取消下注", callback_data="lot_cancel")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def _name(update: Update) -> tuple[int, str | None, str]:
    user = update.effective_user
    username = user.username if user else None
    full_name = user.full_name if user else "Unknown"
    return user.id, username, full_name

def _register(update: Update) -> str:
    """確保用戶已註冊，回傳新手提示（若為新用戶）"""
    user_id, username, full_name = _name(update)
    created = ensure_user(
        user_id=user_id,
        username=username,
        full_name=full_name,
        starting_coins=lottery_settings.starting_coins,
        now_iso=tz_now().isoformat(),
    )
    return "🎁 已發送新手 L幣 100 枚\n" if created else ""

# ── 指令 Handler ──

async def lottery_info_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/539 指令：進入彩票模式並顯示選單"""
    prefix = _register(update)
    draw_dt = next_draw_datetime()
    s = lottery_settings
    
    # 如果帶有參數，直接走文字下注流程
    if context.args and len(context.args) >= 1:
        await bet_539_cmd(update, context)
        return

    text = (
        f"{prefix}🎰 **L幣 539 彩票模式**\n\n"
        f"每注：{s.bet_price} L幣\n"
        f"開獎：每日 {s.draw_hour:02d}:{s.draw_minute:02d}\n\n"
        "請使用下方選單進行操作，或直接輸入 `/539 01 02 03 04 05` 下注。"
    )
    await update.message.reply_text(text, reply_markup=get_menu_keyboard())

async def bet_ui_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """點擊「🎱下注」按鈕：顯示數字鍵盤"""
    open_ok, reason = is_bet_open()
    if not open_ok:
        await update.message.reply_text("⛔ " + reason)
        return

    context.user_data["lot_picks"] = []
    await update.message.reply_text(
        "🎯 **請選擇 5 個號碼：**\n目前已選：(無)",
        reply_markup=get_number_keyboard(),
        parse_mode="Markdown"
    )

async def bet_539_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """文字指令下注：/539 01 02 03 04 05"""
    prefix = _register(update)
    open_ok, reason = is_bet_open()
    if not open_ok:
        await update.message.reply_text(prefix + "⛔ " + reason)
        return

    try:
        numbers = parse_numbers(context.args)
    except ValueError as e:
        await update.message.reply_text(prefix + f"❌ {e}")
        return

    await _execute_bet(update, context, numbers, prefix)

async def _execute_bet(update: Update, context: ContextTypes.DEFAULT_TYPE, numbers: list[int], prefix: str = ""):
    """執行下注的核心邏輯"""
    now = tz_now()
    s = lottery_settings
    draw = get_or_create_today_draw(now.isoformat(), f"{s.draw_hour:02d}:{s.draw_minute:02d}")
    user_id = update.effective_user.id
    
    user_bet_count = count_user_bets(draw["draw_id"], user_id)
    if user_bet_count >= s.max_bets_per_draw:
        msg = prefix + f"⛔ 本期最多只能下 {s.max_bets_per_draw} 注"
        if update.callback_query:
            await update.callback_query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
        return

    numbers_text = numbers_to_text(numbers)
    try:
        new_balance = place_bet(
            draw_id=draw["draw_id"],
            user_id=user_id,
            numbers_text=numbers_text,
            cost=s.bet_price,
            note=f'539 {draw["draw_date"]} {numbers_text}',
            now_iso=now.isoformat(),
        )
    except ValueError as e:
        msg = prefix + f"❌ {e}"
        if update.callback_query:
            await update.callback_query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
        return

    cutoff_dt = now.replace(hour=s.draw_hour, minute=s.draw_minute, second=0, microsecond=0) - timedelta(minutes=s.bet_cutoff_minutes)
    res_text = (
        f"{prefix}✅ **539 下注成功！**\n\n"
        f"🔢 號碼：`{numbers_text}`\n"
        f"💰 投注：{s.bet_price} L幣\n"
        f"📊 本期第 {user_bet_count + 1} 注 / 上限 {s.max_bets_per_draw}\n"
        f"💎 目前餘額：{new_balance} L幣\n\n"
        f"⏰ 截止時間：{cutoff_dt.strftime('%H:%M')}\n"
        f"📢 開獎時間：{s.draw_hour:02d}:{s.draw_minute:02d}"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(res_text, parse_mode="Markdown")
    else:
        await update.message.reply_text(res_text, parse_mode="Markdown")

# ── Callback Query Handler (數字鍵盤互動) ──

async def lottery_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    
    if not data.startswith("lot_"):
        return

    await query.answer()
    picks = context.user_data.get("lot_picks", [])

    if data.startswith("lot_num_"):
        num = int(data.split("_")[2])
        if num in picks:
            picks.remove(num)
        else:
            if len(picks) < 5:
                picks.append(num)
            else:
                await query.answer("最多只能選擇 5 個號碼！", show_alert=True)
                return
        
        context.user_data["lot_picks"] = picks
        
        if len(picks) == 5:
            # 選滿 5 個，自動下注
            picks.sort()
            await _execute_bet(update, context, picks)
            context.user_data["lot_picks"] = []
        else:
            # 更新鍵盤顯示已選號碼
            picks_text = ", ".join(map(str, sorted(picks))) if picks else "(無)"
            await query.edit_message_text(
                f"🎯 **請選擇 5 個號碼：**\n目前已選：`{picks_text}`\n還需選擇：{5 - len(picks)} 個",
                reply_markup=get_number_keyboard(picks),
                parse_mode="Markdown"
            )

    elif data == "lot_quick":
        # 快速隨機
        picks = sorted(random.sample(range(1, 40), 5))
        await _execute_bet(update, context, picks)
        context.user_data["lot_picks"] = []

    elif data == "lot_clear":
        # 清除重選
        context.user_data["lot_picks"] = []
        await query.edit_message_text(
            "🎯 **請選擇 5 個號碼：**\n目前已選：(無)",
            reply_markup=get_number_keyboard([]),
            parse_mode="Markdown"
        )

    elif data == "lot_cancel":
        # 取消下注
        context.user_data["lot_picks"] = []
        await query.edit_message_text("已取消下注流程。")

# ── 其他選單功能 ──

async def lottery_balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prefix = _register(update)
    user = get_user(update.effective_user.id)
    await update.message.reply_text(f"{prefix}💰 你的餘額：{user['balance']} L幣")

async def lottery_daily_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prefix = _register(update)
    result = claim_daily_bonus(update.effective_user.id, lottery_settings.daily_bonus, today_str(), tz_now().isoformat())
    if result is None:
        await update.message.reply_text(f"{prefix}你今天已簽到過了，明天再來。")
        return
    await update.message.reply_text(f"{prefix}✅ 簽到成功，獲得 {lottery_settings.daily_bonus} L幣\n目前餘額：{result} L幣")

async def lottery_history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prefix = _register(update)
    rows = recent_bets(update.effective_user.id)
    if not rows:
        await update.message.reply_text(prefix + "你目前還沒有投注紀錄。")
        return
    lines = [prefix + "🧾 最近投注紀錄"]
    for row in rows:
        res = f"對中 {row['match_count']} 個 / +{row['prize']}" if row["match_count"] is not None else "尚未開獎"
        lines.append(f"{row['draw_date']}｜{row['numbers']}｜{res}")
    await update.message.reply_text("\n".join(lines))

async def lottery_result_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prefix = _register(update)
    draw = get_draw_by_date(today_str())
    if not draw:
        await update.message.reply_text(prefix + "今日尚未建立期別，也尚未開獎。")
        return
    if draw["status"] != "DRAWN":
        await update.message.reply_text(prefix + f"今日尚未開獎，預計 {draw['draw_time']} 開獎。")
        return
    await update.message.reply_text(prefix + f"🎯 今日開獎號碼：{draw['winning_numbers']}")

async def lottery_rank_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prefix = _register(update)
    rows = leaderboard(10)
    lines = [prefix + "🏆 L幣排行榜"]
    for idx, row in enumerate(rows, start=1):
        name = "@" + row["username"] if row["username"] else row["full_name"]
        lines.append(f'{idx}. {name} - {row["balance"]} L幣')
    await update.message.reply_text("\n".join(lines))

async def lottery_rules_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prefix = _register(update)
    s = lottery_settings
    await update.message.reply_text(
        prefix + "📘 **L幣 539 規則**\n\n"
        f"1) 從 1~39 選 5 個不重複號碼\n"
        f"2) 每注 {s.bet_price} L幣\n"
        f"3) 每天 {s.draw_hour:02d}:{s.draw_minute:02d} 開獎\n"
        f"4) 開獎前 {s.bet_cutoff_minutes} 分鐘停止投注\n\n"
        "💰 **獎金：**\n"
        f"對中 2 個 → {s.prize_match_2} L幣\n"
        f"對中 3 個 → {s.prize_match_3} L幣\n"
        f"對中 4 個 → {s.prize_match_4} L幣\n"
        f"對中 5 個 → {s.prize_match_5} L幣",
        parse_mode="Markdown"
    )

async def lottery_exit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """退出彩票模式，由外部 interactive_bot.py 處理選單切換"""
    # 此函數僅作為 handler 佔位，實際邏輯在 interactive_bot.py 中處理
    pass
