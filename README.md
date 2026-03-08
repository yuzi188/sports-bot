# 體育分析機器人系統說明書 V18

這是一套為 Telegram 頻道「世界體育數據室 | Sports Analytics Hub」（@LA11118）打造的自動化體育數據與分析系統。系統結合了即時體育數據 API 與 AI 分析能力，能夠自動抓取賽事資訊、生成專業分析，並定時發布到指定的 Telegram 頻道。此外，系統支援互動式即時比分查詢，頻道會員可直接私訊機器人查詢任何正在進行或即將開始的比賽。

## 版本更新記錄

### V18（2026/03/08）— 三大系統整合版

本次更新靈感來源：[playsport.cc](https://www.playsport.cc) 的會員積分系統、預測記錄追蹤、勝率統計面板與群體行為分析功能。

**新增功能：**

| 功能 | 指令 | 說明 |
| :--- | :--- | :--- |
| 🎯 投票預測遊戲 | 自動 Poll | 頻道推播時自動發送 Telegram Poll 讓用戶預測勝負 |
| 🏆 積分排行榜 | `/rank` | Top 10 積分排行（含勝率統計，靈感來自 playsport.cc） |
| 📊 個人積分 | `/myscore` | 個人積分、預測場次、勝率、稱號（新手/進階/資深/大師） |
| 👤 個人喜好總覽 | `/myfav` | 最愛球隊、運動類型、語言偏好、互動習慣（SQLite 持久化） |
| 🎨 互動習慣設定 | `/style` | 切換詳細分析 / 快速比分 / 自動判斷模式 |
| 📡 即時社群洞察 | `/insights` | 熱門關注指數、群體預測準確率、爆冷事件 |
| 📅 每週趨勢報告 | 自動排程 | 每週一自動發布「本週玩家趨勢報告」到頻道 |
| 🤖 主動推薦 | 自動觸發 | 有相關賽事時，Bot 主動推薦給有查詢記錄的用戶 |

**新增模組：**

| 模組 | 說明 |
| :--- | :--- |
| `modules/user_preferences.py` | 用戶喜好記憶學習（SQLite），記錄查詢歷史、語言、互動習慣 |
| `modules/prediction_game.py` | 投票預測遊戲（Telegram Poll + 積分系統 + 爆冷加成） |
| `modules/community_analytics.py` | 群體行為學習分析（熱門度/群體預測/爆冷/內容優化/週報） |

**積分規則：**

| 結果 | 積分 |
| :--- | :--- |
| 猜對 | +10 分 |
| 猜錯（參與獎） | +2 分 |
| 爆冷猜對加成 | +5 分 |

**稱號系統（靈感來自 playsport.cc 會員等級）：**

| 稱號 | 條件 |
| :--- | :--- |
| 🔥 預測大師 | 勝率 ≥ 70% |
| ⭐ 資深預測員 | 勝率 ≥ 55% |
| 📈 進階預測員 | 勝率 ≥ 40% |
| 🌱 新手預測員 | 勝率 < 40% |

---

### V17（2026/03/08）— 三種運動 AI 分析整合版

本次更新靈感來源：[playsport.cc](https://www.playsport.cc) 的勝率統計、焦點比賽呈現與爆冷指數功能。

**新增功能：**

| 功能 | 說明 |
| :--- | :--- |
| `/football` | ⚽ 今日足球 AI 分析（焦點比賽 / 勝率預測 / 爆冷可能） |
| `/baseball` | ⚾ 今日棒球 AI 分析（焦點比賽 / 勝率預測 / 爆冷可能） |
| `/basketball` | 🏀 今日籃球 AI 分析（焦點比賽 / 勝率預測 / 爆冷可能） |
| `/allanalyze` | 🔥 三種運動綜合 AI 分析（一次查看足球 + 棒球 + 籃球） |
| `/winrate 運動` | 📊 勝率統計面板（各聯盟近期勝率，靈感來自 playsport.cc） |
| `modules/sports_analyzer.py` | 三種運動統一 AI 分析模組（gpt-4.1-mini） |
| `modules/nba.py` | NBA 籃球賽事模組（ESPN API） |
| `bot.py task_sports_ai` | 每日自動推播三種運動 AI 分析 |

**修復問題：**

| 問題 | 修復方式 |
| :--- | :--- |
| PII 個資偵測誤判 | 連續數字 pattern 改為 12-20 位獨立數字（排除短數字如球衣號碼） |
| 多語言邏輯缺陷 | 語言設定同步儲存 SQLite，`_get_user_lang()` 優先從資料庫讀取 |
| 錯誤處理過寬鬆 | dispatch_message 分類處理 API 錯誤與網路錯誤，避免掩蓋問題 |
| 意圖判斷非法 action | should_use_bot_function 加入 valid_actions 驗證 |
| 引導語重複附加 | 縮小觸發範圍，只在明確帳號/金流問題時才附加 |
| user_lang 傳遞不一致 | 統一使用 `_get_user_lang()` 函數取得語言設定 |

---

## 系統架構

本系統由多個核心模組組成，分別負責數據獲取、AI 分析、訊息格式化、Telegram 發送、隊名搜尋與即時比分查詢。

| 模組名稱 | 檔案 | 功能說明 |
| :--- | :--- | :--- |
| **數據抓取** | `espn_api.py` | 串接 ESPN 公開 API，獲取各大聯賽即時比分、賽程與戰績 |
| **AI 分析** | `ai_analyzer.py` | 整合 OpenAI API，根據賽事數據自動生成賽前預覽、深度分析與賽後復盤 |
| **三種運動分析** | `modules/sports_analyzer.py` | ⚽⚾🏀 足球/棒球/籃球統一 AI 分析模組（gpt-4.1-mini） |
| **格式化** | `formatter.py` | 將原始數據與 AI 分析結果轉換為適合 Telegram 閱讀的排版格式 |
| **發送** | `telegram_sender.py` | 負責與 Telegram Bot API 溝通，處理長訊息分段發送與訊息置頂 |
| **隊名搜尋** | `team_search.py` | 中英文隊名對照表與模糊搜尋引擎，支援超過 150 支隊伍的中文查詢 |
| **即時查詢** | `live_query.py` | 跨所有體育項目搜尋即時比分，並格式化為詳細的比分報告 |
| **AI 客服** | `modules/ai_chat.py` | 多語言 AI 客服，支援繁中/英/高棉/越南/泰文 |
| **足球賽事** | `modules/football.py` | ESPN API 足球賽事（英超/西甲/德甲/意甲/法甲/歐冠） |
| **棒球賽事** | `modules/mlb.py` | ESPN API MLB 棒球賽事 |
| **籃球賽事** | `modules/nba.py` | ESPN API NBA 籃球賽事（V17 新增） |
| **用戶喜好** | `modules/user_preferences.py` | SQLite 用戶喜好記憶學習（V18 新增） |
| **預測遊戲** | `modules/prediction_game.py` | Telegram Poll 投票預測遊戲 + 積分系統（V18 新增） |
| **群體分析** | `modules/community_analytics.py` | 群體行為學習分析（熱門度/群體預測/爆冷/週報）（V18 新增） |

---

## 互動式即時比分查詢

頻道會員可以直接**私訊 @LA1111_bot** 查詢即時比分。機器人會自動搜尋所有體育項目（足球、棒球、籃球、冰球、美式足球），找到匹配的比賽並回覆詳細的比分資訊。

### 查詢方式

使用者只需直接輸入隊名，機器人就會自動識別並回覆。支援以下幾種輸入方式：

| 輸入方式 | 範例 |
| :--- | :--- |
| **中文隊名** | `中華台北 日本`、`利物浦 曼城`、`洋基 紅襪` |
| **英文隊名** | `Lakers Celtics`、`Arsenal`、`Inter Milan` |
| **帶查詢詞** | `我想知道 中華台北 日本`、`比分 利物浦` |
| **指令查詢** | `/score 中華台北 日本` |
| **AI 分析** | `今日足球分析`、`NBA分析`、`棒球今天怎麼樣` |

### Bot 指令完整列表

| 指令 | 說明 |
| :--- | :--- |
| `/start` | 顯示歡迎訊息與使用說明 |
| `/help` | 查看完整使用說明 |
| `/score 隊名` | 查詢指定隊伍的即時比分 |
| `/today` | 查看今日所有賽事總覽 |
| `/live` | 查看目前進行中的比賽 |
| `/hot` | 查看今日熱門焦點賽事 |
| `/leaders` | 排行榜（全壘打/得分/射手） |
| `/analyze 隊名` | AI 賽事分析 + 勝率預測 |
| `/football` | ⚽ 今日足球 AI 分析 |
| `/baseball` | ⚾ 今日棒球 AI 分析 |
| `/basketball` | 🏀 今日籃球 AI 分析 |
| `/allanalyze` | 🔥 三種運動綜合 AI 分析 |
| `/winrate 運動` | 📊 勝率統計面板（足球/棒球/籃球） |
| `/odds 隊名` | 盤口資訊 |
| `/rank` | 🏆 預測積分排行榜 Top 10（V18 新增） |
| `/myscore` | 📊 個人預測積分與稱號（V18 新增） |
| `/myfav` | 👤 個人喜好總覽（V18 新增） |
| `/style` | 🎨 切換互動習慣（V18 新增） |
| `/insights` | 📡 即時社群趨勢洞察（V18 新增） |

### AI 分析格式（三種運動統一）

每種運動的 AI 分析均採用相同格式，靈感來自 playsport.cc 的賽事分析呈現方式：

```
⚽/⚾/🏀 【今日焦點比賽】
挑出 1~3 場最值得關注的比賽，說明為何值得關注

📊 【勝率預測】
主隊 XX% vs 客隊 XX%（附理由）

❄️ 【爆冷可能】
爆冷指數：低（<20%）/ 中（20-40%）/ 高（>40%）
```

### 支援的隊伍

系統內建超過 **150 支隊伍**的中英文對照，涵蓋：

- **國家隊**：中華台北、日本、韓國、中國、澳洲、巴西、阿根廷、德國、法國、英格蘭、西班牙、義大利等
- **英超**：利物浦、曼城、曼聯、阿森納、切爾西、熱刺等
- **西甲**：巴塞隆納、皇馬、馬競等
- **德甲**：拜仁、多特蒙德、勒沃庫森等
- **意甲**：國際米蘭、AC米蘭、尤文圖斯等
- **法甲**：巴黎聖日耳曼、馬賽、里昂等
- **MLB**：洋基、紅襪、道奇、太空人等
- **NBA**：湖人、勇士、塞爾提克、尼克等
- **NHL**：企鵝、楓葉等

---

## 自動發文排程

系統已設定六個每日/每週定時任務，確保頻道內容豐富且即時：

| 時間（台灣時間） | 任務 | 內容 |
| :--- | :--- | :--- |
| **10:00** | 今日賽程預覽 | 當日所有重要賽事的完整賽程表（自動置頂），附 AI 賽事亮點預覽 |
| **10:05** | 三種運動 AI 分析 | ⚽⚾🏀 足球/棒球/籃球三種運動 AI 深度分析（焦點比賽/勝率/爆冷） |
| **14:00** | 深度分析 | 挑選 3-5 場焦點戰役，提供數據對比與戰術觀察的深度分析 |
| **18:00** | 傍晚焦點戰 | 更新即時比分，針對即將開打的比賽提供即時分析 |
| **23:00** | 賽後復盤 | 當日最終戰報，AI 總結今日最大看點與意外結果 |
| **每週一 09:00** | 週報 | 本週玩家趨勢報告（熱門關注/群體預測準確率/爆冷事件） |

---

## 手動操作

### 執行定時任務

```bash
cd /home/ubuntu/sports_bot
python3 bot.py morning      # 今日賽程預覽 + 三種運動 AI 分析
python3 bot.py afternoon    # 深度分析
python3 bot.py evening      # 傍晚焦點戰
python3 bot.py night        # 賽後復盤
python3 bot.py sports_ai    # 單獨執行三種運動 AI 分析
python3 bot.py standings    # 週報排名
python3 bot.py weekly       # 手動觸發週報
```

### 管理互動式 Bot

```bash
# 啟動 Bot
bash /home/ubuntu/sports_bot/start_bot.sh

# 重啟 Bot
bash /home/ubuntu/sports_bot/restart_bot.sh

# 查看 Bot 日誌
tail -f /home/ubuntu/sports_bot/bot_interactive.log

# 檢查 Bot 是否運行中
ps aux | grep interactive_bot
```

---

## SQLite 資料庫結構

所有用戶數據共用 `data/user_preferences.db`（自動建立）：

| 資料表 | 用途 |
| :--- | :--- |
| `user_settings` | 用戶語言/互動習慣設定 |
| `query_history` | 查詢歷史（學習喜好用） |
| `favorite_teams` | 最愛球隊統計 |
| `favorite_sports` | 最愛運動類型統計 |
| `recommendation_log` | 推薦記錄（防重複） |
| `prediction_polls` | Poll 記錄（賽事/選項/狀態） |
| `prediction_votes` | 用戶投票記錄 |
| `user_scores` | 用戶積分總表 |
| `community_query_stats` | 全體查詢熱門度統計 |
| `community_prediction_stats` | 群體預測準確率 |
| `upset_events` | 爆冷事件記錄 |
| `content_style_metrics` | 互動風格效果追蹤 |
| `weekly_insights_log` | 週報記錄 |

---

## 設定檔

所有系統配置統一管理於 `config.py`，包括 Bot Token、頻道 ID、支援的聯賽列表與時區設定。若需新增聯賽或修改設定，只需編輯該檔案即可。

## 環境變數

| 變數名稱 | 說明 |
| :--- | :--- |
| `BOT_TOKEN` | Telegram Bot Token |
| `CHANNEL_ID` | Telegram 頻道 ID |
| `OPENAI_API_KEY` | OpenAI API 金鑰（用於 AI 分析，模型：gpt-4.1-mini） |
| `TIMEZONE` | 時區設定（預設：Asia/Taipei） |

---

## 靈感來源

本 Bot 大量參考 [playsport.cc](https://www.playsport.cc) 的功能設計：

| playsport.cc 功能 | Bot 對應功能 |
| :--- | :--- |
| 會員戰績總覽 | `/myfav` 個人喜好總覽 |
| 勝率統計面板 | `/winrate` 各聯盟勝率統計 |
| 預測記錄追蹤 | 投票預測遊戲 + `/myscore` |
| 會員等級系統 | 預測稱號（新手/進階/資深/大師） |
| 賽事分析呈現 | 三種運動 AI 分析統一格式 |
| 焦點比賽 | 今日焦點比賽 AI 挑選 |
| 爆冷指數 | 爆冷可能分析 + 爆冷事件記錄 |
| 群體數據 | 群體行為學習分析系統 |

*📡 世界體育數據室 — Powered by LA1 × GPT-4.1-mini*
