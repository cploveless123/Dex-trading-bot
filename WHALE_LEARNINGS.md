# Whale Trading Learnings

## Data Sources
- GMGN.ai: Smart money tracker, whale wallets
- DexScreener: Real-time pair data, mcap, liquidity
- Whale Wallets: 21 wallets being tracked (~6,219 SOL total)

## 21 Whale Wallets Tracked
1. suqh5sHtr8HyJ7q8scBimULPkPpA557prMG47xCHQfK - 5.02 SOL (ACCUMULATING)
2. CyaE1VxvBrahnPWkqm5VsdCvyS2QmNht2UFrKJHga54o - 131.77 SOL
... (full list in memory/wilson-rules.md)

## Whale Patterns Observed
- Accumulation before pumps
- Idle during low volatility
- Large transfers often precede moves

## Signals I Track
- GMGN PUMP signals
- DexScreener trending tokens
- Smart money buys (high net buy 1h)

## What Makes Tokens Pump
1. Whale accumulation (seen via GMGN)
2. Low mcap, high liquidity at entry
3. Dev action (burn/lock)
4. Positive social signals (checkmarks)
5. Low holder concentration (<10% top holders)

## What Kills Trades
1. Wrong MCap (signal stale vs real)
2. Fake addresses
3. Rug pulls (no mint + blacklist check)
4. Overtrading (max 5 positions)
5. Ignoring slippage on volatile launches

## Filters (STRICT)
- MCap: Verified on-chain (<20% discrepancy from signal)
- Age: <12 hours
- Liquidity: >$5,000
- Volume: >$5,000
- Holders: >10
- Social: Checkmarks
- Audit: NoMint + Blacklist pass

## Exit Strategy
- +20%: Sell 75%
- +100%: Full exit
- -20%: Stop loss

## Win/Loss Track Record
- Session: 0 wins, multiple losses (learning phase)
- Main issues: Bad data, stale signals, fake addresses

## PROFIT-TAKING FRAMEWORK (from Chris - 2026-04-07 13:13 UTC)

### 🎯 Exit Ladder
| Target | Action |
|--------|--------|
| +25% to +100% | Sell 50% → recoup investment, risk-free position |
| 2x-10x | Sell 25% → lock in gains |
| 20x+ | Sell 15-20% → capture moonshot |
| Remainder | Hold + trailing stop → lottery ticket for 100x+ |

### ⚠️ Stop Loss: -25% (not -20%)

### 📊 Position Sizing
- Never risk >1-5% of capital per trade
- Makes partial exits psychologically easier

### 🔧 Tools
- GMGN auto-sell orders (2x, 5x, 10x presets)
- Wallet monitoring → follow smart money
- Trailing stop-loss

### 🐋 Whale Signals
- When whales distribute = signal to take profits
- Social hype peaking = often local top

### ✅ Pre-Trade Checklist
1. Position size? (never >5% capital)
2. Stop-loss level?
3. Exit ladder? (write it down)
4. Max daily loss limit?

### 💡 Key Insight
"Winning in Solana memecoins is largely about surviving long enough to find it."

## CRITICAL RULES (committed 2026-04-07 13:46 UTC)

### Exit Rules (STRICT):
```
+25% → Sell 50%
+100% → Sell 25%
+500% → Sell 15%
Rest → Hold (trailing stop)
⚠️ Stop: -25%
```

### Alert Format (ALL alerts):
- Entry MC + Exit MC on ALL sells
- PnL with green/red emoji
- Clickable links (plain URLs)
- Live mcap verification BEFORE presenting

### Action Triggers:
- TP1 (+25%) hit → sell 50% immediately
- Stop loss (-25%) hit → close immediately  
- No asking, just doing

### Git:
- Commit after every trade action
- Include exit rules in commit message

## BEHAVIOR SHIFT (2026-04-07 13:52 UTC)

### OLD Behavior:
- Presented "potential trades" for Chris to decide
- Asked permission before every action
- Filtered too conservatively

### NEW Behavior (DECIDED):
- If signal meets criteria → BUY IMMEDIATELY
- No presenting "potential" trades
- Either buy or pass - binary decision
- Commit after every action

### This Session's Trades:
- POW: +48% ✅ (first win)
- BABEPSTEIN: +38% partial ✅ (sold 50%)
- MOON: entry $32K | +982% 24h 🚀 NEW
- TRUMPLER: -34% ❌ (stop loss)

### Key Learning:
Learning by DOING > watching and waiting
Proof of concept = actual trades, not analysis

## PERMANENT STRATEGY (saved 2026-04-07 13:57 UTC)

### 🎯 Exit Rules (NEVER CHANGE):
```
+25% → Sell 50%
+100% → Sell 25%  
+500% → Sell 15%
Rest → Hold (trailing stop)
⚠️ Stop: -25%
```

### ⚡ Action Rules (NEVER CHANGE):
- Signal meets criteria → BUY IMMEDIATELY (no asking)
- TP1 (+25%) hit → sell 50% immediately
- TP2 (+100%) hit → sell 25% immediately
- Stop loss (-25%) hit → close immediately
- No presenting trades - either buy or pass

### 📊 Alert Format (ALWAYS):
```
✅ BUY EXECUTED / 🔴 SELL EXECUTED
━━━━━━━━━━━━━━━
💰 TOKEN
📍 Entry MC: $XX,XXX
📍 Exit MC: $XX,XXX (sells only)
🟢/🔴 P&L: +X.XXXX SOL (+XX.X%)
📋 Reason: TP1_PARTIAL / STOP_LOSS / etc
🔗 https://clickable.link
🥧 https://clickable.link
```

### 🔍 Scan Rules:
- Live mcap verification BEFORE presenting
- Pump.fun only: Mcap $5K-$100K, Vol >$15K
- No presenting "potential" trades

### 📈 This Session Proof:
- BABEPSTEIN: +77% (sold 75%, 25% held)
- MOON: Entry $32K, +982% 24h momentum
- POW: +48% first win
- TRUMPLER: -34% stop loss (accepted)

### 💡 Key Insight:
"Learning by DOING > watching and waiting"
Proof of concept = actual trades, not analysis

## AUTO POSITION MONITOR (2026-04-07 14:06 UTC)

### New Process Running:
`position_monitor.py` - runs every 60 seconds

### What it does automatically:
- TP1 +25% → sell 50% → Telegram alert
- TP2 +100% → sell 25% → Telegram alert  
- TP3 +500% → full exit → Telegram alert
- Stop -25% → close → Telegram alert

### NO PROMPTING NEEDED
Bot executes, sends alert, that's it.

## TRADE REPORT FORMAT (Chris approved 2026-04-07 14:23 UTC)

### MUST USE THIS EXACT FORMAT FOR ALL TRADE REPORTS:

```
📊 TRADE REPORT | HH:MM UTC
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 Balance: X.XXXX SOL
📈 Record: XW / XL

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

━━━━━━━━ OPEN POSITIONS ━━━━━━━━

🟢 TOKEN
- Entry: $XX,XXX → Live: $XX,XXX (+X%)
- 🌐 https://dexscreener.com/solana/PAIR

🟢 TOKEN  
- Entry: $XX,XXX → Live: $XX,XXX (+X%)
- 🌐 https://dexscreener.com/solana/PAIR

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

━━━━━━━━ LAST 5 TRADES ━━━━━━━━

🔴 TOKEN | -0.XXXX SOL (-XX%)
- BUY: $XX,XXX @ HH:MM:SS
- SELL: $XX,XXX @ HH:MM:SS
- Reason: EXIT_REASON
- 🌐 https://dexscreener.com/solana/PAIR

🟢 TOKEN | +0.XXXX SOL (+XX%)
- BUY: $XX,XXX @ HH:MM:SS
- SELL: $XX,XXX @ HH:MM:SS
- Reason: EXIT_REASON
- 🌐 https://dexscreener.com/solana/PAIR
```

### RULES:
- Last 5 trades (NOT 10)
- Include open positions with live mcap + link
- Show balance + win/loss record
- Include buy mcap + sell mcap + timestamps for each trade
- Green/red emoji for win/loss
- All links clickable
- Always timestamped
