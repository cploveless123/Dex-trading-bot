# KOL & Price Action Pattern Learning

## Methodology
- Track every signal with full metrics
- Record if traded, entry price, exit price
- Build patterns: which signals → winners vs dumps

## Signal Analysis (Apr 5-6)

### WIN: 714 (PancakeSwap BSC)
| Metric | Value |
|--------|-------|
| Source | DexScreener |
| Signal | HIGH_VOLUME_PUMP + RAPID_MOVE |
| Price Change | +673% |
| Liquidity | $61.5K |
| FDV | $403K |
| Volume | $1.49M |
| Buy/Sell Ratio | 1.07 |
| Exit | TIME_EXIT (TP1 hit) |
| PnL | +32.4% net |

**Pattern learnings:**
- Massive volume spike (>100% price change)
- High liquidity relative to mcap
- Took profit at TP1 instead of holding to TP2

---

### Signals Tracked (not traded yet)

| Token | Signal | Price +% | MCap | Liq | B/S | Notes |
|-------|--------|----------|------|-----|-----|-------|
| QUACKY | RAPID_MOVE | +202% | $102K | $24K | 1.32 | Pumpswap |
| stonks | BUY_MOMENTUM | +601% | $17K | - | 2.06 | pump.fun |
| cumcoin | RAPID_MOVE | +60% | $63K | - | 1.42 | pump.fun |
| Fertcuin | - | - | - | - | - | - |
| SUPERCAT | BUY_MOMENTUM | +232% | $112K | $26K | 7.58 | Very high B/S! |

---

## Pattern Observations

### What worked (714):
- Massive price spike (+673%)
- High volume ($1.49M)
- Liquidity adequate ($61K)
- Exit: TP1 hit → time exit

### Signals to watch:
- **High B/S ratio (>3)** = strong buy pressure
- **+200%+ price change** = momentum
- **BUY_MOMENTUM signal** = multiple buyers

### Signals to avoid (later):
- Low liquidity (<$20K)
- High top holder % (rug risk)
- Very new tokens (<1 min)

---

## KOL Tracking (future)
- Need GMGN re-auth to track KOL signals
- Track: which KOL → success rate
- Track: entry timing after KOL buy

## Next: Continue logging, add price checks on old signals