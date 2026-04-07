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
