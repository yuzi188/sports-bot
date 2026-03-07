#!/bin/bash
# 啟動互動式查詢 Bot
cd /home/ubuntu/sports_bot

# 檢查是否已在運行
if pgrep -f "interactive_bot.py" > /dev/null; then
    echo "Bot 已在運行中"
    exit 0
fi

# 啟動 Bot
nohup python3 interactive_bot.py >> /home/ubuntu/sports_bot/bot_interactive.log 2>&1 &
echo "Bot 已啟動 (PID: $!)"
