#!/usr/bin/env python3
"""
GMGN Signal Scorer
Scores signals 0-100 based on fundamentals and momentum
"""
import json
from pathlib import Path
from datetime import datetime, timedelta

TRADES_FILE = Path("/root/Dex-trading-bot/trades/sim_trades.jsonl")
SIGNALS_DIR = Path("/root/Dex-trading-bot/signals")

# Scoring weights
SCORING = {
    # Liquidity (higher = better) - 25 pts max
    'liq_5k': 10,
    'liq_15k': 15,
    'liq_30k': 20,
    'liq_50k': 25,
    
    # Holders (more decentralized = better) - 20 pts max
    'holders_20': 8,
    'holders_50': 14,
    'holders_100': 18,
    'holders_200': 20,
    
    # Holder concentration (lower = better) - 15 pts max
    'top10_under_20': 15,   # very decentralized
    'top10_under_35': 10,
    'top10_under_50': 5,
    'top10_over_50': 0,     # risky centralized
    
    # LP burnt (yes = safer) - 10 pts
    'lp_burnt_yes': 10,
    'lp_burnt_no': 0,
    
    # No mint / no blacklist (safety) - 10 pts
    'no_mint_yes': 5,
    'no_blacklist_yes': 5,
    
    # Age (not too new, not too old) - 10 pts
    'age_5_30min': 10,    # sweet spot
    'age_30_60min': 8,
    'age_1_3hr': 6,
    'age_3_6hr': 4,
    'age_6hr_plus': 2,
    
    # Volume/Volatility - 10 pts
    'vol_ratio_high': 10,   # volume >> mcap = strong interest
    'vol_ratio_mid': 6,
    'vol_ratio_low': 2,
}

# Action multipliers
ACTION_MULT = {
    'KOL_BUY': 1.5,     # Strongest signal - influencer backed
    'KOTH': 1.3,         # King of the hill - validated
    'PUMP': 1.0,         # Standard pump signal
    'NEW_POOL': 1.1,     # New launch
    'SNIPER': 1.2,       # Active sniper
}

def score_signal(sig: dict) -> dict:
    """Score a GMGN signal dict, return score + breakdown"""
    score = 0
    breakdown = {}
    
    liq = sig.get('liquidity', 0)
    holders = sig.get('holders', 0)
    top10 = sig.get('top_10_pct', 0)
    lp_burnt = sig.get('lp_burnt', False)
    no_mint = sig.get('no_mint', False)
    no_blacklist = sig.get('no_blacklist', False)
    age_min = sig.get('age_minutes', 0)
    vol = sig.get('vol', 0)
    mcap = sig.get('mcap', 0)
    action = sig.get('action', 'PUMP')
    
    # Liquidity score
    if liq >= 50000: score += 25; breakdown['liq'] = '25 (50K+)'
    elif liq >= 30000: score += 20; breakdown['liq'] = '20 (30K+)'
    elif liq >= 15000: score += 15; breakdown['liq'] = '15 (15K+)'
    elif liq >= 5000: score += 10; breakdown['liq'] = '10 (5K+)'
    else: breakdown['liq'] = '0 (too low)'
    
    # Holders score
    if holders >= 200: score += 20; breakdown['holders'] = '20 (200+)'
    elif holders >= 100: score += 18; breakdown['holders'] = '18 (100+)'
    elif holders >= 50: score += 14; breakdown['holders'] = '14 (50+)'
    elif holders >= 20: score += 8; breakdown['holders'] = '8 (20+)'
    else: breakdown['holders'] = '0 (too few)'
    
    # Top 10 concentration
    if top10 < 20: score += 15; breakdown['top10'] = '15 (<20%)'
    elif top10 < 35: score += 10; breakdown['top10'] = '10 (<35%)'
    elif top10 < 50: score += 5; breakdown['top10'] = '5 (<50%)'
    else: breakdown['top10'] = '0 (>50%)'
    
    # LP burnt
    if lp_burnt: score += 10; breakdown['lp'] = '10 (burnt)'
    else: breakdown['lp'] = '0 (not burnt)'
    
    # Safety flags
    if no_mint: score += 5; breakdown['safety'] = '5 (no mint)'
    if no_blacklist: score += 5; breakdown['safety'] = f"{breakdown.get('safety','')}+5 (no blacklist)"
    
    # Age score
    if 5 <= age_min <= 30: score += 10; breakdown['age'] = '10 (5-30min)'
    elif 30 < age_min <= 60: score += 8; breakdown['age'] = '8 (30-60min)'
    elif 60 < age_min <= 180: score += 6; breakdown['age'] = '6 (1-3hr)'
    elif 180 < age_min <= 360: score += 4; breakdown['age'] = '4 (3-6hr)'
    elif age_min > 360: score += 2; breakdown['age'] = '2 (>6hr)'
    else: breakdown['age'] = '0 (<5min)'
    
    # Volume ratio (vol/mcap - high means lots of trading activity)
    if mcap > 0 and vol / mcap > 0.5: score += 10; breakdown['vol'] = '10 (high vol/mcap)'
    elif mcap > 0 and vol / mcap > 0.2: score += 6; breakdown['vol'] = '6 (mid vol/mcap)'
    elif mcap > 0 and vol / mcap > 0.05: score += 2; breakdown['vol'] = '2 (low vol/mcap)'
    else: breakdown['vol'] = '0'
    
    # Action multiplier
    mult = ACTION_MULT.get(action, 1.0)
    final_score = round(score * mult)
    
    return {
        'score': final_score,
        'base_score': score,
        'multiplier': mult,
        'action': action,
        'breakdown': breakdown,
        'symbol': sig.get('symbol', '?'),
        'liquidity': liq,
        'holders': holders,
        'top_10_pct': top10,
        'lp_burnt': lp_burnt,
        'age_min': age_min,
        'vol': vol,
        'mcap': mcap,
        'ca': sig.get('ca', ''),
    }

def get_top_signals(n=5, min_score=50):
    """Get top N signals from the signals directory"""
    files = sorted(SIGNALS_DIR.glob('gmgn_*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
    scored = []
    
    for f in files[:100]:  # Check last 100
        try:
            d = json.load(open(f))
            result = score_signal(d)
            if result['score'] >= min_score:
                scored.append(result)
        except:
            pass
    
    scored.sort(key=lambda x: x['score'], reverse=True)
    return scored[:n]

def format_signal(s: dict) -> str:
    """Format a scored signal for display"""
    b = s['breakdown']
    lines = [
        f"🏆 {s['symbol']} | Score: {s['score']}/100 | {s['action']}",
        f"   Mcap: ${s['mcap']:,.0f} | Liq: ${s['liquidity']:,.0f} | Holders: {s['holders']}",
        f"   Top10: {s['top_10_pct']}% | Age: {s['age_min']}min | Vol: ${s['vol']:,.0f}",
        f"   Score breakdown: liq={b.get('liq','0')} | holders={b.get('holders','0')} | top10={b.get('top10','0')} | lp={b.get('lp','0')} | safety={b.get('safety','')} | age={b.get('age','0')} | vol={b.get('vol','0')}",
    ]
    return '\n'.join(lines)

if __name__ == '__main__':
    print("=== TOP GMGN SIGNALS ===\n")
    top = get_top_signals(n=10, min_score=40)
    for s in top:
        print(format_signal(s))
        print()
