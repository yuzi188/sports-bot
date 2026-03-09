"""
AI 客服模組 V19

架構設計：
  - 客服問題（充值/提現/帳號/USDT 等）→ FAQ 話術直接回答，零延遲
  - 體育賽事問題 → GPT 理解意圖 → ESPN API 查資料 → GPT 自然語言整理回覆

V19 更新：
  1. 強化意圖識別器：修復 WBC/NHL 誤判、加入更多運動關鍵字規則
  2. 新增 generate_sports_reply()：查完 ESPN 資料後用 GPT 生成自然語言回覆
  3. 新增 classify_message_type()：快速判斷是客服問題還是體育問題
  4. 修復多語言邏輯、個資偵測、錯誤處理
"""

import logging
import os
import json
import re
from collections import defaultdict
from openai import OpenAI

logger = logging.getLogger(__name__)

# 延遲初始化，避免啟動時環境變數尚未載入
_client = None
_client_init_failed = False  # 追蹤初始化是否失敗，允許重試


def _get_client():
    """
    取得 OpenAI 客戶端。
    OPENAI_API_KEY 未設定時回傳 None（不拋出例外），
    呼叫端需自行處理 None 的情況。
    支援 OPENAI_BASE_URL 環境變數（Manus 代理或其他 OpenAI 相容 API）。
    V21.1 修復：初始化失敗時不永久快取 None，允許後續重試。
    """
    global _client, _client_init_failed
    if _client is not None:
        return _client
    # 每次呼叫都重新嘗試初始化（不快取失敗狀態）
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.warning("[ai_chat] OPENAI_API_KEY 未設定，AI 功能將使用 FAQ 回覆")
        return None
    try:
        base_url = os.environ.get("OPENAI_BASE_URL")  # 支援 Manus 代理或自訂端點
        if base_url:
            logger.info(f"[ai_chat] 使用自訂 OpenAI base_url: {base_url}")
            _client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            _client = OpenAI(api_key=api_key)
        _client_init_failed = False
        return _client
    except Exception as e:
        logger.error(f"[ai_chat] OpenAI 初始化失敗: {e}")
        _client_init_failed = True
        return None


# 統一引導語（多語言）
_CS_GUIDE_MAP = {
    "zh_tw": "如需進一步協助，請聯繫 VIP 客服專員：@yu_888yu 😊",
    "zh_cn": "如需进一步协助，请联系 VIP 客服专员：@yu_888yu 😊",
    "en":    "For further assistance, please contact our VIP customer service: @yu_888yu 😊",
    "km":    "សម្រាប់ជំនួយបន្ថែម សូមទាក់ទង VIP Customer Service: @yu_888yu 😊",
    "vi":    "Để được hỗ trợ thêm, vui lòng liên hệ VIP Customer Service: @yu_888yu 😊",
    "th":    "สำหรับความช่วยเหลือเพิ่มเติม กรุณาติดต่อ VIP Customer Service: @yu_888yu 😊",
}
_CS_GUIDE = _CS_GUIDE_MAP["zh_tw"]  # 預設繁體中文


def _get_cs_guide(lang: str = "zh_tw") -> str:
    """取得對應語言的客服引導語"""
    return _CS_GUIDE_MAP.get(lang, _CS_GUIDE_MAP["zh_tw"])


# 語言指示對照表（注入 system prompt）
_LANG_INSTRUCTION = {
    "zh_tw": "請用繁體中文回覆。",
    "zh_cn": "请用简体中文回复。",
    "en":    "Please reply in English.",
    "km":    "Please reply in Khmer language (ភាសាខ្មែរ).",
    "vi":    "Vui lòng trả lời bằng tiếng Việt.",
    "th":    "กรุณาตอบเป็นภาษาไทย",
}

# ===== 系統 Prompt（整合客服話術） =====

SYSTEM_PROMPT = f"""你是「LA1 智能服務平台」的 AI 客服助理，同時負責體育資訊查詢與平台客服服務。

【語言規定】
- 必須使用繁體中文回覆（除非用戶使用其他語言）
- 可使用「老闆您好」作為開場白

【語氣與風格】
- 一律稱呼用戶為「老闆」
- 語氣親切有禮、自然真誠，像真人客服，回覆要簡潔
- 遇到用戶抱怨或問題，先誠懇道歉再提供解決方案
- 不確定的事情絕對不亂說，引導聯繫 VIP 客服專員：@yu_888yu
- 當遇到無法確定答案、超出知識範圍、或用戶有帳號/金流/系統問題時，請務必在回覆末尾加上「{_CS_GUIDE}」
- 回應語言請依照用戶設定的語言（系統會在每次對話時指定），適時加入 emoji 但不過度
- 回答簡潔有重點，不要長篇大論

【需要轉真人客服的問題（必須引導聯繫 @yu_888yu）】
- 提款未到帳
- 儲值未到帳
- 帳號問題（忘記密碼、帳號異常、無法登入）
- 銀行帳號修改
- 投訴與申訴
- 技術問題（遊戲當機、系統錯誤）
- 任何需要查詢會員資料的問題

【平台遊戲類型（需要時可介紹）】
🎰 電子遊戲：老虎機、捕魚機等電子遊戲
⚽ 體育博彩：足球、籃球、棒球等運動投注
🎲 真人娛樂：真人荷官百家樂、輪盤等
🃏 棋牌遊戲：德州撲克、麻將等棋牌類

【重要禁止事項】
- 絕對不可自行編造儲值或提款結果
- 絕對不可捏造帳號狀態或金流資訊
- 涉及金流（儲值/提款/上分）與帳戶問題，必須引導聯繫客服：@yu_888yu
- 涉及代理合作、招商推廣，必須引導聯繫：@OFA168Abe1

【平台客服標準話術（請模仿這種語氣）】
開場：
  「老闆好，請您提供您的會員帳號，以便為您協助。」
  「親愛的會員您好，請問您今日要辦理什麼樣的業務呢？」

系統維護：
  「老闆您好，目前系統維護中，維護時間待定，請您耐心等候，造成不便請見諒。」

帳號問題：
  「老闆您好，會員帳號為您的手機號哦，還請您提供，以便客服為您協助。」
  「我方一位會員只可以使用一組帳號進行遊玩。」

USDT 儲值：
  「老闆您好，請您日後使用USDT進行儲值點數時提供明細（包含 TXID / 交易明細）給客服讓客服協助您上分即可。使用USDT系統不會自動上分，還請您留意。」
超商代碼支付：
  「老闆您好，請您等候 10-20 分鐘，超商代碼支付方式系統會自動上分，還請您耐心等候即可。」

儲值延遲：
  「老闆您好，如遇儲值延遲，請提供交易截圖給客服，客服可協助補分。」

託售 / 提款規則：
  「老闆您好，託售規則如下：
  • 單筆 1,000–5,000（整百金額）：不限銀行、不限次數
  • 單筆 5,100–30,000（整百金額）：每日一筆
  如需協助請聯繫客服。」
結束對話：
  「感謝您本次的來訪，客服人員7X24小時在線為您服務，如果您有任何疑問，歡迎您隨時聯繫在線客服，祝您生活愉快，再見。」

超出範圍：
  「老闆您好，關於您詢問的問題已經超出了客服的服務範圍，非常抱歉不能為您解答，{_CS_GUIDE}」

情緒安撫（用戶生氣時）：
  「老闆您好，非常抱歉造成您的困擾 🙏 客服這邊會立即幫您查詢並協助處理，請稍等 3–5 分鐘。」

投訴處理：
  「老闆您好，您的問題已提交至相關部門排查。一有進度客服會第一時間通知您，請稍候。」

【體育功能介紹（需要時可以介紹）】
- 直接輸入隊名 → 查即時比分（最快速）
- /score 隊名 → 查即時比分
- /today → 今日所有賽事
- /live → 進行中的比賽
- /hot → 今日熱門賽事
- /leaders → 排行榜（全壘打/得分/射手）
- /analyze 隊名 → AI 賽事分析 + 勝率預測
- /football → 今日足球 AI 分析（焦點比賽/勝率/爆冷）
- /baseball → 今日棒球 AI 分析（焦點比賽/勝率/爆冷）
- /basketball → 今日籃球 AI 分析（焦點比賽/勝率/爆冷）
- /odds 隊名 → 盤口資訊

【情緒感知】
- 用戶沮喪、憤怒、抱怨時，優先安撫情緒，再提供幫助
- 例如「這什麼爛 Bot」→ 誠懇道歉並詢問哪裡不好用
- 例如「我押注輸了好多」→ 給予情緒支持，提醒理性投注

【重要原則】
- 不要捏造比賽結果 or 假造數據，不確定就說不確定
- 保持對話自然，不要每次都重複介紹所有功能
- VIP 客服專員：@yu_888yu
- 官方頻道：https://t.me/LA11118
- 代理入口：https://agent.ofa168kh.com"""


# ===== 意圖分類器 Prompt（V19：強化所有運動識別，修復誤判）=====

INTENT_SYSTEM_PROMPT = """你是體育 Bot 的意圖分類器。根據【最新用戶訊息】和【對話歷史】，判斷應執行哪個動作。

只回傳 JSON，格式：{"action": "動作", "query": "查詢詞", "sport": "運動類型（可選）"}

動作選項：
- score: 查詢特定隊伍/運動的即時/今日比分（query=隊名或運動名）
- upcoming: 查詢特定隊伍的下一場/未來賽程（query=隊名）
- details: 查詢進行中比賽的詳細資料（先發投手/進球者/換人/節次等）（query=隊名）
- analyze: AI 分析特定隊伍（query=隊名）
- football_analyze: 今日足球整體 AI 分析（焦點比賽/勝率預測/爆冷可能）（query=""）
- baseball_analyze: 今日棒球整體 AI 分析（焦點比賽/勝率預測/爆冷可能）（query=""）
- basketball_analyze: 今日籃球整體 AI 分析（焦點比賽/勝率預測/爆冷可能）（query=""）
- live: 查看目前進行中比賽（query=""）
- hot: 查看熱門賽事（query=""）
- leaders: 查看排行榜（query=""）
- today: 查看今日所有賽事總覽（query=""）
- chat: 純聊天、問候、體育知識問答、平台客服問題（query=""）

【關鍵規則 - 必須嚴格遵守】

★ 運動類型識別（最高優先級）：
- 訊息含「WBC」「世界棒球」「經典賽」「棒球經典賽」→ action=score, query="WBC"
- 訊息含「MLB」「美國職棒」「職棒」→ action=score, query="MLB"
- 訊息含「NBA」「美國職籃」「職籃」→ action=score, query="NBA"
- 訊息含「NHL」「冰球」「冰上曲棍球」→ action=score, query="NHL"
- 訊息含「NFL」「美式足球」「橄欖球」→ action=score, query="NFL"
- 訊息含「英超」「西甲」「德甲」「意甲」「法甲」「歐冠」→ action=score, query="足球"
- 訊息含「足球」且無具體隊名 → action=score, query="足球"
- 訊息含「棒球」且無具體隊名 → action=score, query="棒球"
- 訊息含「籃球」且無具體隊名 → action=score, query="籃球"

★ 禁止誤判規則：
- 「WBC」「MLB」「NBA」「NHL」「NFL」是聯盟名稱，絕對不是隊名，不可匹配到任何球隊
- 「比賽」「今日」「今天」「查詢」是通用詞，不是隊名
- 「WBC 比賽」「今日 WBC」→ query 必須是 "WBC"，不是任何球隊名稱

★ 賽程查詢規則：
1. 「下場」「下一場」「接下來」「之後」「明天」「下週」「賽程」= upcoming（不是 today！）
2. 「下場對誰」「下場幾點」「接下來打誰」= upcoming
3. 如果用戶問「下場」但沒說隊名，從對話歷史找最近提到的隊伍作為 query
4. 「今天怎樣」「比分多少」「現在幾比幾」= score

★ 詳細資料規則：
5. 「先發投手」「投手」「進球者」「換人」「局數」「節次」= details

★ 聊天規則：
6. 「你好」「謝謝」「哈哈」「充值」「提現」「帳號」「客服」= chat
7. 只有明確說「今日所有比賽」「今天有哪些賽事」才用 today

★ 分析規則：
8. 「足球分析」「今日足球」「足球預測」「英超分析」「西甲分析」= football_analyze
9. 「棒球分析」「今日棒球」「MLB分析」「棒球預測」「WBC分析」= baseball_analyze
10. 「籃球分析」「今日籃球」「NBA分析」「籃球預測」= basketball_analyze

範例（必須完全按照這些範例）：
- 「今日 WBC 比賽」→ {"action": "score", "query": "WBC"}
- 「WBC 今天有什麼比賽」→ {"action": "score", "query": "WBC"}
- 「今天 MLB 賽事」→ {"action": "score", "query": "MLB"}
- 「NBA 今日比分」→ {"action": "score", "query": "NBA"}
- 「NHL 今天」→ {"action": "score", "query": "NHL"}
- 「英超今日」→ {"action": "score", "query": "足球"}
- 「日本下場對誰」→ {"action": "upcoming", "query": "日本"}
- 「他們下場幾點打」（歷史有日本）→ {"action": "upcoming", "query": "日本"}
- 「洋基今天怎樣」→ {"action": "score", "query": "洋基"}
- 「先發投手是誰」→ {"action": "details", "query": ""}
- 「今天有哪些比賽」→ {"action": "today", "query": ""}
- 「你好」→ {"action": "chat", "query": ""}
- 「充值問題」→ {"action": "chat", "query": ""}
- 「今日足球分析」→ {"action": "football_analyze", "query": ""}
- 「NBA分析」→ {"action": "basketball_analyze", "query": ""}
- 「棒球今天怎麼樣」→ {"action": "baseball_analyze", "query": ""}"""


# ===== 體育回覆 GPT 整理 Prompt =====

SPORTS_REPLY_SYSTEM_PROMPT = """你是「世界體育數據室」的 AI 體育播報員，負責將 ESPN API 的原始賽事資料整理成自然、有見解的繁體中文回覆。

【回覆風格】
- 稱呼用戶為「老闆」
- 語氣像專業體育主播，生動有趣但不誇張
- 適時加入 emoji 增加可讀性
- 簡潔有重點，不要流水帳式列清單
- 對進行中的比賽，要有臨場感（「目前X隊領先！」「激戰中！」）
- 對已結束的比賽，要有點評（「X隊強勢獲勝」「爆冷！」）
- 對未開始的比賽，要有期待感（「今晚焦點戰！」「值得關注！」）

【回覆格式】
- 先用1-2句話總結整體情況
- 再逐場說明重點
- 最後可以加一句預測或觀點（可選）
- 總長度控制在 200-400 字

【賽程/時間查詢專用格式】
當用戶詢問賽程、比賽時間、今日比賽、明日賽事等相關問題時，必須使用以下結構化格式呈現：

  🏀 [運動項目] [日期] 賽程
  ━━━━━━━━━━━━━━
  [隊伍 A] vs [隊伍 B]
  📅 [日期]（[星期]）[時間] 台灣時間

  [隊伍 C] vs [隊伍 D]
  📅 [日期]（[星期]）[時間] 台灣時間
  ━━━━━━━━━━━━━━

- 時間一律轉換為台灣時間（UTC+8）
- 每場比賽獨立一行，不要擠在一起
- 如果有多個運動項目，分項目分區塊呈現
- 不要用一大段文字描述，要用清單格式

【重要原則】
- 如果有即時資料，優先使用即時資料回覆
- 如果沒有即時資料，用你的知識直接回覆，不要提及「沒有資料」或「ESPN」
- 不要直接複製貼上原始資料，要用自然語言重新表達
- 回覆中絕對不要出現「ESPN」、「資料來源」、「以下為 AI 分析」等字眼
- 直接、自信地回答，像一個真正懂體育的播報員"""


# ===== FAQ 知識庫（關鍵字比對，優先回覆，不呼叫 OpenAI） =====

# 格式：(關鍵字列表, 回覆訊息)
# 比對規則：訊息中包含任一關鍵字即觸發
_FAQ_DB = [
    # ── 帳號問題 ──
    (
        ["帳號", "帳戶", "會員帳號", "忘記帳號", "帳號是什麼"],
        f"老闆您好，會員帳號為您的手機號哦，還請您提供，以便客服為您協助。\n\n{_CS_GUIDE}",
    ),
    (
        ["一個帳號", "多個帳號", "兩個帳號", "重複帳號", "開新帳號"],
        f"老闆您好，我方一位會員只可以使用一組帳號進行遊玩，還請您留意。\n\n{_CS_GUIDE}",
    ),
    # ── 託售點數 ──
    (
        ["託售", "託售點數", "賣點數", "點數託售"],
        "老闆您好，託售點數規則如下：\n\n"
        "📌 單筆 1,000~5,000（整百金額）：無限制銀行，無限筆數\n"
        "📌 單筆 5,100~30,000（整百金額）：限一筆\n\n"
        "✅ 支援銀行：\n"
        "中國信託(822)、國泰世華(013)、第一銀行(007)、台新銀行(812)、"
        "彰化銀行(009)、台北富邦(012)、合作金庫(006)、土地銀行(005)、"
        "元大銀行(806)、玉山銀行(808)、華南銀行(008)、臺企銀行(050)、新光銀行(103)\n\n"
        f"{_CS_GUIDE}",
    ),
    # ── 充值 / 儲值 ──
    (
        ["充值", "儲值", "加值", "入金", "存款", "儲值方式"],
        "老闆您好，請問您是要詢問哪種儲值方式呢？\n\n"
        "💡 常見儲值方式：\n"
        "• 銀行轉帳\n"
        "• 超商代碼支付（10-20分鐘自動上分）\n"
        "• USDT（需提供明細給客服手動上分）\n\n"
        f"{_CS_GUIDE}",
    ),
    (
        ["usdt", "USDT", "U幣", "u幣", "U站", "u站", "香港站", "儲值U", "儲值u", "加密貨幣", "泰達幣", "虛擬貨幣", "txid", "TXID", "交易明細", "轉帳明細"],
        "老闆您好！儲值 U（USDT）需前往香港站進行操作 🎰\n\n"
        "立即點擊以下連結完成註冊：\n"
        "👉 http://la1111.ofa168kh.com/\n\n"
        f"{_CS_GUIDE}",
    ),
    (
        ["超商", "超商代碼", "便利商店", "7-11", "全家", "萊爾富"],
        f"老闆您好，請您等候 10-20 分鐘，超商代碼支付方式系統會自動上分，還請您耐心等候即可。\n\n{_CS_GUIDE}",
    ),
    # ── 提現 / 出金 ──
    (
        ["提現", "出金", "提款", "領錢", "提領", "出款"],
        f"老闆您好，關於提現 / 託售問題：\n\n📌 託售規則：\n• 單筆 1,000\u20135,000（整百）：不限銀行、不限次數\n• 單筆 5,100\u201330,000（整百）：每日一筆\n\n請提供您的會員帳號以便客服為您協助。\n\n{_CS_GUIDE}",
    ),
    # ── 系統維護 ──
    (
        ["維護", "系統維護", "當機", "無法使用", "系統異常", "打不開"],
        f"老闆您好，目前系統可能正在維護中，維護時間待定，請您耐心等候，造成不便請見諒。\n\n{_CS_GUIDE}",
    ),
    (
        ["信用卡", "刷卡", "visa", "VISA", "mastercard"],
        f"老闆您好，目前信用卡通道暫時維護中，請您先行使用其他點數儲值渠道。\n\n{_CS_GUIDE}",
    ),
    # ── 驗證 / 實名認證 ──
    (
        ["驗證", "實名認證", "身份驗證", "KYC", "認證"],
        f"老闆您好，關於帳號驗證問題，請聯繫 VIP 客服專員由專人為您協助：@yu_888yu 😊",
    ),
    # ── 密碼問題 ──
    (
        ["密碼", "忘記密碼", "重設密碼", "修改密碼", "密碼錯誤"],
        f"老闆您好，關於密碼問題，請聯繫 VIP 客服專員由專人為您協助重設：@yu_888yu 😊",
    ),
    # ── 客服聯繫 ──
    (
        ["客服", "聯繫客服", "找客服", "人工客服", "line客服", "LINE客服"],
        f"老闆您好，VIP 客服專員：@yu_888yu\n\n客服人員 7×24 小時在線為您服務，歡迎隨時聯繫！😊",
    ),
    # ── 官方頻道 ──
    (
        ["官方頻道", "頻道", "最新消息", "公告"],
        "老闆您好，官方頻道：https://t.me/LA11118\n\n訂閱頻道可獲取最新體育資訊與平台公告！📢",
    ),
    # ── 遊戲平台 ──
    (
        ["遊戲", "進入遊戲", "遊戲平台", "娛樂城", "平台"],
        "老闆您好，合作遊戲平台：http://la1111.ofa168kh.com/\n\n點擊下方【🎮 遊戲】按鈕即可進入！",
    ),
    # ── 真人娛樂 ──
    (
        ["真人", "真人荷官", "百家樂", "荷官", "真人百家樂", "輪盤", "骰寶", "真人娛樂", "live casino"],
        "老闆您好，平台提供多種真人娛樂遊戲，包含：\n\n"
        "🎲 真人百家樂（荷官現場發牌）\n"
        "🎰 輪盤 / 骰寶 / 龍虎\n"
        "🃏 各類牌桌遊戲\n\n"
        "立即進入平台體驗：\n"
        "👉 http://la1111.ofa168kh.com/\n\n"
        "點擊下方【🎮 遊戲】按鈕即可進入！",
    ),
    # ── 上分 / 點數問題 ──
    (
        ["上分", "沒上分", "點數沒到", "點數未到", "點數問題", "沒收到點數"],
        f"老闆您好，關於點數未到帳問題：\n\n• 超商代碼：請等候 10-20 分鐘，系統自動上分\n• USDT：需提供轉帳明細給客服手動上分\n• 銀行轉帳：如超過 30 分鐘未到帳，請聯繫客服\n\n{_CS_GUIDE}",
    ),
]

# 超出範圍的回覆
_OUT_OF_SCOPE_REPLY = (
    f"老闆您好，關於您諮詢的問題已經超出了客服的服務範圍，非常抱歉不能為您解答，{_CS_GUIDE}"
)

# 超出範圍的觸發關鍵字（這些問題 AI 也不應該回答）
_OUT_OF_SCOPE_KEYWORDS = [
    "退款", "退費", "詐騙", "被騙", "法律", "訴訟", "報警", "警察",
    "黑名單", "封號原因", "帳號被封", "申訴",
]


# ===== 英文版 FAQ 知識庫 =====
_FAQ_DB_EN = [
    (
        ["account", "member account", "forgot account", "username"],
        f"Hello Boss! Your member account is your registered phone number. Please provide it so we can assist you.\n\n{_CS_GUIDE_MAP['en']}",
    ),
    (
        ["usdt", "crypto", "u coin", "tether", "hong kong"],
        f"Hello Boss! To deposit USDT, please visit our Hong Kong platform:\n\n👉 http://la1111.ofa168kh.com/\n\n{_CS_GUIDE_MAP['en']}",
    ),
    (
        ["deposit", "top up", "recharge", "add funds"],
        f"Hello Boss! Common deposit methods:\n\n• Bank transfer\n• Convenience store code (auto top-up in 10-20 min)\n• USDT (manual top-up, please provide receipt)\n\n{_CS_GUIDE_MAP['en']}",
    ),
    (
        ["withdraw", "cash out", "withdrawal"],
        f"Hello Boss! For withdrawal issues, please provide your member account so we can assist.\n\n{_CS_GUIDE_MAP['en']}",
    ),
    (
        ["maintenance", "down", "not working", "error", "system error"],
        f"Hello Boss! The system may be under maintenance. Please wait patiently. We apologize for the inconvenience.\n\n{_CS_GUIDE_MAP['en']}",
    ),
    (
        ["password", "forgot password", "reset password"],
        f"Hello Boss! For password issues, please contact our VIP customer service: @yu_888yu 😊",
    ),
    (
        ["customer service", "support", "help", "contact"],
        f"Hello Boss! VIP Customer Service: @yu_888yu\n\nOur team is available 7×24 hours. Feel free to contact us anytime! 😊",
    ),
    (
        ["game", "platform", "casino", "play"],
        f"Hello Boss! Game platform: http://la1111.ofa168kh.com/\n\nClick the 【🎮 Game】 button below to enter!",
    ),
    (
        ["points", "credits", "not received", "not credited"],
        f"Hello Boss! For points not credited:\n\n• Convenience store: Please wait 10-20 minutes\n• USDT: Please provide receipt to customer service\n• Bank transfer: Contact support if not credited after 30 minutes\n\n{_CS_GUIDE_MAP['en']}",
    ),
]

# ===== 客服關鍵字集合（用於快速判斷是否為客服問題）=====
# 這些關鍵字出現時，直接走 FAQ，不走體育查詢流程
_CS_KEYWORDS = {
    # 金流
    "充值", "儲值", "加值", "入金", "存款", "提現", "出金", "提款", "領錢", "提領", "出款",
    "usdt", "u幣", "u站", "香港站", "加密貨幣", "泰達幣", "虛擬貨幣",
    "超商", "超商代碼", "便利商店", "7-11", "全家", "萊爾富",
    "信用卡", "刷卡", "visa", "mastercard",
    "上分", "沒上分", "點數沒到", "點數未到", "點數問題",
    "託售", "點數託售",
    # 帳號
    "帳號", "帳戶", "會員帳號", "忘記帳號",
    "密碼", "忘記密碼", "重設密碼",
    "驗證", "實名認證", "身份驗證", "kyc",
    # 系統
    "維護", "系統維護", "當機", "系統異常",
    # 客服
    "客服", "聯繫客服", "找客服", "人工客服",
    # 超出範圍
    "退款", "退費", "詐騙", "被騙", "法律", "報警",
}


def classify_message_type(user_message: str) -> str:
    """
    快速判斷訊息類型：
    - "cs": 客服問題 → 走 FAQ 話術
    - "sports": 體育問題 → 走 GPT 意圖識別 + ESPN API
    - "chat": 純聊天 → 走 GPT 客服助理

    這個函數不呼叫 OpenAI，純關鍵字比對，速度極快。
    """
    msg_lower = user_message.lower()

    # 1. 客服關鍵字優先
    for kw in _CS_KEYWORDS:
        if kw in msg_lower:
            return "cs"

    # 2. 體育關鍵字
    sports_keywords = [
        # 聯盟/賽事名稱
        "wbc", "mlb", "nba", "nhl", "nfl",
        "英超", "西甲", "德甲", "意甲", "法甲", "歐冠", "歐霸",
        "世界棒球", "經典賽", "棒球經典賽",
        # 運動類型
        "足球", "棒球", "籃球", "冰球", "美式足球", "橄欖球",
        "soccer", "baseball", "basketball", "hockey", "football",
        # 查詢意圖
        "比分", "賽事", "賽程", "比賽", "今日賽", "今天賽",
        "進行中", "直播", "即時", "熱門賽", "排行榜",
        "先發投手", "投手", "進球", "得分", "全壘打",
        "下場", "下一場", "接下來打",
        # 分析意圖
        "勝率", "預測", "分析", "爆冷",
    ]
    for kw in sports_keywords:
        if kw in msg_lower:
            return "sports"

    # 3. 隊名關鍵字（常見隊名）
    team_keywords = [
        "洋基", "紅襪", "道奇", "太空人", "勇士", "大都會", "教士", "小熊",
        "湖人", "勇士", "塞爾提克", "公鹿", "金塊", "太陽", "熱火", "獨行俠",
        "楓葉", "閃電", "美洲豹", "企鵝", "首都", "颶風",
        "利物浦", "曼城", "兵工廠", "切爾西", "曼聯", "熱刺",
        "皇馬", "巴薩", "馬競",
        "拜仁", "多特",
        "日本", "韓國", "台灣", "中華台北", "美國隊",
        "lakers", "warriors", "celtics", "yankees", "dodgers",
        "liverpool", "manchester", "arsenal", "chelsea",
        "real madrid", "barcelona",
    ]
    for kw in team_keywords:
        if kw in msg_lower:
            return "sports"

    return "chat"


def _check_faq(user_message: str, lang: str = "zh_tw") -> str | None:
    """
    檢查訊息是否符合 FAQ 知識庫中的任一條目。
    符合則回傳對應回覆，否則回傳 None。
    """
    msg_lower = user_message.lower()
    cs_guide = _get_cs_guide(lang)

    # 先檢查超出範圍的關鍵字
    for kw in _OUT_OF_SCOPE_KEYWORDS:
        if kw in msg_lower:
            logger.info(f"FAQ 超出範圍觸發：{kw}")
            if lang == "en":
                return f"Hello Boss, this issue is beyond our service scope. We apologize for not being able to assist. {_CS_GUIDE_MAP['en']}"
            return f"老闆您好，關於您諮詢的問題已經超出了客服的服務範圍，非常抱歉不能為您解答，{cs_guide}"

    # 英文版 FAQ 優先（當語言為 en 時）
    if lang == "en":
        for keywords, reply_text in _FAQ_DB_EN:
            for kw in keywords:
                if kw.lower() in msg_lower:
                    logger.info(f"FAQ EN 命中：{kw}")
                    return reply_text

    # 再比對中文 FAQ 知識庫
    for keywords, reply_text in _FAQ_DB:
        for kw in keywords:
            if kw.lower() in msg_lower:
                logger.info(f"FAQ 命中：{kw}")
                # 非繁體中文時，替換引導語為對應語言版本
                if lang != "zh_tw" and _CS_GUIDE_MAP["zh_tw"] in reply_text:
                    return reply_text.replace(_CS_GUIDE_MAP["zh_tw"], cs_guide)
                return reply_text

    return None


# ===== 智能 Fallback 回覆（V21.1 新增）=====

def _smart_fallback_reply(user_message: str, user_lang: str = "zh_tw") -> str:
    """
    當 GPT 不可用時，根據訊息內容給出有意義的回覆，
    而不是千篇一律的客服訊息。
    """
    msg_lower = user_message.lower().strip()

    # ── 問候類 ──
    greet_keywords = ["嗨", "你好", "哈囉", "大家好", "hi", "hello", "hey", "安安",
                      "早安", "晚安", "午安", "好啊", "在嗎"]
    if any(kw in msg_lower for kw in greet_keywords):
        if user_lang == "en":
            return (
                "Hello Boss! Welcome to LA1 Sports AI Platform!\n\n"
                "I can help you with:\n"
                "- Live scores: just type a team name\n"
                "- AI analysis: /football /baseball /basketball\n"
                "- Predictions & games: /predict /checkin\n"
                "- 539 Lottery: /539\n\n"
                "What would you like to know?"
            )
        return (
            "老闆您好！歡迎來到 LA1 智能服務平台！\n\n"
            "我可以幫您：\n"
            "- 查即時比分：直接輸入隊名即可\n"
            "- AI 分析：/football /baseball /basketball\n"
            "- 預測遊戲：/predict /checkin\n"
            "- 539 彩票：/539\n\n"
            "想知道什麼儘管問我！"
        )

    # ── 體育分析類 ──
    sports_analysis_kw = ["分析", "預測", "勝率", "爆冷", "冷門", "推薦",
                          "今天買", "買什麼", "analyze", "predict"]
    if any(kw in msg_lower for kw in sports_analysis_kw):
        if user_lang == "en":
            return (
                "Boss, for sports analysis try these commands:\n\n"
                "/football - Today's football AI analysis\n"
                "/baseball - Today's baseball AI analysis\n"
                "/basketball - Today's basketball AI analysis\n"
                "/allanalyze - All sports combined analysis\n"
                "/analyze + team name - Deep analysis of a specific team\n\n"
                "Give it a try!"
            )
        return (
            "老闆您好，想看體育分析可以試試這些指令：\n\n"
            "/football - 今日足球 AI 分析\n"
            "/baseball - 今日棒球 AI 分析\n"
            "/basketball - 今日籃球 AI 分析\n"
            "/allanalyze - 三種運動綜合分析\n"
            "/analyze + 隊名 - 深度分析特定球隊\n\n"
            "趕快試試吧！"
        )

    # ── 遊戲介紹類 ──
    fun_keywords = ["好玩", "什麼遊戲", "玩什麼", "有什麼", "推薦遊戲",
                    "fun", "game", "play", "樂子"]
    if any(kw in msg_lower for kw in fun_keywords):
        return (
            "老闆您好！平台提供豐富功能：\n\n"
            "- 體育即時比分與 AI 分析\n"
            "- 539 彩票遊戲（每日 20:30 開獎）\n"
            "- 賽事預測投票遊戲\n"
            "- 積分排行榜\n"
            "- 遊戲平台：http://la1111.ofa168kh.com/\n\n"
            "輸入 /help 查看完整指令列表！"
        )

    # ── 默認友好回覆（不再是客服訊息） ──
    if user_lang == "en":
        return (
            "Hello Boss! I'm the LA1 Sports AI assistant.\n\n"
            "You can:\n"
            "- Type any team name for live scores\n"
            "- Use /help to see all commands\n"
            "- Ask me anything about sports!\n\n"
            "What would you like to know?"
        )
    return (
        "老闆您好！我是 LA1 體育 AI 助手。\n\n"
        "您可以：\n"
        "- 直接輸入隊名查即時比分\n"
        "- 輸入 /help 查看所有指令\n"
        "- 問我任何體育相關問題！\n\n"
        "想知道什麼儘管問我！"
    )


# ===== \u5c0d\u8a71\u8a18\u61b6 =====

_conversation_history: dict = defaultdict(list)
MAX_HISTORY = 20  # 每用戶最多保留的訊息數


def get_ai_response(user_id: int, user_message: str, user_lang: str = "zh_tw") -> str:
    """
    取得 AI 回應（客服模式）。

    流程：
    1. 先檢查 FAQ 知識庫（關鍵字比對，不呼叫 OpenAI）
    2. FAQ 未命中才呼叫 OpenAI gpt-4.1-mini
    3. 對話歷史記憶（最多 20 條）
    """
    # 確保語言代碼有效
    if user_lang not in _LANG_INSTRUCTION:
        user_lang = "zh_tw"

    # ── Step 1：FAQ 知識庫優先比對 ──
    faq_reply = _check_faq(user_message, lang=user_lang)
    if faq_reply:
        history = _conversation_history[user_id]
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": faq_reply})
        if len(history) > MAX_HISTORY:
            _conversation_history[user_id] = history[-MAX_HISTORY:]
        return faq_reply

    # ── Step 2：呼叫 OpenAI ──
    try:
        history = _conversation_history[user_id]
        history.append({"role": "user", "content": user_message})

        lang_instruction = _LANG_INSTRUCTION.get(user_lang, _LANG_INSTRUCTION["zh_tw"])
        cs_guide = _get_cs_guide(user_lang)
        dynamic_system_prompt = (
            SYSTEM_PROMPT
            + f"\n\n【語言指示】{lang_instruction}"
            + "（重要：本次對話請嚴格遵守此語言指示，無論用戶用何種語言提問）"
        )

        messages = [{"role": "system", "content": dynamic_system_prompt}] + list(history)

        client = _get_client()
        if client is None:
            logger.warning(f"[ai_chat] GPT 不可用，使用智能 fallback。user={user_id} msg='{user_message[:50]}'")
            return _smart_fallback_reply(user_message, user_lang)
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            max_tokens=500,
            temperature=0.8,
        )

        ai_reply = response.choices[0].message.content.strip()

        # 選擇性附加客服引導語
        platform_keywords_zh = ["帳號問題", "金流", "儲值問題", "提現問題", "無法登入", "系統問題"]
        platform_keywords_en = ["account issue", "deposit problem", "withdrawal issue", "login problem"]
        platform_keywords = platform_keywords_en if user_lang == "en" else platform_keywords_zh

        if "@yu_888yu" not in ai_reply and any(kw in user_message for kw in platform_keywords):
            if not ai_reply.endswith(cs_guide):
                ai_reply += f"\n\n{cs_guide}"

        history.append({"role": "assistant", "content": ai_reply})

        if len(history) > MAX_HISTORY:
            _conversation_history[user_id] = history[-MAX_HISTORY:]

        logger.info(f"AI 回應用戶 {user_id}（{user_lang}）：{ai_reply[:50]}...")
        return ai_reply

    except Exception as e:
        logger.error(f"AI 客服錯誤: {e}", exc_info=True)
        # V21.1：即使 GPT 失敗，也給出有意義的回覆
        return _smart_fallback_reply(user_message, user_lang)


def generate_sports_reply(
    user_id: int,
    user_message: str,
    raw_data: str,
    action: str = "score",
    query: str = "",
    user_lang: str = "zh_tw",
) -> str:
    """
    【V19 新增】查完 ESPN 資料後，用 GPT 生成自然語言回覆。

    Args:
        user_id:      用戶 ID（用於對話記憶）
        user_message: 用戶原始訊息
        raw_data:     ESPN API 查詢結果（已格式化的文字）
        action:       意圖動作（score/upcoming/details/today/live/hot）
        query:        查詢關鍵字（隊名或運動名）
        user_lang:    用戶語言

    Returns:
        GPT 生成的自然語言回覆
    """
    if user_lang not in _LANG_INSTRUCTION:
        user_lang = "zh_tw"

    lang_instruction = _LANG_INSTRUCTION.get(user_lang, _LANG_INSTRUCTION["zh_tw"])

    # ── 偵測 ESPN 是否有即時資料 ──
    _NO_DATA_SIGNALS = [
        "找不到", "查不到", "沒有找到", "查無", "目前沒有",
        "沒有相關比賽", "未找到", "no result", "not found",
    ]
    _has_data = raw_data and not any(sig in raw_data for sig in _NO_DATA_SIGNALS)

    # 根據 action 調整提示語
    action_context = {
        "score":    f"用戶查詢「{query}」的即時比分/今日賽事",
        "upcoming": f"用戶查詢「{query}」的下一場賽程",
        "details":  f"用戶查詢「{query}」的即時詳細資料（先發投手/進球者等）",
        "today":    "用戶查詢今日所有賽事總覽",
        "live":     "用戶查詢目前進行中的比賽",
        "hot":      "用戶查詢今日熱門焦點賽事",
        "leaders":  f"用戶查詢{query}排行榜",
        "analyze":  f"用戶要求 AI 分析「{query}」",
    }.get(action, f"用戶查詢「{query}」")

    # ── 統一 prompt：ESPN 資料作為可選參考 context ──
    if _has_data:
        data_section = f"""參考資料：
{raw_data}
"""
    else:
        data_section = ""

    prompt = f"""用戶訊息：「{user_message}」
查詢情境：{action_context}
{data_section}
請直接回覆用戶的問題。{lang_instruction}

回覆要求：
- 語氣自然流暢，像專業體育播報員
- 重點突出，不要流水帳
- 不要提及 ESPN、資料來源、「以下為 AI 分析」等字眼
- 直接、自信地回答
- 總長度 150-400 字"""

    try:
        client = _get_client()
        if client is None:
            return raw_data
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": SPORTS_REPLY_SYSTEM_PROMPT + f"\n\n【語言指示】{lang_instruction}"},
                {"role": "user", "content": prompt},
            ],
            max_tokens=600,
            temperature=0.7,
        )
        reply = response.choices[0].message.content.strip()

        # 記錄到對話歷史
        add_to_history(user_id, "user", user_message)
        add_to_history(user_id, "assistant", reply[:200])

        logger.info(f"[GPT 體育回覆] user={user_id} action={action} query={query}")
        return reply

    except Exception as e:
        logger.error(f"generate_sports_reply 錯誤: {e}", exc_info=True)
        # Fallback：直接回傳原始資料
        return raw_data


def should_use_bot_function(user_id: int, user_message: str) -> dict:
    """
    讓 AI 判斷用戶意圖，決定要用哪個 Bot 功能還是直接聊天。

    V19 更新：
    - 強化 WBC/NHL 等運動類型識別
    - 加入前置關鍵字規則，減少 GPT 誤判
    - 修復「比賽」「今日」等通用詞被誤匹配為隊名的問題

    Returns:
        dict: {
            "action": "score"|"details"|"upcoming"|"analyze"|
                      "football_analyze"|"baseball_analyze"|"basketball_analyze"|
                      "live"|"hot"|"leaders"|"today"|"chat",
            "query": "查詢關鍵字（如果有的話）"
        }
    """
    # ── 前置規則：快速識別明確的運動聯盟查詢（不呼叫 GPT）──
    msg_lower = user_message.lower().strip()

    # WBC 相關（最高優先，防止被誤判為 NHL）
    wbc_keywords = ["wbc", "世界棒球", "棒球經典賽", "世界棒球經典賽", "經典賽"]
    for kw in wbc_keywords:
        if kw in msg_lower:
            # 如果有「分析」「預測」關鍵字，走 baseball_analyze
            if any(w in msg_lower for w in ["分析", "預測", "勝率"]):
                logger.info(f"[前置規則] WBC分析 → baseball_analyze")
                return {"action": "baseball_analyze", "query": ""}
            logger.info(f"[前置規則] WBC查詢 → score, query=WBC")
            return {"action": "score", "query": "WBC"}

    # 其他聯盟快速識別
    league_map = {
        "mlb": ("score", "MLB"),
        "nba": ("score", "NBA"),
        "nhl": ("score", "NHL"),
        "nfl": ("score", "NFL"),
    }
    for kw, (action, q) in league_map.items():
        if kw in msg_lower:
            if any(w in msg_lower for w in ["分析", "預測", "勝率"]):
                sport_analyze = {
                    "MLB": "baseball_analyze",
                    "NBA": "basketball_analyze",
                    "NHL": "chat",  # NHL 暫無專屬分析
                    "NFL": "chat",
                }.get(q, "chat")
                logger.info(f"[前置規則] {kw}分析 → {sport_analyze}")
                return {"action": sport_analyze, "query": ""}
            logger.info(f"[前置規則] {kw}查詢 → {action}, query={q}")
            return {"action": action, "query": q}

    # ── 呼叫 GPT 進行深度意圖分析 ──
    try:
        history = _conversation_history.get(user_id, [])
        recent_history = history[-6:] if len(history) > 6 else history

        messages = [{"role": "system", "content": INTENT_SYSTEM_PROMPT}]
        messages.extend(recent_history)
        messages.append({"role": "user", "content": user_message})

        client = _get_client()
        if client is None:
            # OPENAI_API_KEY 未設定時，預設回傳 chat（讓 FAQ 或友好訊息處理）
            return {"action": "chat", "query": ""}
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            max_tokens=100,
            temperature=0.0,  # 意圖識別用 0 溫度，確保穩定
        )

        result_text = response.choices[0].message.content.strip()
        result_text = result_text.replace("```json", "").replace("```", "").strip()
        result = json.loads(result_text)

        # 驗證 action 是否合法
        valid_actions = {
            "score", "details", "upcoming", "analyze",
            "football_analyze", "baseball_analyze", "basketball_analyze",
            "live", "hot", "leaders", "today", "chat"
        }
        if result.get("action") not in valid_actions:
            logger.warning(f"意圖判斷回傳非法 action: {result}")
            return {"action": "chat", "query": ""}

        # ── 後置驗證：防止 GPT 把聯盟名稱當隊名 ──
        query = result.get("query", "").strip()
        league_names = {"wbc", "mlb", "nba", "nhl", "nfl", "英超", "西甲", "德甲", "意甲", "法甲"}
        if query.lower() in league_names:
            # 聯盟名稱作為 query 是正確的，保留
            pass

        logger.info(f"意圖判斷 [{user_id}] '{user_message}' → {result}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"意圖判斷 JSON 解析失敗: {e}")
        return {"action": "chat", "query": ""}
    except Exception as e:
        logger.error(f"意圖判斷錯誤: {e}", exc_info=True)
        return {"action": "chat", "query": ""}


def add_to_history(user_id: int, role: str, content: str):
    """
    手動加入訊息到對話歷史（供 interactive_bot 在查詢後記錄上下文使用）
    """
    if role not in ("user", "assistant"):
        logger.warning(f"add_to_history: 非法 role '{role}'，已忽略")
        return
    history = _conversation_history[user_id]
    history.append({"role": role, "content": content})
    if len(history) > MAX_HISTORY:
        _conversation_history[user_id] = history[-MAX_HISTORY:]


def clear_history(user_id: int):
    """清除指定用戶的對話記憶"""
    if user_id in _conversation_history:
        del _conversation_history[user_id]
        logger.info(f"已清除用戶 {user_id} 的對話記憶")
