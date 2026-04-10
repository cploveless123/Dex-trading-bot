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
• Liquidity < $1K = rug (unless bonding curve)
• NoMint / Mintable tokens
• Blacklisted tokens
• Non-ASCII ticker = reject

---

## 📊 BUY CRITERIA

| Rule | Value |
| ------|------- |
| Mcap | $5K - $75K |
| BS ratio | > 0.2 (<5 min) / >0.9 (>5 min) |
| Holders | > 15 |
| Vol/Mcap | > 1.1x |
| 5 min vol | > $1K |
| Liquidity | > $1K (waived for bonding curve) |

### Dip Detection

| Age | Rule |
| --------------- | --------------------------- |
| **New (<5 min)** | 11-39% dip + h1>+50% + 5min>+50% + vol>$1K |
| **Older (>5 min)** | 11-39% dip + h1>+1% + 5min>+1% + vol>$1K |

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

• NoMint / Blacklist checks
• Age-based BS ratio
• 11-39% peak dip
• Liquidity waived for bonding curve pairs
• 60s startup delay

---

**Target Win Rate: 50%+**
