# MESSAGE FORMAT RULES - ALWAYS USE THIS

## Chris's Rules (2026-04-07 14:49 UTC):

### URL/Links - MUST BE CLICKABLE:
- Plain https:// URLs on their own line
- Telegram auto-detects and makes them clickable
- One link per line, nothing else on that line
- Example:
```
🔗 https://dexscreener.com/solana/PAIRADDRESS
🥧 https://pump.fun/TOKENADDRESS
💵 /buy TOKENADDRESS 0.1
```

### DON'T DO:
- Markdown links like [text](url)
- URLs with text directly before without space
- URLs in tables or code blocks
- Mixed formatting with URLs

---

## Trade Alerts - BUY format:
```
✅ BUY EXECUTED
━━━━━━━━━━━━━━━
💰 TOKEN

📍 Entry MC: $XX,XXX
💵 Amount: 0.1 SOL

🔗 https://dexscreener.com/solana/PAIRADDRESS
🥧 https://pump.fun/TOKENADDRESS

🎯 Exit Plan:
+25% → Sell 50%
+100% → Sell 25%
+500% → Sell 15%
Rest → Hold
⚠️ Stop: -25%
```

## Trade Alerts - SELL format:
```
🔴 SELL EXECUTED
━━━━━━━━━━━━━━━
💰 TOKEN

📍 Entry MC: $XX,XXX
📍 Exit MC: $XX,XXX
🟢 P&L: +0.XXXX SOL (+XX.X%)
📋 Reason: TP1_PARTIAL

🔗 https://dexscreener.com/solana/PAIRADDRESS
🥧 https://pump.fun/TOKENADDRESS
```

## Trade Report format:
See RECOVERY_REMINDERS.md - same format every time

---

## Key Reminders:
- Last 5 trades (not 10)
- Open positions with live mcap + clickable link
- Balance + record
- Green/red emoji for PnL
- Timestamps on all trades
- Buy mcap + sell mcap

**Last updated: 2026-04-07 14:49 UTC**
