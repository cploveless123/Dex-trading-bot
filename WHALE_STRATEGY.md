# Whale Trading Strategy v1.0
## Based on 22 whale wallets + Chris's token pattern analysis

---

## 🎯 OBJECTIVE
Turn 1.0 SOL → 100 SOL via compound pump.fun/DEX trades

---

## 🐋 WHALE WALLETS (22 tracked)

### Top Performers (>50% WR)

| Wallet | Winrate | Avg Hold | Strategy |
|--------|---------|----------|----------|
| ATFRUwvy... | **100%** | 57 days | Long-term hold, huge winners |
| Hn6vBWWy... | **74%** | 11 days | Mid-term swing, CUM/MAPS/Oil |
| 4BdKaxN8... | **72%** | 16h | Quick swing, Hopecore specialist |
| 4uCT4g7Y... | **59%** | 14h | Rapid trades, AIFRUITS |
| DYAn4XpA... | **54%** | 11h | Mauri/LOOP swing |
| Hw5UKBU5... | **54%** | 43h | PEACE lover |
| GARVttNd... | **53%** | 15h | milkers specialist |
| FAicXNV5... | **53%** | 10h | The PVE/WIN |
| Fr9B91h3... | **51%** | 0.1h | Scalp KarpathyTalk |

### Scalpers (<1h hold)
- C1HWvjfa... (59% WR) - OG specialist
- 8iKJ2xKyc... (50% WR) - Speedrun

### UNIVERSAL PATTERN
> **ALL whales prefer sub-$10K mcap entries**

Every whale's history shows "<$10K=20 buys" preference.

---

## ✅ WINNER PATTERNS

| Token | Top10% | TradeFee | BS | Mcap | Result |
|-------|--------|---------|-----|------|--------|
| NEU | 47% | 54.7 | 1.20 | $718K | ✅ 8x+ in 11h |
| AOW | 31% | 37.9 | 1.21 | $1.4M | ✅ Winner |
| ROCKET | 39% | 142 | 1.62 | $418K | ✅ Winner |
| milkers | 42% | 53 | - | graduated | ✅ pump graduate |

**Winner traits:**
- Top10% < 50% (healthy distribution)
- Trade fee > 20 (smart money active)
- BS ratio > 1.15 (buy pressure)
- Graduated from pump.fun to Raydium

---

## ❌ LOSER ANTI-PATTERNS

| Token | Top10% | TradeFee | BS | Result |
|-------|--------|---------|-----|--------|
| RISE | 82% | 71 | - | ❌ -99% (dumper) |
| Unknown | 85% | - | - | ❌ -99% |
| Cope | 75% | 1.5 | - | ⚠️ Danger |
| $PLUG | 64% | 2.3 | 0.71 | ❌ Bad BS |

**Anti-pattern traits:**
- Top10% > 70% = dump risk (REJECT IMMEDIATELY)
- BS ratio < 1.0 = more sells than buys
- Trade fee < 5 = no smart money

---

## 📊 BUY CRITERIA (v3)

### Hard Filters
- Mcap: $5,000 - $75,000 (<3min old) / $9,000 - $75,000 (>3min old)
- BS Ratio: 0.25+ (<2min) / 1.0+ (>2min)
- Holders: 15+
- Min 5min volume: $1,000
- Top 10 holder % < 70% (reject if >70%)

### Early Momentum Tier
- $5K-$12K mcap + vol/mcap 1:1+ = BUY SIGNAL (bypasses BS check)

### Pattern Filters
- Top 10 holder % < 50% ✅ (healthy)
- Trade fee > 20 ✅ (smart money active)
- BS ratio > 0.99 ✅ (buy pressure)
- Vol/Mcap alone = insufficient (need whale + BS)

### Anti-Patterns (reject immediately)
- Top 10 holder > 70% = dump risk
- BS < 1.0 = sell pressure (>3min pairs)
- Liquidity < $5K = rug risk

### Pullback Entry Rule
> **Buy AFTER dip, not on pump**

For pairs >5min old:
- 5min change must be 0-40% (pullback zone)
- If 5min chg >40% = skip (bought the top)
- If 5min chg <-20% = skip (falling knife)
- If 5min chg <0% AND BS <2.0 = skip (no support)

---

## 🐋 WHALE FOLLOW STRATEGY

### When a tracked whale buys a new token:
1. Check if we already hold it → skip
2. Apply stricter filters:
   - BS > 1.5 (stricter than normal)
   - Holders > 20
   - Mcap < $75K
   - PRIORITIZE sub-$10K entries (whale preference)
3. Auto-enter at 0.025 SOL

### Whale-Only Filters
- Only follow whales with >50% WR
- Only follow whales with 3+ buys
- Weight sub-$10K entries higher

---

## 📈 EXIT STRATEGY (tax-adjusted 2.5% per round trip)

- **TP1**: +50% minimum → 15% trailing from peak → sell 50%
- **TP2**: +200% → sell 25%
- **TP3**: +500% → sell remaining 25%
- **Trailing**: 30% from peak on remaining
- **Stop**: -20% (net: -20.5%)

---

## ⚠️ CRITICAL LESSONS

### JellyBean Post-Mortem
- 170x vol/mcap at entry = EXTREME signal
- But we entered at $74K (near peak)
- Dumped to $2K → stopped out -97%
- **Lesson: Entry timing > signal strength. Wait for pullback.**

### FRUGHTEST INSIGHT
> High vol/mcap (100x+) can signal pump BUT:
> - Entering at peak mcap = disaster
> - Low liquidity coins dump hard after initial pump
> - Check liquidity before position size

### What Winners Have in Common
1. Graduated from pump.fun (proved demand)
2. Top10% < 50% (decent distribution)
3. Trade fee > 20 (continuous smart money activity)
4. BS ratio stays > 1.15 after entry
5. Sub-$10K entry mcap

---

## 🔧 SCANNERS ACTIVE

| Scanner | Purpose |
|---------|---------|
| auto_scanner.py | Pullback filter (conservative) |
| gmgn_buyer.py | GMGN whale/KOL signals |
| new_pair_scanner.py | Fresh Raydium pairs + migrations |
| bonding_scanner.py | pump.fun bonding curve |
| whale_follower.py | Copies 10 tracked whales (>50% WR) |
| position_monitor.py | TP/stop execution |
| alert_sender.py | Telegram alerts |

---

## 📊 SIM RESET
- Date: 2026-04-09T14:14:44
- Starting: 1.0 SOL
- Goal: 100 SOL

---

*v1.0 - Built from 22 whale wallets + Chris's token pattern analysis*
