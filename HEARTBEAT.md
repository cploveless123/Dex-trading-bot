# Heartbeat Checklist - Run every 15 minutes

## Check Systems
1. `ps aux | grep -E "combined|gmgn|sim_trader" | grep -v grep`
2. Check signals: `ls -lt signals/ | head -5`
3. Check trades: `tail -5 trades/sim_trades.jsonl`

## Format for Chris (15-min update):

```
📊 15-MINUTE UPDATE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 Balance: X.XXXX SOL (+XX.XX%)
📈 Record: XW/0L | All TP2 hits!

📋 RECENT TRADES:
(foreach trade, newest first)

💊 GMGN PUMP → ✅ WIN +0.XXXX SOL
🔗 https://dexscreener.com/solana/TOKENADDRESS

📡 NEW SIGNALS:
(foreach new signal)

💊 GMGN PUMP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 SYMBOL
📊 VOL +XX.X%
💎 FDV: $XXXK | Liq: $XXXK
🎯 TP1: +50% | TP2: +100% | Stop: -30%
🔗 https://dexscreener.com/solana/TOKENADDRESS

🧠 WHAT I'M LEARNING:
- Pattern insight 1
- Pattern insight 2
```

## If systems down
```
cd /root/.openclaw/workspace/trading-bot
/root/.openclaw/workspace/venv/bin/python scripts/combined_monitor.py &
/root/.openclaw/workspace/venv/bin/python scripts/gmgn_poll_monitor.py &
/root/.openclaw/workspace/venv/bin/python scripts/sim_trader.py &
```

## Git push (hourly)
```
git -C /root/.openclaw/workspace add -A && git -C /root/.openclaw/workspace commit -m "Update $(date)" && git -C /root/.openclaw/workspace push origin master
```
