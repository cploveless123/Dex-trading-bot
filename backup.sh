#!/bin/bash
set -e

cd /root/Dex-trading-bot

# Run health check first
echo "[$(date)] Running health check..."
python3 health_check.py > /tmp/health_check.log 2>&1
HC_RESULT=$?

if [ $HC_RESULT -ne 0 ]; then
    echo "[$(date)] Health check found issues"
fi

# Commit bot repo
git add -A
git commit -m "Auto-backup $(date -u '+%Y-%m-%d %H:%M UTC')" || true
git push origin master 2>/dev/null || echo "Git push failed"

# Workspace backup
cd /root/.openclaw/workspace
git add -A
git commit -m "Auto-backup $(date -u '+%Y-%m-%d %H:%M UTC')" 2>/dev/null || true
git push origin master 2>/dev/null || echo "Workspace push failed"

# Copy workspace files to bot workspace-backup dir
mkdir -p /root/Dex-trading-bot/workspace-backup/memory
cp /root/.openclaw/workspace/memory/2026-04-08.md /root/Dex-trading-bot/workspace-backup/memory/ 2>/dev/null || true
cp /root/.openclaw/workspace/MEMORY.md /root/Dex-trading-bot/workspace-backup/ 2>/dev/null || true
cp -r /root/.openclaw/.agents/skills/gmgn-* /root/Dex-trading-bot/workspace-backup/skills/ 2>/dev/null || true

# Commit workspace backup
cd /root/Dex-trading-bot
git add workspace-backup/
git commit -m "Workspace backup $(date -u '+%Y-%m-%d %H:%M UTC')" 2>/dev/null || true
git push origin master 2>/dev/null || true

echo "[$(date)] Backup complete"
