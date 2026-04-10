# Trading Strategy v1.0

---

## 🎯 OBJECTIVE

Turn 1.0 SOL → 100 SOL

---

## ✅ WINNER TRAITS

• Top10% holder < 50% (ignore if 0)
• BS ratio > 0.9 (>5 min) / >0.2 (<5 min)
• Liquidity > $1K (waived for bonding curve)

---

## ❌ ANTI-PATTERNS (REJECT)

• Top10% > 70% = dump (ignore if 0)
• NoMint / Mintable tokens
• Blacklisted tokens
• Non-ASCII ticker = reject

---

## 📊 BUY CRITERIA

| Rule | Value |
| ------|------- |
| Mcap | $5K - $95K |
| BS ratio | > 0.2 (<5 min) / > 0.9 (>5 min) |
| Holders | > 15 |
| 5 min vol | > $1K |
| Liquidity | > $1K (waived for bonding curve) |

### Dip Detection

| Age | Rule |
| --------------- | --------------------------- |
| **New (<5 min)** | 11-39% dip + h1>+50% + 5min>+50% |
| **Older (>5 min)** | 11-39% dip + **24hr>+25%** + **h1>-39%** + **5min>-39%** |

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
• **24hr > +25% for older pairs**
• **Allows negative h1 and 5min for older pairs**
• Liquidity waived for bonding curve
• 15 second scan interval

---

**Target Win Rate: 50%+**
