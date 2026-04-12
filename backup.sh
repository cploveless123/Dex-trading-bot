#!/bin/bash
# Hourly backup for both Dex-trading-bot and workspace
# Runs every 30 minutes

LOG_FILE="/root/Dex-trading-bot/backup.log"
DATE=$(date "+%Y-%m-%d %H:%M UTC")

echo "[$DATE] Backup started" >> $LOG_FILE

# Backup Dex-trading-bot
cd /root/Dex-trading-bot
git add -A >> $LOG_FILE 2>&1
git commit -m "Auto backup $(date)" >> $LOG_FILE 2>&1
GIT_STATUS=$(git push origin master 2>&1)
echo "[$DATE] Dex: $GIT_STATUS" >> $LOG_FILE

# Backup workspace
cd /root/.openclaw/workspace
git add -A >> $LOG_FILE 2>&1  
git commit -m "Auto backup $(date)" >> $LOG_FILE 2>&1
WS_STATUS=$(git push origin master 2>&1)
echo "[$DATE] Workspace: $WS_STATUS" >> $LOG_FILE

echo "[$DATE] Backup complete" >> $LOG_FILE