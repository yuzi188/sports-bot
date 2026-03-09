"""
539 彩票開獎排程 - 整合版
每日 20:30 自動開獎並推送結果到群組
"""
from __future__ import annotations

import random
import logging
from collections import defaultdict

from modules.lottery.lottery_config import lottery_settings
from modules.lottery.repository import (
    get_or_create_today_draw,
    settle_draw,
    all_open_draw_bets,
)
from modules.lottery.utils import tz_now, numbers_to_text

logger = logging.getLogger(__name__)


def _winner_name(item: dict) -> str:
    return "@" + item["username"] if item.get("username") else item["full_name"]


async def draw_job(context):
    """每日 20:30 自動開獎任務"""
    now = tz_now()
    s = lottery_settings
    draw = get_or_create_today_draw(
        now.isoformat(), f"{s.draw_hour:02d}:{s.draw_minute:02d}"
    )
    if draw["status"] == "DRAWN":
        logger.info("[draw_job] 今日已開獎，跳過")
        return

    winning_numbers = sorted(random.sample(range(1, 40), 5))
    winning_text = numbers_to_text(winning_numbers)
    winners = settle_draw(
        draw["draw_id"], winning_text, s.prize_table, now.isoformat()
    )
    bets = all_open_draw_bets(draw["draw_id"])

    total_prize = sum(w["prize"] for w in winners)
    grouped = defaultdict(list)
    for winner in winners:
        grouped[winner["match_count"]].append(winner)

    lines = [
        "🎰 今日 539 開獎",
        "",
        f"號碼：{winning_text}",
        f"參與注數：{len(bets)}",
        f"發放獎金：{total_prize} L幣",
        "",
    ]

    if not winners:
        lines.append("本期無中獎玩家。")
    else:
        for match_count in sorted(grouped.keys(), reverse=True):
            label = {
                5: "🏆 五中",
                4: "🥈 四中",
                3: "🥉 三中",
                2: "✨ 二中",
            }.get(match_count, f"{match_count} 中")
            lines.append(label)
            for item in grouped[match_count]:
                lines.append(f"- {_winner_name(item)} +{item['prize']} L幣")
            lines.append("")

    msg = "\n".join(lines).strip()
    logger.info(f"[draw_job] 開獎完成: {winning_text}, 中獎人數: {len(winners)}")

    # 推送到群組（使用 sports-bot 的 GROUP_ID）
    from config import GROUP_ID
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    if GROUP_ID:
        try:
            # 加入 539 下注按鈕
            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎱 去 Bot 下注", url="https://t.me/LA1111_bot?start=539")]
            ])
            await context.bot.send_message(
                chat_id=GROUP_ID, 
                text=msg, 
                reply_markup=reply_markup
            )
            logger.info(f"[draw_job] 開獎結果已推送到群組 {GROUP_ID}")
        except Exception as e:
            logger.error(f"[draw_job] 群組推送失敗: {e}")
