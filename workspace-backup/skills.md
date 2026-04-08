# Wilson's Trading Skills

## Active Skills
- **DexScreener scanning** - Reading signals, analyzing liquidity/volume/mcap
- **Simulation trading** - Testing strategies with 5% costs built in

## Skills to Build

### Token Launch Sniping (pump.fun)
- **How it works:** New Solana tokens launch on pump.fun, snipe at launch
- **API:** api.pump.fun (new token monitoring)
- **Key metrics to analyze:** Creator wallet age, initial buys, holder distribution
- **Challenge:** Speed critical - need fast RPC
- **Approach:** Build monitor first in sim, then integrate wallet for live

### Other income streams to explore:
1. Grid trading on DEXes
2. Arbitrage between DEXes  
3. MEV (sandwich attacks)
4. SOL staking auto-compound

## Sim Stats
- Starting: 1.0 SOL
- Costs: 2% slippage + 3% tax = 5% per trade
- Rules: TP1 +50% | TP2 +100% | SL -30%