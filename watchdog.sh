#!/bin/bash
# Watchdog - restarts trading systems if any are down

LOG="/root/Dex-trading-bot/watchdog.log"
PYTHON="/root/Dex-trading-bot/venv/bin/python"
SCANNER_DIR="/root/Dex-trading-bot"

cd $SCANNER_DIR

# Check if systems are running
WHALE=$(ps aux | grep -c "whale_momentum_scanner.py" | grep -v grep)
MONITOR=$(ps aux | grep -c "position_monitor.py" | grep -v grep)
ALERT=$(ps aux | grep -c "alert_sender.py" | grep -v grep)
AUTO=$(ps aux | grep -c "auto_scanner.py" | grep -v grep)

RESTART=0

if [ "$WHALE" -lt 1 ]; then
    echo "[$(date)] whale_momentum_scanner DOWN - restarting" >> $LOG
    nohup $PYTHON -u whale_momentum_scanner.py > whale_momentum.log 2>&1 &
    RESTART=1
fi

if [ "$MONITOR" -lt 1 ]; then
    echo "[$(date)] position_monitor DOWN - restarting" >> $LOG
    nohup $PYTHON -u position_monitor.py > position_monitor.log 2>&1 &
    RESTART=1
fi

if [ "$ALERT" -lt 1 ]; then
    echo "[$(date)] alert_sender DOWN - restarting" >> $LOG
    nohup $PYTHON -u alert_sender.py > alert_sender.log 2>&1 &
    RESTART=1
fi

if [ "$AUTO" -lt 1 ]; then
    echo "[$(date)] auto_scanner DOWN - restarting" >> $LOG
    nohup $PYTHON -u auto_scanner.py > auto_scanner.log 2>&1 &
    RESTART=1
fi

if [ "$RESTART" -eq 1 ]; then
    sleep 5
    echo "[$(date)] Systems restarted - whale:$(ps aux | grep -c 'whale_momentum_scanner' | grep -v grep) monitor:$(ps aux | grep -c 'position_monitor' | grep -v grep) alert:$(ps aux | grep -c 'alert_sender' | grep -v grep) auto:$(ps aux | grep -c 'auto_scanner' | grep -v grep)" >> $LOG
fi
