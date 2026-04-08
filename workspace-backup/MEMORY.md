# MEMORY.md - Long-Term Memory

## Trading Bot Setup
- Location: `/root/Dex-trading-bot/`
- Git remote: https://github.com/cploveless123/Dex-trading-bot.git
- Telegram alerts via @WilsonVultrBot (token: 8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg)
- Chat ID: 6402511249 (Chris - "please grow good weed")

## Trading Strategy (CORRECTED - 2026-04-08)

### Exit Rules (UPDATED - trailing stop):
```
+35% → Sell initial investment (~74% of position — recovers 0.05 SOL)
Remaining ~26%: TRAILING STOP — sell if 20% drop from peak
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
- Re-entry lockout added: no re-buy of stopped tokens within 30 min unless strong momentum (bs 3.0+, chg 60%+)
- Markdown mode in Telegram fails with certain emoji → use HTML mode
- .last_alert_index can go stale and cause missed alerts → must sync to actual trade count
- Position monitor and sim_trader had hardcoded wrong thresholds → must use trading_constants
- TP2 threshold of +95% is too high — only 3 trades hit it in 110. Winners avg +54% but we only capture +35% at TP1
- Scanner is catching dumps (both winners and losers use MOMENTUM) — same signal, different outcome = timing/luck

## Trading Patterns
See `/root/.openclaw/workspace/trading-patterns.md` for full analysis

## Win Rate Problem
- Current WR: 18% (20W/90L)
- Scanner filters were too loose — MOMENTUM signal fires on both winners and losers
- GMGN signals are mostly noise — PUMP signals dominate but rarely translate to wins
- Need: better entry confirmation, not just MOMENTUM scan

## Entry Criteria (UPDATED per Chris)
- Mcap: $5K-$100K
- 24h volume: $15K+
- 5min volume: $2K+
- Buy/sell ratio: 1.5+
- Holders: 15+
- Pump.fun only
- 30 min re-entry lockout after any close
- NODES bought 6 times in one day, stopped out 4x → ~0.15 SOL lost to repeat chasing
- Re-entry lockout added: no re-buy of stopped tokens within 30 min unless strong momentum (bs 2.5+, chg 50%+)
- Markdown mode in Telegram fails with certain emoji → use HTML mode
- .last_alert_index can go stale and cause missed alerts → must sync to actual trade count
- Position monitor and sim_trader had hardcoded wrong thresholds → must use trading_constants

## Whales Tracked
- GH9yk8vgFvHnAD8JZqXxr3hBN1Lr1mJ9NPzrP5mVqiJe (Chris-added 2026-04-08)
- 4 others tracked in wallet_analysis/whale_wallets.jsonl

## GMGN Channels Watched (7 total)
- @gmgnai — 💎GMGN Degen Group - Official
- @gmgnsignals — GMGN Featured Signals (Lv2) - SOL
- @gmgn_trading — Solana Trading
- @pump_sol_alert — Portal for Pump Alert Channel - GMGN
- @solnewlp — Portal for Solana New Pool Channel - GMGN
- @sollpburnt — Portal for Sol LP Burn - GMGN
- @gmgn_degencalls — 💎Portal for Degen Calls - GMGN

## HOURLY BACKUP (CRITICAL - DO NOT SKIP)
Chris explicitly said: "Don't ever forget to do this."
Hourly cron job backs up to GitHub — runs every :30 at :30 UTC:
- Workspace files: *.md, BOOTSTRAP.md
- Cron jobs: /root/.openclaw/cron/jobs.json
- Workspace skills: skills/
- System skills: /opt/node22/lib/node_modules/openclaw/skills/
Job ID: 16429a40-b0b6-470e-8c3e-8c154b57862a (hourly-bot-backup)
Runs at :30 every hour
