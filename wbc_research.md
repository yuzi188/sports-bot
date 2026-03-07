# WBC API 研究結果

## 端點
- WBC scoreboard: `baseball/world-baseball-classic/scoreboard`
- 支援日期查詢: `?dates=20260305` (單日)
- 今日有 8 場 WBC 賽事

## 隊伍資訊
- WBC 隊伍用 records 欄位記錄戰績 (如 "1-2")
- 隊伍 ID: Chinese Taipei=6, Korea=8, Japan=?, USA=?

## 歷史比賽
- 可用日期範圍查詢歷史比賽
- 需要遍歷近幾天的 scoreboard 來找特定隊伍的歷史比賽
- 或者直接從 scoreboard 的 records 欄位取得戰績

## 近3場策略
- 方法1: 遍歷近7天的 scoreboard，找到特定隊伍的比賽
- 方法2: 從當前 scoreboard 中提取 records 欄位
- 方法1 更好，因為可以顯示具體的比分和對手
