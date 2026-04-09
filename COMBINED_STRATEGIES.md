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
| ------|------- |
| Mcap | $5K - $75K |
| BS ratio | > 0.20 |
| Holders | > 15 |
| Vol/Mcap | > 1.15x |
| 5 min vol | > $1K |
| Liquidity | > $1K |

### Pullback Detection

| Type | Rule |
| --------------- | --------------------------- |
| New (<90 sec) | 30% dip from local peak |
| Older (>90 sec) | 30% dip from local peak |

### Volume Momentum Filter
• High 1min% + **declining volume** = **TOP FORMING** (reject)
• High 1min% + **increasing volume** = momentum still going (hold)

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

• 30% dip from local peak (all pairs)
• Volume momentum confirmation
• Liquidity > $1K
• 60s startup delay

---

**Target Win Rate: 50%+**
