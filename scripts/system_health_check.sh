#!/bin/bash
# System health check - verify all trading bots running
cd /root/Dex-trading-bot

echo "=== SYSTEM HEALTH CHECK $(date '+%Y-%m-%d %H:%M UTC') ==="

# Check processes
AUTO=$(ps aux | grep -c "auto_scanner.py" | grep -v grep)
GMGN=$(ps aux | grep -c "gmgn_buyer.py" | grep -v grep)
MON=$(ps aux | grep -c "position_monitor.py" | grep -v grep)
ALERT=$(ps aux | grep -c "alert_sender.py" | grep -v grep)

echo "Auto Scanner: $AUTO"
echo "GMGN Buyer: $GMGN"
echo "Position Monitor: $MON"
echo "Alert Sender: $ALERT"

TOTAL=$((AUTO + GMGN + MON + ALERT))
echo "Total running: $TOTAL/4"

if [ $TOTAL -lt 4 ]; then
    echo "⚠️ WARNING: Some systems down! Restarting..."
    kill $(ps aux | grep -E "auto_scanner|gmgn_buyer|position_monitor|alert_sender" | grep -v grep | awk '{print $2}') 2>/dev/null
    sleep 2
    nohup python3 -u auto_scanner.py > auto_scanner.log 2>&1 &
    nohup python3 -u gmgn_buyer.py > gmgn_buyer.log 2>&1 &
    sleep 2
    nohup python3 -u position_monitor.py > position_monitor.log 2>&1 &
    sleep 1
    nohup python3 -u alert_sender.py > alert_sender.log 2>&1 &
    sleep 3
    echo "Restarted. New count: $(ps aux | grep -E 'auto_scanner|gmgn_buyer|position_monitor|alert_sender' | grep -v grep | wc -l)"
else
    echo "✅ All 4 systems running"
fi

# Quick balance check
python3 -c "
import json
from trading_constants import SIM_RESET_TIMESTAMP as RESET, CHRIS_STARTING_BALANCE as BAL
with open('trades/sim_trades.jsonl') as f:
    lines = f.readlines()
rt = [json.loads(l) for l in lines if json.loads(l).get('opened_at','') > RESET]
has_pnl = [t for t in rt if t.get('pnl_sol') is not None]
wins = [t for t in has_pnl if t.get('pnl_sol',0) > 0]
losses = [t for t in has_pnl if t.get('pnl_sol',0) < 0]
total_pnl = sum(t.get('pnl_sol',0) for t in has_pnl)
bal = BAL + total_pnl
open_pos = [t for t in rt if not t.get('closed_at')]
wr = len(wins)/(len(wins)+len(losses))*100 if wins+losses else 0
print(f'Balance: {round(bal,4)} SOL | Record: {len(wins)}W/{len(losses)}L ({round(wr)}% WR) | Open: {len(open_pos)}')
"

echo "=== END ==="
