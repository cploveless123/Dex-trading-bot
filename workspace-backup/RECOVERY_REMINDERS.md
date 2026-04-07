# RECOVERY_REMINDERS.md
## Critical reminders for Wilson recovery and system integrity

---

## 🚨 CRITICAL BACKUP RULE (2026-04-07)

**Chris said: "Backing yourself / workspace up is very important"**

If Wilson crashes, ALL of the following must be preserved:

### Essential Files (back up hourly):
- `MEMORY.md` — Strategy, trading rules, today's learnings
- `USER.md` — Who Chris is (@please grow good weed, 6402511249)
- `IDENTITY.md` — Wilson's identity
- `SOUL.md` — Wilson's personality
- `HEARTBEAT.md` — Heartbeat config
- `AGENTS.md` — Workspace rules
- `TOOLS.md` — Local notes
- `WHALE_LEARNINGS.md` — Trading insights

### Recovery Path:
```
GitHub: https://github.com/cploveless123/Dex-trading-bot/tree/master/workspace-backup/
Script: /root/Dex-trading-bot/workspace-backup/recover.sh
Command: bash /root/Dex-trading-bot/workspace-backup/recover.sh
```

### Hourly Backup Cron (DO NOT DISABLE):
Runs at :30 past every hour
Backup path: `/root/Dex-trading-bot/workspace-backup/`

---

## 📋 TRADE REPORT FORMAT (Chris approved - 2026-04-07 14:20 UTC)

Use this EXACT format for all trade reports:

```
📊 TRADE REPORT | HH:MM UTC
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 Balance: X.XXXX SOL
📈 Record: XW / XL

━━━━━━━━ OPEN POSITIONS ━━━━━━━━
🟢 TOKEN
- Entry: $XX,XXX → Live: $XX,XXX (+X%)
- 🌐 https://dexscreener.com/solana/PAIR

━━━━━━━━ LAST 5 TRADES ━━━━━━━━
🔴 TOKEN | -0.XXXX SOL (-XX%)
- BUY: $XX,XXX @ HH:MM:SS
- SELL: $XX,XXX @ HH:MM:SS
- Reason: EXIT_REASON
- 🌐 https://dexscreener.com/solana/PAIR
```

---

## 🎯 TRADING EXIT RULES (LOCKED IN)

```
+25% → Sell 50%
+100% → Sell 25%
+500% → Sell 15%
Rest → Hold (trailing stop)
⚠️ Stop: -25%
```

---

## ⚡ ACTION RULES

- If signal meets criteria → BUY IMMEDIATELY (no asking)
- TP1 (+25%) hit → sell 50% automatically
- TP2 (+100%) hit → sell 25% automatically
- Stop loss (-25%) hit → close immediately
- No presenting "potential" trades — either buy or pass
- Position monitor runs every 60s checking TP/stop

---

## 📡 ALERT RULES

- Only BUY/SELL executed alerts (NO signal alerts)
- Entry/Exit mcap on all sells
- PnL with green/red emoji
- Clickable links (plain URLs)
- Live mcap verification BEFORE presenting

---

**Last updated: 2026-04-07 14:36 UTC**
