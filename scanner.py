#!/usr/bin/env python3
"""
DexScreener Scanner - Monitors Solana DEX for token pairs matching criteria
"""
import asyncio
import json
import time
from datetime import datetime
from typing import Optional

import aiohttp


class DexScreenerScanner:
    def __init__(self, min_liquidity=10000, min_mcap=50000):
        self.min_liquidity = min_liquidity
        self.min_mcap = min_mcap
        self.base_url = "https://api.dexscreener.com/latest/dex/tokens"
        self.scanned_pairs = set()
        
    async def scan_token(self, token_address: str) -> Optional[dict]:
        """Scan a specific token address"""
        url = f"{self.base_url}/{token_address}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return self._parse_pair_data(data)
        return None
    
    async def scan_solana_pairs(self, limit=50):
        """Scan recent Solana pairs - requires different endpoint"""
        url = "https://api.dexscreener.com/latest/dex/solana"
        pairs = []
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    pairs = data.get('pairs', [])[:limit]
        return [self._parse_pair_data({'pair': p}) for p in pairs]
    
    def _parse_pair(self, pair_data: dict) -> Optional[dict]:
        """Parse pair data and filter by criteria"""
        try:
            pair = pair_data.get('pair', {})
            liquidity = pair.get('liquidity', {}).get('usd', 0)
            mcap = pair.get('marketCap', 0)
            
            if liquidity < self.min_liquidity or mcap < self.min_mcap:
                return None
                
            return {
                'address': pair.get('pairAddress'),
                'token_address': pair.get('baseToken', {}).get('address'),
                'symbol': pair.get('baseToken', {}).get('symbol'),
                'name': pair.get('baseToken', {}).get('name'),
                'price': pair.get('priceUsd'),
                'liquidity': liquidity,
                'mcap': mcap,
                'change_24h': pair.get('priceChange', {}).get('h24'),
                'volume_24h': pair.get('volume', {}).get('h24'),
                'txns_24h': pair.get('txns', {}).get('h24', {}),
                'dex': pair.get('dexId'),
                'updated': pair.get('pairCreatedAt'),
                'scanned_at': datetime.utcnow().isoformat()
            }
        except Exception as e:
            print(f"Error parsing pair: {e}")
            return None
    
    def save_signal(self, signal: dict):
        """Save signal to signals directory"""
        filename = f"signals/{signal['token_address']}_{int(time.time())}.json"
        with open(filename, 'w') as f:
            json.dump(signal, f, indent=2)
        print(f"📡 Signal saved: {signal['symbol']} - ${signal['price']}")


async def main():
    scanner = DexScreenerScanner(min_liquidity=10000, min_mcap=50000)
    
    while True:
        print(f"\n[{datetime.now().isoformat()}] Scanning...")
        pairs = await scanner.scansolana_pairs(limit=50)
        
        signals_found = 0
        for pair_data in pairs:
            signal = scanner._parse_pair({'pair': pair_data})
            if signal:
                scanner.save_signal(signal)
                signals_found += 1
        
        print(f"Found {signals_found} signals this scan")
        await asyncio.sleep(90)


if __name__ == "__main__":
    asyncio.run(main())