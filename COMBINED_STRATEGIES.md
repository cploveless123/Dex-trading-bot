# Combined Trading Strategies v1.0
## Chris's Full Trade Strategy

---

## 🎯 OBJECTIVE
Turn 1.0 SOL → 100 SOL

---

## ✅ WINNER TRAITS
- Top10% holder < 50%
- BS ratio > 1.15
- Liquidity > $1K

## ❌ ANTI-PATTERNS (REJECT)
- Top10% > 70% = dump
- Liquidity < $1K = rug
- 5min change > 50% = chasing top
- 5min change < -50% = falling knife
- Non-ASCII ticker = reject

---

## 📊 BUY CRITERIA

| Rule | Value |
|------|-------|
| Mcap | $5K - $75K |
| BS ratio | > 0.20 |
| Holders | > 15 |
| Vol/Mcap | > 1.25x |
| **1 min change** | **-30% to +5% (PULLBACK ONLY)** |
| 5 min volume | > $1K |
| Liquidity | > $1K |
| Target WR | 35%+ |

---

## 📈 EXIT STRATEGY

| Target | Action |
|--------|--------|
| TP1 +50% | Sell 50%, trail 15% |
| TP2 +150% | Sell 25% |
| Trailing | 30% from peak |
| Stop | -20% |

---

## 🔧 FILTERS
- Confirmed pullback only (1min change -30% to +5%)
- Liquidity > $1K
- ASCII tickers only
- 60s startup delay

---

## ⚙️ ACTIVE SCANNER
| Scanner | Strategy |
|---------|----------|
| whale_momentum_scanner.py | PULLBACK_MOMENTUM |

---
