# DEX Trading Bot - Simulation Spec

## Current State (to rebuild)
- 3 positions open
- 0.7 SOL reserve
- Telegram alerts firing on every buy
- Scanning every 90 seconds

## Tracking Goals
- Entry signals → do they predict winners?
- Time to TP1 on each position
- Whether we're cutting losses or letting winners run

## Risk Rules (from plan)
- Default position size: 0.1 SOL
- Take profit: 2x (100%) at TP1, 50% at TP2
- Stop loss: -30%

## GMGN Commands
- /buy
- /sell
- /create limitsell