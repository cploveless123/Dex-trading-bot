#!/bin/bash
cd /root/Dex-trading-bot
git add -A
git commit -m "Auto-backup $(date -u '+%Y-%m-%d %H:%M UTC')"
git push origin master
cd /root/.openclaw/workspace
git add -A
git commit -m "Auto-backup $(date -u '+%Y-%m-%d %H:%M UTC')"
git push origin master
cp /root/.openclaw/workspace/*.md /root/Dex-trading-bot/workspace-backup/ 2>/dev/null
cp /root/.openclaw/workspace/memory/*.md /root/Dex-trading-bot/workspace-backup/memory/ 2>/dev/null
echo "DONE"
