# Trading Strategy v1.0

---

## 🎯 OBJECTIVE

Turn 1.0 SOL → 100 SOL

---

## ✅ WINNER TRAITS

• Top10% holder < 50%
• BS ratio > 1.15
• Liquidity > $1K

---

## ❌ ANTI-PATTERNS (REJECT)

• Top10% > 70% = dump
• Liquidity < $1K = rug
• Non-ASCII ticker = reject

---

## 📊 BUY CRITERIA

| Rule | Value |
| --------- | ---------- |
| Mcap | $5K - $75K |
| BS ratio | > 0.20 |
| Holders | > 15 |
| Vol/Mcap | > 1.25x |
| 5 min vol | > $1K |
| Liquidity | > $1K |

### Pullback Detection

| Age | Rule |
| --------------- | --------------------------- |
| New (<90 sec) | Initial dip 5-30% from peak |
| Older (>90 sec) | h1 positive + m5 negative |

---

## 📈 EXIT STRATEGY

| Target | Action |
| --------- | ------------------- |
| TP1 +50% | Sell 50%, trail 15% |
| TP2 +150% | Sell 25% |
| Trailing | 30% from peak |
| Stop | -20% |

---

## 🔧 FILTERS

• Initial dip for new pairs (<90 sec)
• Multi-timeframe for older pairs
• Liquidity > $1K
• ASCII tickers only

