#!/bin/bash
# Quick scan report - does its own scan rather than reading logs
cd /root/Dex-trading-bot

echo "=== SCAN REPORT $(date '+%H:%M UTC') ==="

# Quick scan of 20 tokens
python3 << 'PYEOF'
import requests
import json
import subprocess
import sys

try:
    # Fetch tokens
    resp = requests.get("https://api.dexscreener.com/token-profiles/latest/v1", 
                        headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
    tokens = resp.json()[:20]
    
    print(f"\n📊 Scanned {len(tokens)} tokens")
    print("-" * 50)
    
    for tok in tokens:
        addr = tok.get('tokenAddress', '')
        if not addr:
            continue
        
        try:
            # Quick DexScreener check
            r = requests.get(f'https://api.dexscreener.com/latest/dex/tokens/{addr}', timeout=5)
            if r.status_code != 200:
                continue
            data = r.json()
            pairs = data.get('pairs', [])
            if not pairs:
                continue
            
            p = max(pairs, key=lambda x: x.get('liquidity', {}).get('usd', 0))
            m = float(p.get('fdv', 0) or p.get('marketCap', 0) or 0)
            v5 = float(p.get('volume', {}).get('m5', 0) or 0)
            v24 = float(p.get('volume', {}).get('h24', 0) or 0)
            chg5 = float(p.get('priceChange', {}).get('m5', 0) or 0)
            chg60 = float(p.get('priceChange', {}).get('h1', 0) or 0)
            h24 = float(p.get('priceChange', {}).get('h24', 0) or 0)
            mc = float(p.get('marketCap', 0) or 0)
            
            # Quick filters
            if mc < 4000 or mc > 75000:
                continue
            if chg5 < 0:
                continue
            if chg60 < 50:
                continue
            
            # Passed quick filters
            print(f"✅ {addr[:12]}... | Mcap ${mc:,.0f} | h1 {chg60:+.1f}% | 5m {chg5:+.1f}%")
            
        except Exception as e:
            continue

except Exception as e:
    print(f"Error: {e}")

print("\n✅ Report complete")
PYEOF