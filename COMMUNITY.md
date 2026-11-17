# LA1 社群助手

新 Bot：@LA1Community_bot。目標頻道：@LA11118。
獨立入口 `community_bot.py`，不啟用 main.py、娛樂城客服、539 彩票與舊廣告排程。
沿用原有 ESPN get_scoreboard 及訊息長度／頻率檢查。

## 部署

使用獨立 Railway 服務，Dockerfile 路徑 `Dockerfile.community`。
不要修改或重新啟動原 la1-bot 服務。
必須覆寫舊 railway.json 的啟動命令為 `python community_bot.py`，或將服務來源設為不使用舊設定檔的獨立部署分支。

環境變數：BOT_TOKEN、OPENAI_API_KEY、ADMIN_IDS（管理員 Telegram 數字 ID，逗號分隔）、COMMUNITY_GROUP_ID（指定討論群數字 ID）、COMMUNITY_CHANNEL=@LA11118、OPENAI_MODEL=gpt-4.1-mini。
正式環境掛載持久磁碟 /data，設定 COMMUNITY_DB=/data/community.db。
密鑰只存 Railway 私密環境變數，不進 Git。
單一服務、單一副本，以 polling 接收訊息，不開公開 HTTP 入口。
啟動會檢查機器人帳號；若有既存 webhook 就拒絕啟動，避免覆蓋其他服務。

## 操作

- /start、/help：說明。
- /today、/live：ESPN 賽程／比分，UTC+8；來源失敗會顯示，不冒充無賽事。
- /ask 問題：GPT 依賽事資料回覆。
- 一般群組對話只回應 @機器人或回覆機器人的訊息；不讀取其他群組作答。
- 管理員限私訊：/draft 主題 → 預覽 → /publish 編號。
- /poll 問題 | 選項一 | 選項二：管理員發布匿名投票。
- /autopost on：每天 10:00 籃球一篇、22:00 足球一篇（UTC+8），附 LA1 賽事封面。off 暫停。
- /daily basketball 或 /daily soccer：管理員私訊預覽圖片與文章，不公開發布。
- /status：機器人頻道身分與排程狀態。GPT 仍須實際 /ask 驗證。

發布前保留狀態，逾時不自動重送；需人工查看頻道判斷結果。
SQLite 儲存貼文與開關，不儲存一般聊天內容。尚未加入刪文／禁言權限。
第一次上線後須驗證 /start、/today、/ask、未授權 /publish、頻道試貼及重啟防重複。

## 目前進度

2026-11-17：已部署 Railway 獨立 la1-community-bot，來源 community-assistant 分支。
已實測 /start、/ask GPT 回覆、/today ESPN 賽事；管理員私訊身份已確認。
使用者已確認密鑰儲存與部署；OpenAI 使用 Railway 的 la1-platform.OPENAI_API_KEY 服務引用。
已授予 @LA11118 僅發布訊息權限，已加入 -1002827345434 討論群並成功回覆歡迎訊息。
使用者授權每天籃球、足球各一篇，已透過管理員指令開啟排程。
已實測頻道介紹文發布、/focus、足球 /pick 建立預覽及 /review 待完場紀錄。
每日文章的隊名、比分及台港時間直接由資料排版；GPT 只產生一般觀賽提問，避免誤譯隊名或捏造賽況。
圖片為自製 LA1 字標與賽程圖卡；籃球橘色、足球綠色。圖片與全文分兩則連續訊息發布。
模擬注單與復盤目前為獨立指令，沒有自動加入每日文章；實際完場自動核對仍待賽事結束驗證。

## 編輯與模擬紀錄

- /focus：未來 48 小時支援聯賽候選，按時間排序，沒有投注量資料，不能稱熱度榜。
- /pick 賽事編號：管理員產生 GPT 賽前觀點與模擬單場注單；資料不足允許觀望。
- 一場只保留一份預測、原始資料與建立時間；發布前再次確認尚未開賽。
- /review：按 ESPN 完場結果核對全部預測（包含未發布預覽），最近 15 場明細與完整累計。
- 足球只結算一般 Full Time，延長／點球不當成 90 分鐘結果。其他未確認賽果保留待核對。
- 只有虛擬單位，沒有平台下注操作；未接入可靠賠率，不計算損益、不生成真實投注憑證。
- GPT 觀點沒有已驗證的預測優勢，不生成精準勝率、保證收益或虛構歷史戰績。

## 內容參考（2026-11-17 公開頻道觀察）

- https://t.me/s/mimi2888 ：短篇賽事方向與結果標記；LA1 採短摘要，但原預測不可覆寫。
- https://t.me/s/pierrecashon8 ：賽前、比賽進程與賽後連續討論；LA1 採事件節奏與社群問句。
- https://t.me/s/boyboyboytips ：反應互動、時間／場次／方向資訊；LA1 採清楚欄位與投票。
- 不複製他人圖片、長文、注單或戰績。頻道內容作選題線索，比分及事實另向賽事來源核對。
- 經營順序：賽程候選 → 原創賽前預覽 → 確認發布 → 留言討論 → 完整模擬復盤。
