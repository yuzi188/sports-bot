"""
clear_channel.py - 清除頻道舊訊息工具

說明：
  Telegram Bot API 不提供「取得頻道歷史訊息」的功能，
  因此採用以下策略：
  1. 嘗試刪除最近 N 個 message_id（從最新往舊推算）
  2. 透過 getUpdates 取得 Bot 收到的 update，找出 Bot 自己發的訊息
  3. 支援命令列參數指定刪除範圍

使用方式：
  python3 clear_channel.py                  # 嘗試刪除最近 200 則
  python3 clear_channel.py --count 500      # 嘗試刪除最近 500 則
  python3 clear_channel.py --from-id 1000 --to-id 1200  # 指定 ID 範圍

注意：
  - Bot 只能刪除自己發的訊息
  - 頻道訊息超過 48 小時後無法刪除（Telegram 限制）
  - 刪除失敗的訊息會靜默跳過
"""

import os
import sys
import time
import argparse
import requests
from config import BOT_TOKEN, CHANNEL_ID

API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


def get_bot_info() -> dict:
    """取得 Bot 資訊（包含 bot_id）"""
    resp = requests.get(f"{API_BASE}/getMe", timeout=10)
    data = resp.json()
    if data.get("ok"):
        return data["result"]
    return {}


def get_channel_info() -> dict:
    """取得頻道資訊，包含最新 message_id"""
    resp = requests.get(
        f"{API_BASE}/getChat",
        params={"chat_id": CHANNEL_ID},
        timeout=10,
    )
    data = resp.json()
    if data.get("ok"):
        return data["result"]
    return {}


def delete_message(chat_id: str, message_id: int) -> bool:
    """嘗試刪除單則訊息，回傳是否成功"""
    resp = requests.post(
        f"{API_BASE}/deleteMessage",
        json={"chat_id": chat_id, "message_id": message_id},
        timeout=10,
    )
    result = resp.json()
    return result.get("ok", False)


def get_latest_message_id() -> int:
    """
    透過發送一則訊息再立即刪除，取得目前最新的 message_id。
    這是取得頻道最新 message_id 的常見技巧。
    """
    # 發送一則空白訊息（Telegram 不允許空白，用空格代替）
    resp = requests.post(
        f"{API_BASE}/sendMessage",
        json={
            "chat_id": CHANNEL_ID,
            "text": "🔄 系統維護中，正在清理舊訊息...",
        },
        timeout=10,
    )
    data = resp.json()
    if data.get("ok"):
        msg_id = data["result"]["message_id"]
        # 立即刪除這則探測訊息
        delete_message(CHANNEL_ID, msg_id)
        return msg_id
    return 0


def clear_channel_messages(count: int = 200, from_id: int = None, to_id: int = None):
    """
    清除頻道訊息。

    Args:
        count: 從最新訊息往前嘗試刪除的數量（當 from_id/to_id 未指定時使用）
        from_id: 起始 message_id（包含）
        to_id: 結束 message_id（包含）
    """
    print(f"🔍 正在連接頻道 {CHANNEL_ID}...")

    # 取得 Bot 資訊
    bot_info = get_bot_info()
    if not bot_info:
        print("❌ 無法取得 Bot 資訊，請確認 BOT_TOKEN 是否正確")
        return

    print(f"✅ Bot: @{bot_info.get('username', '')} (ID: {bot_info.get('id', '')})")

    # 決定刪除範圍
    if from_id and to_id:
        start_id = from_id
        end_id = to_id
        print(f"📋 指定刪除範圍：message_id {start_id} ~ {end_id}")
    else:
        # 取得最新 message_id
        print("📡 正在取得最新訊息 ID...")
        latest_id = get_latest_message_id()
        if latest_id == 0:
            print("❌ 無法取得最新訊息 ID，請確認 Bot 是否為頻道管理員")
            return
        print(f"📌 最新訊息 ID：{latest_id}")
        end_id = latest_id
        start_id = max(1, latest_id - count)
        print(f"📋 嘗試刪除範圍：message_id {start_id} ~ {end_id}（共 {end_id - start_id + 1} 則）")

    # 逐一嘗試刪除
    deleted = 0
    failed = 0
    skipped = 0

    print("\n🗑️  開始刪除...")
    for msg_id in range(end_id, start_id - 1, -1):
        result = delete_message(CHANNEL_ID, msg_id)
        if result:
            deleted += 1
            if deleted % 10 == 0:
                print(f"  ✅ 已刪除 {deleted} 則（目前 ID: {msg_id}）")
        else:
            # 刪除失敗可能是：非 Bot 訊息、超過 48 小時、ID 不存在
            failed += 1

        # 避免觸發 Telegram 速率限制（每秒最多 30 個請求）
        time.sleep(0.05)

    print(f"\n📊 清除結果：")
    print(f"  ✅ 成功刪除：{deleted} 則")
    print(f"  ⏭️  無法刪除（非 Bot 訊息或超時）：{failed} 則")
    print(f"\n完成！")


def clear_via_updates():
    """
    透過 getUpdates 取得 Bot 收到的 channel_post update，
    找出 Bot 自己發的訊息並刪除。
    適用於 Bot 設定了 webhook 或有接收 channel_post 的情況。
    """
    print("📡 透過 getUpdates 取得頻道訊息...")
    resp = requests.get(
        f"{API_BASE}/getUpdates",
        params={"limit": 100, "allowed_updates": ["channel_post"]},
        timeout=10,
    )
    data = resp.json()
    if not data.get("ok"):
        print(f"❌ getUpdates 失敗：{data.get('description', '')}")
        return

    updates = data.get("result", [])
    print(f"📋 取得 {len(updates)} 個 update")

    deleted = 0
    for update in updates:
        channel_post = update.get("channel_post", {})
        if not channel_post:
            continue

        chat = channel_post.get("chat", {})
        # 確認是目標頻道
        if str(chat.get("username", "")) != CHANNEL_ID.lstrip("@") and \
           str(chat.get("id", "")) != str(CHANNEL_ID):
            continue

        msg_id = channel_post.get("message_id")
        if msg_id:
            if delete_message(CHANNEL_ID, msg_id):
                deleted += 1
                print(f"  ✅ 刪除訊息 ID: {msg_id}")
            time.sleep(0.05)

    print(f"\n透過 updates 刪除了 {deleted} 則訊息")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="清除 Telegram 頻道舊訊息")
    parser.add_argument(
        "--count", type=int, default=200,
        help="從最新訊息往前嘗試刪除的數量（預設 200）"
    )
    parser.add_argument(
        "--from-id", type=int, default=None,
        help="起始 message_id"
    )
    parser.add_argument(
        "--to-id", type=int, default=None,
        help="結束 message_id"
    )
    parser.add_argument(
        "--via-updates", action="store_true",
        help="透過 getUpdates 取得並刪除（適用於有 channel_post 的情況）"
    )

    args = parser.parse_args()

    if not BOT_TOKEN:
        print("❌ 請設定 BOT_TOKEN 環境變數")
        sys.exit(1)

    if args.via_updates:
        clear_via_updates()
    else:
        clear_channel_messages(
            count=args.count,
            from_id=args.from_id,
            to_id=args.to_id,
        )
