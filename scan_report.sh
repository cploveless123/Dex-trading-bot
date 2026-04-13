#!/bin/bash
cd /root/Dex-trading-bot

echo "=== SCAN REPORT $(date '+%H:%M UTC') ==="

python3 << 'EOF'
import requests
import json
import subprocess

# Use DexScreener as primary source
try:
    resp = requests.get("https://api.dexscreener.com/token-profiles/latest/v1", 
                        headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
    tokens = resp.json()[:30]
    
    print(f"\n📊 Scanned {len(tokens)} tokens")
    print("-" * 60)
    
    passed = []
    rejected = []
    
    for tok in tokens:
        addr = tok.get('tokenAddress', '')
        if not addr:
            continue
        
        try:
            # Get detailed data from DexScreener
            r = requests.get(f'https://api.dexscreener.com/latest/dex/tokens/{addr}', timeout=5)
            if r.status_code != 200:
                continue
            data = r.json()
            pairs = data.get('pairs', [])
            if not pairs:
                continue
            
            p = max(pairs, key=lambda x: x.get('liquidity', {}).get('usd', 0))
            m = float(p.get('fdv', 0) or p.get('marketCap', 0) or 0)
            mc = float(p.get('marketCap', 0) or 0)
            v5 = float(p.get('volume', {}).get('m5', 0) or 0)
            chg5 = float(p.get('priceChange', {}).get('m5', 0) or 0)
            chg60 = float(p.get('priceChange', {}).get('h1', 0) or 0)
            h24 = float(p.get('priceChange', {}).get('h24', 0) or 0)
            liq = float(p.get('liquidity', {}).get('usd', 0) or 0)
            
            # Get holder info from GMGN
            h1_for_gmgn = chg60
            m5_for_gmgn = chg5
            
            # Quick filters (same as scanner)
            reasons = []
            if mc < 4000 or mc > 75000:
                reasons.append(f"mcap ${mc:,.0f}")
            if chg5 < 0:
                reasons.append(f"chg5 {chg5:+.1f}% <0")
            if chg5 > 200:
                reasons.append(f"chg5 {chg5:+.1f}% >200%")
            if chg60 > 500:
                reasons.append(f"h1 {chg60:+.1f}% >500%")
            
            name = tok.get('name', p.get('baseToken', {}).get('name', '?'))
            symbol = tok.get('symbol', p.get('baseToken', {}).get('symbol', '?')[:6])
            
            if reasons:
                rejected.append(f"❌ {name} [{symbol}] | {', '.join(reasons)}")
            else:
                passed.append(f"✅ {name} [{symbol}] | Mcap ${mc:,.0f} | h1 {chg60:+.1f}% | 5m {chg5:+.1f}%")
            
        except Exception as e:
            continue
    
    print("\n📋 PASSED FILTERS:")
    if passed:
        for p in passed[:10]:
            print(f"  {p}")
        if len(passed) > 10:
            print(f"  ... and {len(passed) - 10} more")
    else:
        print("  (none)")
    
    print(f"\n📋 REJECTED (sample):")
    if rejected:
        for r in rejected[:10]:
            print(f"  {r}")
        if len(rejected) > 10:
            print(f"  ... and {len(rejected) - 10} more")
    else:
        print("  (none)")
    
    print(f"\n📊 Summary: {len(passed)} passed, {len(rejected)} rejected out of {len(tokens)} scanned")

except Exception as e:
    print(f"Error: {e}")

print("\n✅ Report complete")
EOF