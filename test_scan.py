#!/usr/bin/env python3
from gmgn_scanner import get_gmgn_trending, scan_token

tokens = get_gmgn_trending(20)
print(f'Fetched {len(tokens)} tokens from GMGN')

candidates = []
for t in tokens:
    mc = t.get('market_cap', 0)
    h1 = t.get('price_change_percent1h', 0)
    chg5 = t.get('price_change_percent5m', 0)
    chg1 = t.get('price_change_percent1m', 0)
    holders = t.get('holder_count', 0)
    symbol = t.get('symbol', '?')
    volume = t.get('volume', 0)
    launchpad = t.get('launchpad', '?')
    
    # Quick filter check
    if mc < 6000 or mc > 55000:
        reason = f'mcap ${mc:,.0f} out of range'
    elif h1 > 350 and mc < 25000:
        reason = f'Fallen Giant h1={h1:.0f}% mcap=${mc:,.0f}'
    elif holders < 15:
        reason = f'holders {holders} < 15'
    elif volume < 10000:
        reason = f'vol ${volume:,.0f} < $10K'
    else:
        result, fail = scan_token(t)
        if result:
            pump = result.get('pump_rule_triggered', False)
            candidates.append({'symbol': symbol, 'mcap': mc, 'chg1': chg1, 'chg5': chg5, 'h1': h1, 'holders': holders, 'volume': volume, 'launchpad': launchpad, 'pump': pump})
        else:
            reason = fail
            print(f'REJECT {symbol}: {reason}')

print(f'\nCandidates found: {len(candidates)}')
for c in candidates[:5]:
    pump_marker = ' [PUMP]' if c['pump'] else ''
    print(f"  {c['symbol']}: mcap=${c['mcap']:,.0f} chg1={c['chg1']:.1f}% chg5={c['chg5']:.1f}% h1={c['h1']:.0f}% holders={c['holders']}{pump_marker}")