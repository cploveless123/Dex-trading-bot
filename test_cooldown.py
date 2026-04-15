#!/usr/bin/env python3
from gmgn_scanner import get_gmgn_trending, scan_token, add_to_cooldown, COOLDOWN_WATCH

tokens = get_gmgn_trending(20)
print(f'Fetched {len(tokens)} from GMGN')

for t in tokens:
    mc = t.get('market_cap', 0)
    h1 = t.get('price_change_percent1h', 0)
    chg1 = t.get('price_change_percent1m', 0)
    holders = t.get('holder_count', 0)
    volume = t.get('volume', 0)
    symbol = t.get('symbol', '?')
    
    if mc < 6000 or mc > 55000:
        continue
    if h1 > 350 and mc < 25000:
        continue
    if holders < 15:
        continue
    if volume < 10000:
        continue
    
    result, fail = scan_token(t)
    if result is None:
        continue
    
    pump = result.get('pump_rule_triggered', False)
    addr = t.get('address', '')
    chg5 = result.get('chg5', 0)
    
    print(f'Adding to cooldown: {symbol} pump={pump} chg1={chg1:.1f}% chg5={chg5:.1f}%')
    add_to_cooldown(addr, t, result, chg5)

print(f'\nCOOLDOWN_WATCH size: {len(COOLDOWN_WATCH)}')

import time
now = time.time()
for addr, data in list(COOLDOWN_WATCH.items())[:5]:
    token = data.get('result', {}).get('token', '?')
    state = data['state']
    remaining = data['cooldown_end'] - now
    print(f'  {token}: state={state}, remaining={remaining:.1f}s')