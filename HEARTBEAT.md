# Heartbeat Checklist - Run every 15 minutes

## Check Systems
1. Are monitors running? `ps aux | grep -E "combined|gmgn|sim_trader" | grep -v grep`
2. Check for new signals: `ls -lt /root/.openclaw/workspace/trading-bot/signals/ | head -5`
3. Check trade results: `tail -3 /root/.openclaw/workspace/trading-bot/trades/sim_trades.jsonl`

## If new signals/trades found
Send Telegram update to Chris with:
- New signals in GMGN format
- New trade results with DexScreener links
- Current balance and P&L
- What I'm learning

## If systems down
Restart them:
```
cd /root/.openclaw/workspace/trading-bot
/root/.openclaw/workspace/venv/bin/python scripts/combined_monitor.py &
/root/.openclaw/workspace/venv/bin/python scripts/gmgn_poll_monitor.py &
/root/.openclaw/workspace/venv/bin/python scripts/sim_trader.py &
```

## Git push (hourly)
Every hour, push to GitHub to backup:
```
git -C /root/.openclaw/workspace add -A
git -C /root/.openclaw/workspace commit -m "Update $(date)"
git -C /root/.openclaw/workspace push origin master
```
