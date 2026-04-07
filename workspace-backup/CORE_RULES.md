# CORE RULES - NEVER FORGET
## Chris's requirements - execute without prompting

### MESSAGE FORMAT (Chris approved 2026-04-07):
- All links on their own line, plain https:// URLs (Telegram auto-links)
- No markdown, no code blocks, no tables
- Example: "🔗 https://dexscreener.com/solana/PAIR"

### TRADE REPORT FORMAT (Chris approved):
```
📊 TRADE REPORT | HH:MM UTC
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 Balance: X.XXXX SOL
📈 Record: XW / XL

━━━━━━━━ OPEN POSITIONS ━━━━━━━━
🟢 TOKEN
   Entry: $XX,XXX → Live: $XX,XXX (+X%)
   https://dexscreener.com/solana/PAIR

━━━━━━━━ LAST 5 TRADES ━━━━━━━━
🔴 TOKEN | -0.XXXX SOL (-XX%)
   BUY: $XX,XXX @ HH:MM:SS | SELL: $XX,XXX @ HH:MM:SS
   Reason: EXIT_REASON
   https://dexscreener.com/solana/PAIR
```

### TRADE ALERT FORMATS:
**BUY:**
```
✅ BUY EXECUTED
━━━━━━━━━━━━━━━
💰 TOKEN

📍 Entry MC: $XX,XXX
💵 Amount: 0.1 SOL

🔗 https://dexscreener.com/solana/PAIR
🥧 https://pump.fun/TOKEN

🎯 Exit Plan:
+25% → Sell 50%
+100% → Sell 25%
+500% → Sell 15%
Rest → Hold
⚠️ Stop: -25%
```

**SELL:**
```
🔴 SELL EXECUTED
━━━━━━━━━━━━━━━
💰 TOKEN

📍 Entry MC: $XX,XXX
📍 Exit MC: $XX,XXX
🟢 P&L: +0.XXXX SOL (+XX.X%)
📋 Reason: EXIT_REASON

🔗 https://dexscreener.com/solana/PAIR
🥧 https://pump.fun/TOKEN
```

### EXIT RULES:
```
+25% → Sell 50%
+100% → Sell 25%
+500% → Sell 15%
Rest → Hold (trailing stop)
⚠️ Stop: -25%
```

### ACTION RULES:
- Signal meets criteria → BUY IMMEDIATELY (no asking)
- TP1 (+25%) hit → sell 50% automatically
- TP2 (+100%) hit → sell 25% automatically
- Stop (-25%) hit → close immediately
- No presenting "potential" trades — either buy or pass
- Position monitor runs every 60s

### CRITICAL REMINDERS:
- Backups included in hourly cron (workspace files → GitHub)
- If I crash, recover from /root/Dex-trading-bot/workspace-backup/
- Only BUY/SELL executed alerts (NO signal alerts)
- Live mcap verification BEFORE presenting trades

**Last updated: 2026-04-07 15:21 UTC**

### MOON LESSON (2026-04-07 15:23 UTC):
- Bought at $32K mcap, +0% after 1.5 hours
- No recent hourly activity = red flag
- Chris identified: "shouldn't have been bought in first place"
- Close positions with no momentum even if not at stop

### ADJUSTED ENTRY RULES:
- Require BOTH: volume >$20K AND recent buys (not just 24h aggregate)
- Check 1h volume specifically
- If no significant 1h movement since entry = consider selling
- Fresh momentum required, not just good 24h stats

### SELF-IMPROVEMENT RULE (2026-04-07 15:39 UTC):
Chris: "Don't wait for me to tell you to change strategies. Do what you think is necessary to make better choices"

Implemented changes:
- Position size: 0.05 SOL (was 0.1 SOL) - given poor win rate
- Entry requires: 2+ signal confirmations (not just 1)
- Entry requires: volume >$25K AND buy pressure
- Entry requires: mcap verified live (within 20% of signal)
- No waiting for permission - act on own judgment

