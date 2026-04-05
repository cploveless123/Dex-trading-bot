#!/usr/bin/env python3
"""
DexScreener Integration
Monitors Solana DEX pairs and provides advanced analytics
"""
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List

import aiohttp


class DexScreenerMonitor:
    def __init__(self, min_liquidity=10000, min_mcap=30000):
        self.min_liquidity = min_liquidity
        self.min_mcap = min_mcap
        self.base_url = "https://api.dexscreener.com/latest/dex"
        self.token_cache = {}
        self.signals_dir = Path(__file__).parent.parent / "signals"
        
    async def get_token_pairs(self, token_address: str) -> List[dict]:
        """Get all DEX pairs for a token"""
        url = f"{self.base_url}/tokens/{token_address}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get('pairs', []) or []
        return []
    
    async def get_pair(self, pair_address: str) -> Optional[dict]:
        """Get specific pair data"""
        url = f"{self.base_url}/pairs/solana/{pair_address}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get('pair')
        return None
    
    async def get_recent_pairs(self, chain="solana", limit=50) -> List[dict]:
        """Get recent pairs on a chain"""
        url = f"{self.base_url}/{chain}?limit={limit}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get('pairs', []) or []
        return []
    
    def analyze_pair(self, pair: dict) -> dict:
        """Analyze a pair and generate signals"""
        liquidity = pair.get('liquidity', {}).get('usd', 0)
        mcap = pair.get('marketCap', 0)
        volume_24h = pair.get('volume', {}).get('h24', 0)
        price_change = pair.get('priceChange', {}).get('h24', 0)
        
        # Buys/sells ratio
        txns = pair.get('txns', {}).get('h24', {})
        buys = txns.get('buys', 0)
        sells = txns.get('sells', 0)
        buy_sell_ratio = buys / max(sells, 1)
        
        analysis = {
            'pair_address': pair.get('pairAddress'),
            'token_address': pair.get('baseToken', {}).get('address'),
            'symbol': pair.get('baseToken', {}).get('symbol'),
            'price': pair.get('priceUsd'),
            'liquidity': liquidity,
            'mcap': mcap,
            'volume_24h': volume_24h,
            'price_change_24h': price_change,
            'buys_24h': buys,
            'sells_24h': sells,
            'buy_sell_ratio': buy_sell_ratio,
            'dex': pair.get('dexId'),
            'analyzed_at': datetime.utcnow().isoformat()
        }
        
        # Generate signal based on criteria
        signals = []
        
        if liquidity > 50000 and volume_24h > 100000 and price_change > 20:
            signals.append('HIGH_VOLUME_PUMP')
            
        if liquidity > 20000 and buy_sell_ratio > 3:
            signals.append('STRONG_BUY_PRESSURE')
            
        if liquidity > 10000 and price_change > 50:
            signals.append('RAPID_MOVE')
            
        if buys > 100 and buy_sell_ratio > 2:
            signals.append('BUY_MOMENTUM')
            
        analysis['signals'] = signals
        
        return analysis
    
    async def check_token(self, token_address: str) -> Optional[dict]:
        """Check a specific token and return analysis"""
        pairs = await self.get_token_pairs(token_address)
        
        if not pairs:
            return None
            
        # Use the pair with most liquidity
        best_pair = max(pairs, key=lambda p: p.get('liquidity', {}).get('usd', 0))
        
        return self.analyze_pair(best_pair)
    
    async def scan_for_opportunities(self) -> List[dict]:
        """Scan for trading opportunities"""
        print(f"[{datetime.now().isoformat()}] Scanning DexScreener...")
        
        recent = await self.get_recent_pairs(limit=100)
        opportunities = []
        
        for pair in recent:
            analysis = self.analyze_pair(pair)
            
            # Filter by basic criteria
            if analysis['liquidity'] < self.min_liquidity:
                continue
            if analysis['mcap'] < self.min_mcap:
                continue
                
            # If has signals, it's an opportunity
            if analysis['signals']:
                opportunities.append(analysis)
                
        return opportunities
    
    def save_signal(self, signal: dict):
        """Save signal to file"""
        token = signal.get('symbol', 'unknown')
        filename = self.signals_dir / f"dexscreener_{token}_{int(time.time())}.json"
        
        with open(filename, 'w') as f:
            json.dump(signal, f, indent=2)
        
        print(f"📊 DexScreener signal: {signal.get('symbol')} - {signal.get('signals', [])}")


async def main():
    monitor = DexScreenerMonitor(min_liquidity=10000, min_mcap=30000)
    
    # Test: scan for opportunities
    print("🔍 Scanning for opportunities...")
    opportunities = await monitor.scan_for_opportunities()
    
    print(f"\nFound {len(opportunities)} opportunities:")
    for opp in opportunities[:10]:
        print(f"  {opp['symbol']}: {opp['signals']} | ${opp['price']} | Vol: ${opp['volume_24h']:,.0f}")


if __name__ == "__main__":
    asyncio.run(main())