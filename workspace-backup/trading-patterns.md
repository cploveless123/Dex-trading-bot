# Trading Patterns Learned — 2026-04-08

## Win/Loss Analysis (110 trades, 18% WR)

### WINNERS (20 trades, avg +0.0539 SOL)
- Entry reason: MOMENTUM signal only
- Entry mcap range: $5,206 - $52,976 (avg $17,522)
- Best performers: STREAMER (+0.10), POW (+0.048), BABEPSTEIN (+0.077 partial)

### LOSERS (90 trades, avg -0.024 SOL)
- Entry reason: MOMENTUM signal (same as winners!)
- Entry mcap range: $4,589 - $78,861 (avg $18,394)
- 65 stop losses | 22 manual closes

### CRITICAL PROBLEM: TP2 never fires
- TP2 threshold is +95% — TOO HIGH
- Only 3 trades ever reached TP2 in 110 trades
- Winners avg +54% but we only capture +35% (TP1 sell 70%)
- TP1 sells 70% too early — leaving too much on table

## Signal Sources
| Source | WR | PnL |
|--------|-----|-----|
| live_scan | 25% | +0.10 |
| manual_scan | 50% | +0.10 |
| auto_scanner | 25% | -0.04 |
| auto_scanner_v2 | 16% | -0.56 |
| combined_monitor_live_verify | 0% | -0.03 |

## What Makes a Winner vs Loser
Both have same: entry mcap range, MOMENTUM signal, similar liquidity
**The difference is not in entry — it's timing and luck**

## GMGN Channel Signals (450+ captured)
- PUMP signals: 29/50 recent
- KOTH: 6/50
- KOL_BUY: 3/50
- Liquidity: $1.5K - $83B (very wide)
- Holders: 3 - 2718 (very wide)

## Pattern Recommendations
1. **Lower TP2 threshold** — +95% is too high. Consider +60% or +70%
2. **Re-entry lockout works** — NODES problem fixed
3. **GMGN signals are noisy** — most don't translate to trades
4. **Scanner needs better filtering** — both winners and losers use MOMENTUM
5. **Consider trailing stop** — instead of fixed TP2

## What I'm Learning From GMGN Channels
- Most signals are early-stage pumps (PUMP type)
- LP burn signals (@sollpburnt) indicate token maturity
- New pool signals (@solnewlp) catch launches early
- Degen calls are high risk but can be explosive
- Need to correlate GMGN signals with on-chain data (liquidity, holders)
