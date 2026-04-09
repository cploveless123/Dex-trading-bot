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
| BS ratio | > 0.2 (<2 min) / >1.0 (>2 min) |
| Holders | > 15 |
| Vol/Mcap | > 1.1x |
| 5 min vol | > $1K |
| Liquidity | > $1K |

### Dip Detection

| Age | Rule |
| --------------- | --------------------------- |
| **New (<2 min)** | 11-39% dip + h1>+200% + 5min>+100% + vol>$1K |
| **Older (>2 min)** | 11-39% dip + h1>+200% + 5min>+50% + vol>$1K |

**Peak** = highest price seen in first 60 seconds

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

• Age-based BS ratio
• 11-39% peak dip
• High momentum confirmation (h1+200%)
• Liquidity > $1K
• 60s startup delay

---

**Target Win Rate: 50%+**
