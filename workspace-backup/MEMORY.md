# MEMORY.md - Long-Term Memory

## Trading Bot Setup
- Location: `/root/Dex-trading-bot/`
- Git remote: https://github.com/cploveless123/Dex-trading-bot.git
- Telegram alerts via @WilsonVultrBot (token: 8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg)
- Chat ID: 6402511249 (Chris - "please grow good weed")

## Trading Strategy (CORRECTED - 2026-04-08)

### Exit Rules:
```
+35% → Sell 70%
+95% → Sell 30%
⚠️ Stop: -25%
```

### Alert Format:
- Telegram uses HTML mode (Markdown fails on emoji → HTTP 400)
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
`auto_scanner.py` runs every 90s scanning for buys
`alert_sender.py` runs every 30s sending Telegram alerts

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

## Trading Lessons Learned
- NODES bought 6 times in one day, stopped out 4x → ~0.15 SOL lost to repeat chasing
- Re-entry lockout added: no re-buy of stopped tokens within 30 min unless strong momentum (bs 2.5+, chg 50%+)
- Markdown mode in Telegram fails with certain emoji → use HTML mode
- .last_alert_index can go stale and cause missed alerts → must sync to actual trade count
- Position monitor and sim_trader had hardcoded wrong thresholds → must use trading_constants

## Whales Tracked
- GH9yk8vgFvHnAD8JZqXxr3hBN1Lr1mJ9NPzrP5mVqiJe (Chris-added 2026-04-08)
- 4 others tracked in wallet_analysis/whale_wallets.jsonl

## HOURLY BACKUP (CRITICAL - DO NOT SKIP)
Hourly cron job backs up to GitHub:
- Workspace files: *.md, BOOTSTRAP.md
- Cron jobs: /root/.openclaw/cron/jobs.json
- Workspace skills: skills/
- System skills: /opt/node22/lib/node_modules/openclaw/skills/
Job ID: 16429a40-b0b6-470e-8c3e-8c154b57862a (hourly-bot-backup)
Runs at :30 every hour
