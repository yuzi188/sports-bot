# 體育分析 Bot - Railway 部署指南

這份指南將協助您將體育分析 Bot 部署到 Railway 平台上。此版本已經過修改，支援透過環境變數讀取敏感資訊，並使用多執行緒同時運行排程器與互動式 Bot。

## 1. 準備工作

在開始部署之前，請確保您已經準備好以下資訊：

| 環境變數名稱 | 說明 | 範例 |
| --- | --- | --- |
| `BOT_TOKEN` | Telegram Bot 的 Token（從 @BotFather 取得） | `8796143383:AAFMOZcc5yJO0GjRpPuDH40F1HTn0x7RCus` |
| `CHANNEL_ID` | 要發送訊息的 Telegram 頻道 ID 或使用者名稱 | `@LA11118` |
| `OPENAI_API_KEY` | OpenAI API 金鑰（用於 AI 分析功能） | `sk-proj-...` |

## 2. 部署步驟（手機與電腦皆可操作）

### 步驟一：建立 GitHub 儲存庫
1. 登入您的 GitHub 帳號。
2. 建立一個新的私有（Private）儲存庫。
3. 將 `sports_bot_railway.zip` 解壓縮後的所有檔案上傳到該儲存庫中。

### 步驟二：在 Railway 上建立專案
1. 前往 [Railway 官網](https://railway.app/) 並登入（建議使用 GitHub 帳號登入）。
2. 點擊右上角的 **"New Project"**（新增專案）。
3. 選擇 **"Deploy from GitHub repo"**（從 GitHub 部署）。
4. 選擇您剛剛建立的體育分析 Bot 儲存庫。
5. 點擊 **"Deploy Now"**（立即部署）。

### 步驟三：設定環境變數
1. 在 Railway 專案儀表板中，點擊剛剛建立的服務（Service）。
2. 切換到 **"Variables"**（變數）分頁。
3. 點擊 **"New Variable"**（新增變數），依序加入以下三個變數：
   - `BOT_TOKEN` = 您的 Telegram Bot Token
   - `CHANNEL_ID` = 您的頻道 ID（例如 `@LA11118`）
   - `OPENAI_API_KEY` = 您的 OpenAI API 金鑰
4. 設定完成後，Railway 會自動重新部署您的應用程式。

## 3. 驗證部署

部署完成後，您可以透過以下方式確認 Bot 是否正常運作：

1. **檢查日誌**：在 Railway 儀表板中，切換到 **"Deployments"** 分頁，點擊最新的部署紀錄，然後查看 **"View Logs"**。您應該會看到類似以下的訊息：
   ```
   🤖 世界體育數據室 Bot 啟動中...
   ✅ Bot 連接成功
   啟動排程器...
   啟動互動式 Bot...
   ```
2. **測試互動功能**：在 Telegram 中傳送訊息給您的 Bot（例如輸入 `/start` 或查詢球隊名稱），確認 Bot 是否會回覆。
3. **測試排程功能**：Bot 會依照設定的時間（10:00, 14:00, 18:00, 23:00）自動發送訊息到指定的頻道。

## 4. 常見問題與故障排除

- **Bot 沒有回應**：請檢查 `BOT_TOKEN` 是否正確，並確認 Bot 已經加入到指定的頻道中，且具有發送訊息的權限。
- **AI 分析功能失效**：請檢查 `OPENAI_API_KEY` 是否正確，以及您的 OpenAI 帳號是否有足夠的額度。
- **時區問題**：程式碼中已預設使用 `Asia/Taipei` 時區，排程時間將以台灣時間為準。

---
*文件由 Manus AI 產生*
