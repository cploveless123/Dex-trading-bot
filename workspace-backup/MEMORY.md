# MEMORY.md - Long-Term Memory

## Trading Bot Setup
- Location: `/root/Dex-trading-bot/`
- Git remote: https://github.com/cploveless123/Dex-trading-bot.git
- Telegram alerts via @WilsonVultrBot (token: 8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg)
- Chat ID: 6402511249 (Chris - "please grow good weed")

## Trading Strategy (LOCKED IN - 2026-04-07)

### Exit Rules:
```
+25% → Sell 50%
+100% → Sell 25%
+500% → Sell 15%
Rest → Hold (trailing stop)
⚠️ Stop: -25%
```

### Alert Format:
- Entry/Exit mcap on all sells
- PnL with green/red emoji
- Clickable links (plain URLs)
- No signal alerts - only BUY/SELL executed

### Trade Report Format (Chris approved):
- Last 5 trades (NOT 10)
- Open positions with live mcap + link
- Balance + record
- Buy mcap + sell mcap + timestamps
- Green/red emoji
- All links clickable

### Auto Monitor:
`position_monitor.py` runs every 60s checking TP/stop hits

## Today's Trades (2026-04-07)

### Wins:
- POW: +48% (first win)
- BABEPSTEIN: +77% partial (stop final)
- MOON: +50% partial (sold 50%)
- MJG: +355% full exit 🚀

### Losses:
- TRUMPLER: -25% stop
- BABEPSTEIN: -83% final stop
- Solana: +0% (user exit)
- conviction: -5%
- Various: small losses

## Current Positions:
- MOON: 50% held, entry $32.4K
- CHAIN: entry $78.8K, +19%

## Chris (@please grow good weed):
- Trading style: Aggressive, wants action not analysis
- Rule: "Either buy or pass - no presenting signals"
- Wants continuous scanning and trading
- Prefers fast decisions over perfect analysis
- Very detail-oriented on alert/report format

## HOURLY BACKUP (CRITICAL - DO NOT SKIP)
Hourly cron job backs up to GitHub:
- Workspace files: *.md, BOOTSTRAP.md
- Cron jobs: /root/.openclaw/cron/jobs.json
- Workspace skills: skills/
- System skills: /opt/node22/lib/node_modules/openclaw/skills/
Job ID: 16429a40-b0b6-470e-8c3e-8c154b57862a (hourly-bot-backup)
Runs at :30 every hour
