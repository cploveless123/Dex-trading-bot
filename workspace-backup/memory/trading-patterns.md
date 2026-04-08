# Trading Pattern Learnings

## Today's Data (Apr 6, 2026)

### Signal Analysis (127 signals scanned)
| Token | Mcap | Vol 24h | Change | DEX | Signals | Triggered? |
|-------|------|---------|--------|-----|---------|------------|
| TRAP | $2.8M | $65k | +190466% | meteora | STRONG_BUY_PRESSURE + RAPID_MOVE + BUY_MOMENTUM | No |
| Time | $358k | $1051k | +959% | pumpswap | RAPID_MOVE | No |
| 돼지 | $140k | $329k | +258% | pumpswap | RAPID_MOVE + BUY_MOMENTUM | No |
| STONKS9800 | $17k | $45k | +606% | pumpfun | BUY_MOMENTUM | No |
| 714 | $26M | $575k | +26% | pancakeswap | HIGH_VOLUME_PUMP + STRONG_BUY_PRESSURE | YES → +0.032 SOL |

### Filters Applied (why many rejected)
- Min mcap: $10k (CTRUMP $17k didn't trigger)
- Min volume: $10k
- Must be Solana (714 is BSC, but still bought)
- Liquidity requirement

### Key Patterns
1. **Very conservative filtering** - 127 signals → 1 trade (0.8% trigger rate)
2. **Repeated tokens** = 돼지 appeared 4x, 714 appeared 3x - shows momentum
3. **Best signal combo:** STRONG_BUY_PRESSURE + RAPID_MOVE + BUY_MOMENTUM (TRAP had all 3 but filtered)
4. **DEX preference:** pumpswap > pumpfun > meteora > pancakeswap

### Trade Result
- **714** (BSC): Bought 0.1 SOL @ 0.0001, exited TIME_EXIT at TP1
- **PnL:** +0.032 SOL (+32%)
- **TP1 contribution:** +0.0286 SOL (89% of total gain)
- **Time in trade:** ~2 hours

### Missing Data
- No GMGN signals received yet (just connected)
- No loss examples to learn from
- No SL triggers observed

---

*Updated: 2026-04-06 14:53 UTC*