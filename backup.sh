#!/bin/bash
# Wilson backup script - Everything that makes Wilson, Wilson
# Runs every 30 minutes

LOG_FILE="/root/Dex-trading-bot/wilson_backup.log"
DATE=$(date "+%Y-%m-%d %H:%M UTC")

echo "[$DATE] Wilson backup started" >> $LOG_FILE

# ======================
# DEX TRADING BOT
# ======================
cd /root/Dex-trading-bot
git add -A >> $LOG_FILE 2>&1
git commit -m "Auto backup $(date)" >> $LOG_FILE 2>&1
GIT_STATUS=$(git push origin master 2>&1)
if [[ "$GIT_STATUS" == *"Everything up-to-date"* ]] || [[ "$GIT_STATUS" == *"to"* ]]; then
    echo "[$DATE] Dex: OK" >> $LOG_FILE
else
    echo "[$DATE] Dex: $GIT_STATUS" >> $LOG_FILE
fi

# ======================
# WORKSPACE - WILSON IDENTITY
# ======================
cd /root/.openclaw/workspace

# Core identity files
CORE_FILES="AGENTS.md SOUL.md USER.md TOOLS.md MEMORY.md HEARTBEAT.md IDENTITY.md RECOVERY_INSTRUCTIONS.md BOOTSTRAP.md"

# Memory files
MEMORY_FILES=$(ls memory/*.md 2>/dev/null | tr '\n' ' ')

# Skills
SKILL_FILES=$(ls skills/*.md skills/*.py 2>/dev/null | tr '\n' ' ')

# Add and commit
git add $CORE_FILES $MEMORY_FILES $SKILL_FILES workspace-backup.json 2>> $LOG_FILE
git commit -m "Wilson auto backup $(date)" >> $LOG_FILE 2>&1
WS_STATUS=$(git push origin master 2>&1)
if [[ "$WS_STATUS" == *"Everything up-to-date"* ]] || [[ "$WS_STATUS" == *"to"* ]]; then
    echo "[$DATE] Workspace: OK" >> $LOG_FILE
else
    echo "[$DATE] Workspace: $WS_STATUS" >> $LOG_FILE
fi

# ======================
# OPENCLAW SYSTEM SKILLS  
# ======================
cd /opt/node22/lib/node_modules/openclaw/skills
git add -A >> $LOG_FILE 2>&1
git commit -m "Skills backup $(date)" >> $LOG_FILE 2>&1
git push origin master >> $LOG_FILE 2>&1

# ======================
# CRON JOBS
# ======================
cd /root/.openclaw/cron
if [ -f jobs.json ]; then
    git add -A >> $LOG_FILE 2>&1
    git commit -m "Cron backup $(date)" >> $LOG_FILE 2>&1
    git push origin master >> $LOG_FILE 2>&1
    echo "[$DATE] Cron: OK" >> $LOG_FILE
fi

echo "[$DATE] Wilson backup complete" >> $LOG_FILE
echo "---" >> $LOG_FILE