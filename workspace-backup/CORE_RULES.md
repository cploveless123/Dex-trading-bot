# CORE RULES - EXACT MESSAGE FORMATS
## Chris's approved formats - USE EXACTLY THESE

---

## 📊 TRADE REPORT FORMAT:
```
📊 TRADE REPORT | HH:MM UTC
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 Balance: X.XXXX SOL
📈 Record: XW / XL

━━━━━━━━ OPEN POSITIONS ━━━━━━━━
[emoji] TOKEN NAME
   Entry: $XX,XXX → Live: $XX,XXX (+X%)
   https://dexscreener.com/solana/PAIRADDRESS

━━━━━━━━ LAST 5 TRADES ━━━━━━━━
[emoji] TOKEN NAME | +0.XXXX SOL (+XX%)
   BUY: $XX,XXX @ HH:MM:SS | SELL: $XX,XXX @ HH:MM:SS
   Reason: EXIT_REASON
   https://dexscreener.com/solana/PAIRADDRESS
```

---

## ✅ BUY ALERT FORMAT:
```
✅ BUY EXECUTED
━━━━━━━━━━━━━━━
💰 TOKEN NAME

📍 Entry MC: $XX,XXX
💵 Amount: 0.0X SOL

🔗 https://dexscreener.com/solana/PAIRADDRESS
🥧 https://pump.fun/TOKENADDRESS

🎯 Exit Plan:
+25% → Sell 50%
+100% → Sell 25%
+500% → Sell 15%
Rest → Hold
⚠️ Stop: -25%
```

---

## 🔴 SELL ALERT FORMAT:
```
🔴 SELL EXECUTED
━━━━━━━━━━━━━━━
💰 TOKEN NAME

📍 Entry MC: $XX,XXX
📍 Exit MC: $XX,XXX
[emoji] P&L: +0.XXXX SOL (+XX.X%)
📋 Reason: EXIT_REASON

🔗 https://dexscreener.com/solana/PAIRADDRESS
🥧 https://pump.fun/TOKENADDRESS
```

---

## ⚠️ KEY RULES:
- Use exact separator: ━━━━━ (not random dashes)
- Section headers: ━━━━━━━━ (full line)
- All URLs on their own line, plain https://
- Emoji before token name
- Timestamps: @ HH:MM:SS format
- Mcap numbers formatted: $XX,XXX

**Last updated: 2026-04-07 16:28 UTC**

### PARTIAL EXIT STATUS RULE (2026-04-07 16:32 UTC):
Chris: "Stop making these reoccurring mistakes"

When selling partial (e.g. 50% at TP1):
- status = "open_partial" (NOT "closed")
- closed = False
- partial_exit = True
- Exit reason = "TP1_PARTIAL" or similar

The trade is NOT fully closed until full exit or stop loss.
A partially exited position should show in OPEN POSITIONS.

### Updated partial exit handling in position_monitor.py:
- If partial_exit = True AND NOT full exit achieved → status = "open_partial"
- Only mark "closed" when fully exited (all positions sold)

### TIMESTAMPS ON ALL MESSAGES (LOCKED IN 2026-04-07 16:43 UTC):
Chris: "Perfect. Please don't forget"

ALL alerts and reports MUST include timestamp in header:
- ✅ BUY EXECUTED | HH:MM UTC
- 🔴 SELL EXECUTED | HH:MM UTC
- 📊 TRADE REPORT | HH:MM UTC

Timestamps prevent confusion about when actions occurred.
This is now permanently saved and will be backed up hourly.
