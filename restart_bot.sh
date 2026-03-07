#!/bin/bash
# 重啟互動式查詢 Bot
cd /home/ubuntu/sports_bot
PID=$(pgrep -f "interactive_bot.py")
if [ -n "$PID" ]; then
    kill $PID
    echo "已停止舊 Bot (PID: $PID)"
    sleep 2
fi
nohup python3 interactive_bot.py >> /home/ubuntu/sports_bot/bot_interactive.log 2>&1 &
echo "Bot 已重啟 (PID: $!)"
