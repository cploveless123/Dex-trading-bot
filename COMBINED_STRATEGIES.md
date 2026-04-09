# Trading Strategy v1.0
## Chris's Full Trade Strategy

---

## 🎯 OBJECTIVE
Turn 1.0 SOL → 100 SOL

---

## ✅ WINNER TRAITS
- Top10% holder < 50%
- BS ratio > 0.20
- Liquidity > $1K

## ❌ ANTI-PATTERNS (REJECT)
- Top10% > 70% = dump
- Liquidity < $1K = rug
- 1min change > 50% = chasing top
- 1min change < -50% = falling knife
- Non-ASCII ticker = reject

---

## 📊 BUY CRITERIA

| Rule | Value |
|------|-------|
| Mcap | $5K - $75K |
| BS ratio | > 0.20 |
| Holders | > 15 |
| Vol/Mcap | > 1.25x |
| 1 min change | -30% to +5% |
| 5 min volume | > $1K |
| Liquidity | > $1K |

---

## 📈 EXIT STRATEGY (tax-adjusted 2.5% per round trip)

| Target | Action |
|--------|--------|
| TP1 +50% | Sell 50%, trail 15% |
| TP2 +200% | Sell 25% more |
| TP3 +500% | Sell remaining 25% |
| Trailing | 30% from peak on remaining |
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
|--------|----------|
| whale_momentum_scanner.py | PULLBACK_MOMENTUM |

---
