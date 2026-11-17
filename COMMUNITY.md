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
- /autopost on：明確開啟每天 10:00、22:00 賽程賽果摘要。預設關閉；off 暫停。
- /status：機器人頻道身分與排程狀態。GPT 仍須實際 /ask 驗證。

發布前保留狀態，逾時不自動重送；需人工查看頻道判斷結果。
SQLite 儲存貼文與開關，不儲存一般聊天內容。尚未加入刪文／禁言權限。
第一次上線後須驗證 /start、/today、/ask、未授權 /publish、頻道試貼及重啟防重複。

## 目前進度

2026-11-17：機器人帳號及介紹已建立；獨立程式與 3 項測試通過。
ESPN 真實資料連線另行查驗。GPT 與 Telegram 真實呼叫、部署、群組權限尚待完成。
使用者已要求沿用同一組 API；已找到網站本機設定中存在 OpenAI Key，未輸出值。
將新 Token 與既有 OpenAI Key 存入 Railway 的確認仍待回覆。未上線、未公開發文。
