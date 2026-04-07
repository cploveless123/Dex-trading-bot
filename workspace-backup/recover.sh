#!/bin/bash
# Recovery Script - If Wilson crashes, run this to restore workspace
# From: https://github.com/cploveless123/Dex-trading-bot/blob/master/workspace-backup/

BACKUP_DIR="/root/Dex-trading-bot/workspace-backup"
WORKSPACE="/root/.openclaw/workspace"

echo "🔄 Wilson Recovery Starting..."

# Backup current workspace first (in case)
cp $WORKSPACE/MEMORY.md $WORKSPACE/MEMORY.md.bak 2>/dev/null

# Restore essential files
for f in MEMORY.md USER.md IDENTITY.md SOUL.md HEARTBEAT.md AGENTS.md TOOLS.md WHALE_LEARNINGS.md; do
    if [ -f "$BACKUP_DIR/$f" ]; then
        cp "$BACKUP_DIR/$f" "$WORKSPACE/$f"
        echo "✅ Restored: $f"
    fi
done

echo ""
echo "🎉 Recovery complete! Wilson should have:"
echo "   - Memory of past trades and strategy"
echo "   - Who Chris is and his preferences"
echo "   - Trading rules and exit plan"
echo "   - Alert formats and report style"
echo ""
echo "Restart Wilson and verify with !status"
