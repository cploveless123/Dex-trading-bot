# Whale Trading Learnings

## Data Sources
- GMGN.ai: Smart money tracker, whale wallets
- DexScreener: Real-time pair data, mcap, liquidity
- Whale Wallets: 21 wallets being tracked (~6,219 SOL total)

## 21 Whale Wallets Tracked
1. suqh5sHtr8HyJ7q8scBimULPkPpA557prMG47xCHQfK - 5.02 SOL (ACCUMULATING)
2. CyaE1VxvBrahnPWkqm5VsdCvyS2QmNht2UFrKJHga54o - 131.77 SOL
... (full list in memory/wilson-rules.md)

## Whale Patterns Observed
- Accumulation before pumps
- Idle during low volatility
- Large transfers often precede moves

## Signals I Track
- GMGN PUMP signals
- DexScreener trending tokens
- Smart money buys (high net buy 1h)

## What Makes Tokens Pump
1. Whale accumulation (seen via GMGN)
2. Low mcap, high liquidity at entry
3. Dev action (burn/lock)
4. Positive social signals (checkmarks)
5. Low holder concentration (<10% top holders)

## What Kills Trades
1. Wrong MCap (signal stale vs real)
2. Fake addresses
3. Rug pulls (no mint + blacklist check)
4. Overtrading (max 5 positions)
5. Ignoring slippage on volatile launches

## Filters (STRICT)
- MCap: Verified on-chain (<20% discrepancy from signal)
- Age: <12 hours
- Liquidity: >$5,000
- Volume: >$5,000
- Holders: >10
- Social: Checkmarks
- Audit: NoMint + Blacklist pass

## Exit Strategy
- +20%: Sell 75%
- +100%: Full exit
- -20%: Stop loss

## Win/Loss Track Record
- Session: 0 wins, multiple losses (learning phase)
- Main issues: Bad data, stale signals, fake addresses
