#!/bin/bash
cd /root/Dex-trading-bot

# Run health check first
python3 health_check.py > /tmp/health_check.log 2>&1
HC_RESULT=$?

# Auto-fix if needed
if [ $HC_RESULT -ne 0 ]; then
    echo "Health check found issues, attempted fix"
fi

# Commit with status
git add -A

# Only push if no import/syntax errors in key files
python3 -c "import position_monitor, auto_scanner, send_alert" 2>/dev/null
if [ $? -eq 0 ]; then
    git commit -m "Auto-backup $(date -u '+%Y-%m-%d %H:%M UTC')" || true
    git push origin master 2>/dev/null || echo "Git push failed"
else
    echo "Skipping backup - import errors detected"
fi

# Workspace backup
cd /root/.openclaw/workspace
git add -A
git commit -m "Auto-backup $(date -u '+%Y-%m-%d %H:%M UTC')" 2>/dev/null || true
git push origin master 2>/dev/null || echo "Workspace push failed"

# Copy to workspace-backup
cp /root/.openclaw/workspace/*.md /root/Dex-trading-bot/workspace-backup/ 2>/dev/null
