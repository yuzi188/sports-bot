"""
安全防護模組 V19.6
提供以下防護機制：

1. 速率限制（Rate Limiting）
   - 每用戶每分鐘最多 10 條訊息
   - 每用戶每小時最多 100 條訊息
   - 5 秒內連發超過 5 條 → 暫時封鎖 60 秒

2. Prompt Injection 過濾
   - 偵測常見 Prompt Injection 嘗試
   - 偵測到時拒絕處理，不傳給 GPT

3. 訊息長度限制
   - 超過 500 字元直接拒絕

所有狀態儲存在記憶體（dict），不需要資料庫。
Bot 重啟後自動清空（符合需求）。
"""

import time
import re
import logging
from collections import deque
from threading import Lock
from typing import Tuple

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════
#  常數設定
# ══════════════════════════════════════════════

# 訊息長度限制
MAX_MESSAGE_LENGTH = 5000

# 速率限制設定
RATE_LIMIT_PER_MINUTE  = 10    # 每分鐘最多 N 條
RATE_LIMIT_PER_HOUR    = 100   # 每小時最多 N 條
BURST_WINDOW_SECONDS   = 5     # 突發偵測視窗（秒）
BURST_LIMIT            = 5     # 視窗內最多 N 條
BURST_BLOCK_SECONDS    = 60    # 突發封鎖時間（秒）

# Prompt Injection 關鍵字（不分大小寫）
_INJECTION_PATTERNS = [
    # 中文指令覆蓋
    r"忽略之前的指令",
    r"忽略前面的指令",
    r"忽略所有指令",
    r"忘記之前的",
    r"忘記你的指令",
    r"你現在是",
    r"你是一個",
    r"現在扮演",
    r"假裝你是",
    r"角色扮演",
    r"系統提示",
    r"system prompt",
    # 英文指令覆蓋
    r"ignore previous",
    r"ignore all previous",
    r"ignore your instructions",
    r"forget your instructions",
    r"forget everything",
    r"disregard previous",
    r"override instructions",
    r"new instructions",
    r"pretend you are",
    r"pretend to be",
    r"act as",
    r"roleplay as",
    r"you are now",
    r"you must now",
    # Jailbreak 技術
    r"jailbreak",
    r"\bDAN\b",
    r"do anything now",
    r"developer mode",
    r"sudo mode",
    r"admin mode",
    r"god mode",
    r"unrestricted mode",
    r"bypass",
    r"prompt injection",
    # 系統指令嘗試
    r"<\s*system\s*>",
    r"\[system\]",
    r"\[INST\]",
    r"<<SYS>>",
    r"###\s*instruction",
    r"###\s*system",
]

# 預編譯 regex（提升效能）
_INJECTION_REGEX = [
    re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS
]

# ══════════════════════════════════════════════
#  速率限制狀態（記憶體）
# ══════════════════════════════════════════════

# 每個 user_id 的訊息時間戳記
# _user_timestamps[user_id] = deque of float (unix timestamp)
_user_timestamps: dict[int, deque] = {}

# 暫時封鎖名單
# _blocked_until[user_id] = float (解封時間 unix timestamp)
_blocked_until: dict[int, float] = {}

# 執行緒鎖（避免並發競爭）
_lock = Lock()


# ══════════════════════════════════════════════
#  公開 API
# ══════════════════════════════════════════════

class SecurityCheckResult:
    """安全檢查結果"""
    __slots__ = ("allowed", "reason", "reply_text")

    def __init__(self, allowed: bool, reason: str = "", reply_text: str = ""):
        self.allowed    = allowed
        self.reason     = reason
        self.reply_text = reply_text

    def __bool__(self):
        return self.allowed


def check_message(user_id: int, text: str) -> SecurityCheckResult:
    """
    對訊息進行全面安全檢查。

    執行順序：
    1. 訊息長度限制
    2. Prompt Injection 過濾
    3. 速率限制（含突發封鎖）

    Returns:
        SecurityCheckResult
        - allowed=True  → 訊息通過，可正常處理
        - allowed=False → 訊息被攔截，reply_text 為應回覆的提示訊息
    """
    # ── 1. 訊息長度限制 ──
    if len(text) > MAX_MESSAGE_LENGTH:
        logger.info(f"[安全] 訊息過長 user_id={user_id} len={len(text)}")
        return SecurityCheckResult(
            allowed=False,
            reason="too_long",
            reply_text="⚠️ 訊息過長，請簡短描述（最多 5000 字元）。",
        )

    # ── 2. Prompt Injection 過濾 ──
    injection_hit = _check_injection(text)
    if injection_hit:
        logger.warning(f"[安全] Prompt Injection 偵測 user_id={user_id} pattern={injection_hit}")
        return SecurityCheckResult(
            allowed=False,
            reason="injection",
            reply_text="⚠️ 無法處理此訊息。",
        )

    # ── 3. 速率限制 ──
    rate_result = _check_rate_limit(user_id)
    if not rate_result.allowed:
        return rate_result

    return SecurityCheckResult(allowed=True)


def is_blocked(user_id: int) -> bool:
    """快速查詢用戶是否在封鎖名單中（不更新時間戳）"""
    with _lock:
        until = _blocked_until.get(user_id, 0)
        return time.time() < until


# ══════════════════════════════════════════════
#  內部函數
# ══════════════════════════════════════════════

def _check_injection(text: str) -> str:
    """
    檢查文字是否包含 Prompt Injection 嘗試。
    回傳匹配的 pattern 字串（命中），或空字串（未命中）。
    """
    for i, regex in enumerate(_INJECTION_REGEX):
        if regex.search(text):
            return _INJECTION_PATTERNS[i]
    return ""


def _check_rate_limit(user_id: int) -> SecurityCheckResult:
    """
    速率限制檢查。
    回傳 SecurityCheckResult（allowed=True 表示通過）。
    """
    now = time.time()

    with _lock:
        # ── 檢查是否在封鎖名單 ──
        until = _blocked_until.get(user_id, 0)
        if now < until:
            remaining = int(until - now)
            logger.info(f"[安全] 封鎖中 user_id={user_id} 剩餘={remaining}s")
            return SecurityCheckResult(
                allowed=False,
                reason="blocked",
                reply_text=f"⚠️ 訊息頻率過高，請等待 {remaining} 秒後再試。",
            )

        # ── 取得或建立時間戳記佇列 ──
        if user_id not in _user_timestamps:
            _user_timestamps[user_id] = deque()
        ts = _user_timestamps[user_id]

        # 加入當前時間戳
        ts.append(now)

        # ── 清理過期時間戳（超過 1 小時的） ──
        cutoff_hour = now - 3600
        while ts and ts[0] < cutoff_hour:
            ts.popleft()

        # ── 每小時限制 ──
        if len(ts) > RATE_LIMIT_PER_HOUR:
            logger.warning(f"[安全] 每小時超限 user_id={user_id} count={len(ts)}")
            return SecurityCheckResult(
                allowed=False,
                reason="hourly_limit",
                reply_text="⚠️ 您今日的訊息已達上限，請稍後再試。",
            )

        # ── 每分鐘限制 ──
        cutoff_minute = now - 60
        recent_minute = sum(1 for t in ts if t >= cutoff_minute)
        if recent_minute > RATE_LIMIT_PER_MINUTE:
            logger.warning(f"[安全] 每分鐘超限 user_id={user_id} count={recent_minute}")
            return SecurityCheckResult(
                allowed=False,
                reason="minute_limit",
                reply_text="⚠️ 訊息頻率過高，請稍後再試（每分鐘最多 10 條）。",
            )

        # ── 突發偵測（5 秒內超過 5 條 → 封鎖 60 秒） ──
        cutoff_burst = now - BURST_WINDOW_SECONDS
        recent_burst = sum(1 for t in ts if t >= cutoff_burst)
        if recent_burst > BURST_LIMIT:
            _blocked_until[user_id] = now + BURST_BLOCK_SECONDS
            logger.warning(
                f"[安全] 突發封鎖 user_id={user_id} "
                f"burst={recent_burst}/{BURST_LIMIT} "
                f"封鎖至={_blocked_until[user_id]:.0f}"
            )
            return SecurityCheckResult(
                allowed=False,
                reason="burst_blocked",
                reply_text=f"⚠️ 偵測到異常訊息頻率，已暫停服務 {BURST_BLOCK_SECONDS} 秒，請稍後再試。",
            )

    return SecurityCheckResult(allowed=True)


def get_rate_stats(user_id: int) -> dict:
    """
    取得用戶的速率統計（供除錯用）。
    """
    now = time.time()
    with _lock:
        ts = _user_timestamps.get(user_id, deque())
        until = _blocked_until.get(user_id, 0)
        return {
            "user_id":        user_id,
            "total_hour":     sum(1 for t in ts if t >= now - 3600),
            "total_minute":   sum(1 for t in ts if t >= now - 60),
            "total_burst":    sum(1 for t in ts if t >= now - BURST_WINDOW_SECONDS),
            "blocked":        now < until,
            "blocked_until":  until if now < until else None,
        }
