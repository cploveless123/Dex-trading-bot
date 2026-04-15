#!/usr/bin/env python3
"""Fix pump path cooldown expiry - use cached data if fresh fetch fails"""

with open('/root/Dex-trading-bot/gmgn_scanner.py', 'r') as f:
    content = f.read()

# The problematic block to replace
old_block = '''            if remaining <= 0:
            # Timer expired - get fresh data for buy check
            if cooldown_remaining > 15:
                # Timer not close - skip fresh fetch, use cached data
                chg5 = result.get('chg5', 0)
                h1 = result.get('h1', 0)
                chg1 = result.get('chg1', 0)
                mcap = result.get('mcap', 0)
                fresh_data = None
                source = None
            else:
                # Timer about to expire - get fresh data
                fresh_data, source = get_fresh_token_data(addr)
                if fresh_data is None:
                    # Failed to get fresh data - skip this cycle, don't remove
                    print(f"   [EXPIRED] {result['token']}: fresh data fetch failed - removing")
                    to_remove.append(addr)
                    continue
                
                # Extract data from source
                if source == 'gmgn':
                    chg5 = float(fresh_data.get('price_change_percent5m', 0) or 0)
                    h1 = float(fresh_data.get('price_change_percent1h', 0) or 0)
                    chg1 = float(fresh_data.get('price_change_percent1m', 0) or 0)
                    mcap = float(fresh_data.get('market_cap', 0) or 0)
                else:
                    pc = fresh_data.get('priceChange', {})
                    chg5 = float(pc.get('m5', 0) or 0)
                    h1 = float(pc.get('h1', 0) or 0)
                    chg1 = float(pc.get('m1', 0) or 0)
                    mcap = float(fresh_data.get('marketCap', 0) or 0)
                
                result['chg5'] = chg5
                result['h1'] = h1
                result['chg1'] = chg1
                result['mcap'] = mcap'''

new_block = '''            if remaining <= 0:
            # Timer expired - check buy condition using cached OR fresh chg1
            if cooldown_remaining > 15:
                # Timer not close - use cached data
                chg5 = result.get('chg5', 0)
                h1 = result.get('h1', 0)
                chg1 = result.get('chg1', 0)
                mcap = result.get('mcap', 0)
                fresh_data = None
                source = 'cached'
            else:
                # Timer about to expire (<=15s) - try fresh data
                fresh_data, source = get_fresh_token_data(addr)
                if fresh_data is None:
                    # Failed fresh fetch - use CACHED chg1_prev BEFORE expiring
                    chg1_check = chg1_prev
                    chg5_check = chg5
                    mcap_check = mcap
                    source = 'cached'
                else:
                    # Got fresh data
                    if source == 'gmgn':
                        chg5 = float(fresh_data.get('price_change_percent5m', 0) or 0)
                        h1 = float(fresh_data.get('price_change_percent1h', 0) or 0)
                        chg1 = float(fresh_data.get('price_change_percent1m', 0) or 0)
                        mcap = float(fresh_data.get('market_cap', 0) or 0)
                    else:
                        pc = fresh_data.get('priceChange', {})
                        chg5 = float(pc.get('m5', 0) or 0)
                        h1 = float(pc.get('h1', 0) or 0)
                        chg1 = float(pc.get('m1', 0) or 0)
                        mcap = float(fresh_data.get('marketCap', 0) or 0)
                    result['chg5'] = chg5
                    result['h1'] = h1
                    result['chg1'] = chg1
                    result['mcap'] = mcap
                    chg1_check = chg1
                    chg5_check = chg5
                    mcap_check = mcap'''

if old_block in content:
    content = content.replace(old_block, new_block)
    with open('/root/Dex-trading-bot/gmgn_scanner.py', 'w') as f:
        f.write(content)
    print("Block replaced successfully")
else:
    print("Could not find exact block match")
    # Try partial match
    if "EXPIRED" in content and "fresh data fetch failed" in content:
        print("Found partial match - EXPIRED pattern exists")
    else:
        print("Block not found at all")