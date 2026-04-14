#!/usr/bin/env python3
import subprocess, json, time, sys
from pathlib import Path
sys.path.insert(0, '.')
from trading_constants import *

# Load blacklist
BLACKLIST_FILE = Path('/root/Dex-trading-bot/ticker_blacklist.json')
PERM_BLACKLIST = set()
try:
    with open(BLACKLIST_FILE) as f:
        PERM_BLACKLIST = set(json.load(f).keys())
except: pass

# Get gmgn data
r = subprocess.run(['gmgn-cli', 'market', 'trending', '--chain', 'sol', '--interval', '5m', '--limit', '20'],
    capture_output=True, text=True, timeout=15)
rank = json.loads(r.stdout).get('data', {}).get('rank', [])
r2 = subprocess.run(['gmgn-cli', 'market', 'trenches', '--chain', 'sol', '--limit', '30'],
    capture_output=True, text=True, timeout=15)
trenches = json.loads(r2.stdout)
all_tokens = rank + trenches.get('creating', []) + trenches.get('created', []) + trenches.get('completed', [])

# Dedupe
seen = set()
unique = []
for t in all_tokens:
    addr = t.get('address', '')
    if addr and addr not in seen:
        seen.add(addr)
        unique.append(t)

print(f'Total unique tokens: {len(unique)}')

for t in unique:
    sym = t.get('symbol', '')
    if sym not in ['BELKA', 'BLOCKADE', 'Allan']:
        continue
    
    addr = t.get('address', '')
    mcap = float(t.get('market_cap', 0) or 0)
    h1 = float(t.get('price_change_percent1h', 0) or 0)
    h24 = float(t.get('price_change_percent24h', 0) or 0)
    m5 = float(t.get('price_change_percent5m', 0) or 0)
    holders = int(t.get('holder_count', 0) or 0)
    top10 = float(t.get('top_10_holder_rate', 0) or 0) * 100
    liq = float(t.get('liquidity', 0) or 0)
    creation_ts = int(t.get('creation_timestamp', 0) or 0)
    ath = float(t.get('history_highest_market_cap', 0) or 0)
    buys = int(t.get('buys', 0) or 0)
    sells = int(t.get('sells', 0) or 1)
    if sells == 0:
        sells = 1
    bs = buys / sells
    
    age_sec = (time.time() - creation_ts)
    age_min = age_sec / 60
    
    dip = ((ath - mcap) / ath * 100) if ath > 0 else 0
    ath_dist = ((ath - mcap) / ath * 100) if ath > 0 else 0
    
    print(f'\n=== {sym} ({addr[:8]}...) ===')
    print(f'  mcap=${mcap:,.0f}')
    print(f'  age={age_min:.1f}min ({age_sec:.0f}s)')
    print(f'  holders={holders}')
    print(f'  top10={top10:.1f}%')
    print(f'  h1={h1:.1f}%  d24={h24:.1f}%')
    print(f'  dip={dip:.1f}%  ATH_dist={ath_dist:.1f}%')
    print(f'  BS={bs:.2f}  liq=${liq:,.0f}')
    
    checks = []
    if mcap < MIN_MCAP: checks.append(f'FAIL mcap')
    if mcap > MAX_MCAP: checks.append(f'FAIL mcap too high')
    if age_sec < MIN_AGE_SECONDS: checks.append(f'FAIL age too young')
    if age_sec > MAX_AGE_SECONDS: checks.append(f'FAIL age too old ({age_min:.0f}m > {MAX_AGE_SECONDS/60:.0f}m)')
    if holders < MIN_HOLDERS: checks.append(f'FAIL holders')
    if holders == 0 or top10 == 0: checks.append(f'FAIL bot farm')
    if top10 > TOP10_HOLDER_MAX: checks.append(f'FAIL top10 too high')
    if h1 < H1_MOMENTUM_MIN and h24 < H24_MOMENTUM_MIN: checks.append(f'FAIL no momentum')
    if h1 > H1_PARABOLIC_REJECT: checks.append(f'FAIL parabolic h1')
    if dip < DIP_MIN: checks.append(f'FAIL dip too shallow')
    if dip > DIP_MAX: checks.append(f'FAIL dip too deep')
    if ath_dist < ATH_DIVERGENCE_MIN: checks.append(f'FAIL ATH too close')
    if bs < BS_RATIO_OLD and (age_min >= 15): checks.append(f'FAIL BS too low')
    if sym in TICKER_BLACKLIST: checks.append(f'FAIL ticker blacklist')
    if addr in PERM_BLACKLIST: checks.append(f'FAIL perm blacklisted')
    
    if checks:
        for c in checks:
            print(f'  {c}')
    else:
        print(f'  >>> PASSES ALL FILTERS!')
