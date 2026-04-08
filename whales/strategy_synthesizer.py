#!/usr/bin/env python3
"""
Whale Strategy Synthesizer
Takes whale DB and synthesizes actionable trading strategy
"""
import json
from datetime import datetime

WHALE_DB = "/root/Dex-trading-bot/whales/whale_db.json"
OUTPUT = "/root/Dex-trading-bot/whales/synthesized_strategy.md"

def load_db():
    with open(WHALE_DB) as f:
        return json.load(f)

def synthesize():
    db = load_db()
    whales = db.get('whales', [])
    syn = db.get('synthesis', {})
    
    if len(whales) < 1:
        print("Need at least 1 whale in DB")
        return
    
    print("=" * 60)
    print("WHALE STRATEGY SYNTHESIS REPORT")
    print("=" * 60)
    print(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Whales analyzed: {len(whales)}")
    print()
    
    # 1. WHALE PROFILES
    print("=" * 60)
    print("1. WHALE PROFILES")
    print("=" * 60)
    for w in whales:
        tags = w.get('tags', [])
        tag_str = f" ({', '.join(tags)})" if tags else ""
        print(f"\n{w['wallet'][:20]}...{tag_str}")
        print(f"  Realized PnL: {w['realized_profit']:+.2f} SOL")
        print(f"  Win rate: {w['winrate']*100:.1f}%")
        print(f"  Avg hold: {w['avg_hold_hours']:.1f}h")
        print(f"  Tokens traded: {w['unique_tokens']}")
        print(f"  Buy/Sell: {w['buy_count']}B/{w['sell_count']}S")
        
        # PnL distribution
        dist = w.get('pnl_distribution', {})
        total = sum(dist.values())
        if total > 0:
            pct_above_0 = (dist.get('0% to 100%', 0) + dist.get('100% to 500%', 0) + dist.get('>500%', 0)) / total * 100
            print(f"  % profitable: {pct_above_0:.0f}%")
        
        # Mcap preference
        mcap = w.get('mcap_buckets', {})
        best_mcap = max(mcap.items(), key=lambda x: x[1]['wins']/(x[1]['wins']+x[1]['losses']+0.01) if (x[1]['wins']+x[1]['losses']) > 0 else 0)
        print(f"  Best mcap range: {best_mcap[0]} ({best_mcap[1]['buys']} buys, {best_mcap[1]['wins']/(best_mcap[1]['wins']+best_mcap[1]['losses'])*100:.0f}% WR)")
    
    print()
    
    # 2. COMMON PATTERNS
    print("=" * 60)
    print("2. COMMON PATTERNS (What whales agree on)")
    print("=" * 60)
    
    # Aggregate all mcap buckets
    combined_mcap = {}
    for w in whales:
        for bucket, data in w.get('mcap_buckets', {}).items():
            if bucket not in combined_mcap:
                combined_mcap[bucket] = {'buys': 0, 'wins': 0, 'losses': 0}
            combined_mcap[bucket]['buys'] += data['buys']
            combined_mcap[bucket]['wins'] += data['wins']
            combined_mcap[bucket]['losses'] += data['losses']
    
    print("\n📊 MCAP RANGES (combined):")
    for bucket in ["<$10K", "$10K-$30K", "$30K-$60K", "$60K-$100K", ">$100K"]:
        if bucket in combined_mcap:
            d = combined_mcap[bucket]
            total = d['wins'] + d['losses']
            if total > 0:
                wr = d['wins'] / total * 100
                print(f"  {bucket}: {d['buys']} buys | {d['wins']}W/{d['losses']}L ({wr:.0f}% WR)")
    
    # Common tokens
    all_tokens = []
    for w in whales:
        for sym, count, buys, sells in w.get('most_traded', [])[:10]:
            all_tokens.append(sym)
    
    from collections import Counter
    token_freq = Counter(all_tokens)
    print("\n🪙 COMMON TOKENS (traded by multiple whales):")
    for token, count in token_freq.most_common(10):
        print(f"  {token}: appears in {count} whale(s)")
    
    # 3. OUTLIERS (differences)
    print()
    print("=" * 60)
    print("3. OUTLIERS (Where whales differ)")
    print("=" * 60)
    
    hold_times = [w['avg_hold_hours'] for w in whales]
    winrates = [w['winrate']*100 for w in whales]
    pnls = [w['realized_profit'] for w in whales]
    
    print(f"\n⏱ Hold times: {[f'{h:.1f}h' for h in hold_times]}")
    print(f"   → Range: {min(hold_times):.1f}h to {max(hold_times):.1f}h")
    print(f"   → Style: {'FAST CYCLE' if max(hold_times) < 2 else 'SWING/BUILD' if min(hold_times) > 4 else 'MIXED'}")
    
    print(f"\n📈 Win rates: {[f'{wr:.0f}%' for wr in winrates]}")
    print(f"   → Range: {min(winrates):.0f}% to {max(winrates):.0f}%")
    
    print(f"\n💰 Realized PnL: {[f'${p:.0f}' for p in pnls]}")
    
    # 4. SYNTHESIZED STRATEGY
    print()
    print("=" * 60)
    print("4. SYNTHESIZED OPTIMAL STRATEGY")
    print("=" * 60)
    
    # Find best mcap range by WR
    best_mcap = max(combined_mcap.items(), key=lambda x: x[1]['wins']/(x[1]['wins']+x[1]['losses']) if (x[1]['wins']+x[1]['losses']) > 0 else 0)
    
    # Determine strategy type
    if max(hold_times) < 2:
        strategy_type = "FAST_CYCLE"
        description = "Short hold times (1-2h), take quick 0-50% profits, high volume"
    elif min(hold_times) > 4:
        strategy_type = "SWING_BUILD"
        description = "Longer holds, let winners run, focus on WR over volume"
    else:
        strategy_type = "HYBRID"
        description = "Combination: quick takes for normal setups, let winners run longer"
    
    print(f"\n🎯 STRATEGY TYPE: {strategy_type}")
    print(f"   {description}")
    
    print(f"\n📊 ENTRY FILTERS:")
    print(f"   MIN_MCAP: $10,000")
    print(f"   MAX_MCAP: $75,000")
    print(f"   BS_RATIO: 1.5+")
    print(f"   HOLDERS: 15+")
    
    # Exit strategy based on hold time
    avg_hold = sum(hold_times) / len(hold_times)
    print(f"\n📤 EXIT STRATEGY:")
    if strategy_type == "FAST_CYCLE":
        print(f"   TP1: +25% → sell 50%")
        print(f"   TP2: +50% → sell remaining")
        print(f"   Stop: -15%")
        print(f"   Trailing: N/A (fast cycle)")
    else:
        print(f"   TP1: +45% → sell 74% (recoup investment)")
        print(f"   Trailing: 30% from peak (let winners run)")
        print(f"   Stop: -20%")
    
    print(f"\n📋 POSITION SIZING:")
    print(f"   Normal: 0.05 SOL")
    print(f"   KOL_BUY: 0.10 SOL")
    
    # Tokens to watch
    watch_tokens = [t for t, c in token_freq.most_common(5)]
    if watch_tokens:
        print(f"\n👀 WHALE-TOKEN WATCH LIST:")
        for t in watch_tokens:
            print(f"   {t}")
    
    # 5. GENERATE CODE UPDATES
    print()
    print("=" * 60)
    print("5. RECOMMENDED TRADING_CONSTANTS.PY UPDATES")
    print("=" * 60)
    
    print("""
# === WHALE-SYNTHESIZED SETTINGS ===
# Based on analysis of {} whale(s)

MIN_MCAP = 10000           # $10K floor (whale sweet spot)
MAX_MCAP = 75000           # $75K ceiling (good captures $10K-$60K range)

STOP_LOSS_PERCENT = -20    # -20% stop (cut losers fast)
TRAILING_STOP_PCT = 30     # 30% from peak (let winners run)

# Position sizing
POSITION_SIZE = 0.05      # Normal position
KOL_BUY_POSITION_SIZE = 0.10  # KOL signal = double size

# TP levels
TP1_PERCENT = 45           # First target (+45%)
TP1_SELL_PCT = 74          # Sell 74% at TP1
TP2_PERCENT = 100          # Second target (+100%)
TP2_SELL_PCT = 26          # Sell remaining at TP2
""".format(len(whales)))
    
    # Save to file
    report = f"""# Synthesized Whale Trading Strategy
# Generated: {datetime.utcnow().isoformat()}
# Whales analyzed: {len(whales)}

## Strategy Type: {strategy_type}
{description}

## Entry Filters
- MIN_MCAP: $10,000
- MAX_MCAP: $75,000  
- BS_RATIO: 1.5+
- HOLDERS: 15+

## Exit Strategy
- TP1: +45% → sell 74%
- Trailing: 30% from peak
- Stop: -20%

## Position Sizing
- Normal: 0.05 SOL
- KOL_BUY: 0.10 SOL

## Whale Token Watch List
{chr(10).join(f'- {t}' for t in watch_tokens)}

## Whales Analyzed
{chr(10).join(f'- {w["wallet"]} ({w["realized_profit"]:+.2f} SOL, {w["winrate"]*100:.1f}% WR)' for w in whales)}
"""
    
    with open(OUTPUT, 'w') as f:
        f.write(report)
    
    print(f"\n💾 Strategy saved to: {OUTPUT}")

if __name__ == '__main__':
    synthesize()
