#!/usr/bin/env python3
"""
Combined Trading Monitor
Runs DexScreener scanning (no Telegram needed)
"""
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import aiohttp
from dotenv import load_dotenv

# Load environment
load_dotenv(Path(__file__).parent.parent / ".env")

TRADES_DIR = Path(__file__).parent.parent / "trades"
SIGNALS_DIR = Path(__file__).parent.parent / "signals"
TRADES_FILE = TRADES_DIR / "trades.jsonl"
JOURNAL_FILE = TRADES_DIR / "learning_journal.jsonl"


class TradingMonitor:
    def __init__(self, scan_interval=90):
        self.scan_interval = scan_interval
        self.positions = []
        self.reserve = 1.0  # SOL
        self.running = False
        self.seen_tokens = set()
        
    async def get_token_price(self, token_address: str) -> dict:
        """Get price data for a token"""
        url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
        
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(15), headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    pairs = data.get('pairs', [])
                    if pairs:
                        # Return best pair (highest liquidity)
                        return max(pairs, key=lambda p: p.get('liquidity', {}).get('usd', 0))
        return None
    
    def analyze_token(self, token_data: dict) -> dict:
        """Analyze token and generate signals"""
        if not token_data:
            return None
            
        liquidity = token_data.get('liquidity', {}).get('usd', 0)
        mcap = token_data.get('marketCap', 0)
        volume_24h = token_data.get('volume', {}).get('h24', 0)
        price_change = token_data.get('priceChange', {}).get('h24', 0)
        
        txns = token_data.get('txns', {}).get('h24', {})
        buys = txns.get('buys', 0)
        sells = txns.get('sells', 1)
        
        buy_sell_ratio = buys / sells if sells > 0 else 0
        
        analysis = {
            'pair_address': token_data.get('pairAddress'),
            'token_address': token_data.get('baseToken', {}).get('address'),
            'symbol': token_data.get('baseToken', {}).get('symbol'),
            'name': token_data.get('baseToken', {}).get('name'),
            'price': token_data.get('priceUsd'),
            'liquidity': liquidity,
            'mcap': mcap,
            'volume_24h': volume_24h,
            'price_change_24h': price_change,
            'buys_24h': buys,
            'sells_24h': sells,
            'buy_sell_ratio': buy_sell_ratio,
            'dex': token_data.get('dexId'),
            'analyzed_at': datetime.utcnow().isoformat()
        }
        
        # Generate signals based on criteria
        signals = []
        
        if liquidity > 50000 and volume_24h > 100000 and price_change > 20:
            signals.append('HIGH_VOLUME_PUMP')
            
        if liquidity > 20000 and buy_sell_ratio > 3:
            signals.append('STRONG_BUY_PRESSURE')
            
        if liquidity > 10000 and price_change > 50:
            signals.append('RAPID_MOVE')
            
        if buys > 50 and buy_sell_ratio > 2:
            signals.append('BUY_MOMENTUM')
            
        analysis['signals'] = signals
        return analysis
    
    def format_dex_signal(self, signal: dict) -> str:
        """Format DexScreener signal in GMGN style"""
        symbol = signal.get('symbol', signal.get('name', 'UNKNOWN'))
        token_addr = signal.get('token_address', '')
        price_change = signal.get('price_change_24h', 0)
        liquidity = signal.get('liquidity', 0)
        mcap = signal.get('mcap', 0)
        volume = signal.get('volume_24h', 0)
        age = signal.get('age_minutes', 0)
        signals = signal.get('signals', [])
        
        # Format liquidity
        if liquidity >= 1000000:
            liq_str = f"${liquidity/1000000:.1f}M"
        elif liquidity >= 1000:
            liq_str = f"${liquidity/1000:.1f}K"
        else:
            liq_str = f"${liquidity:.0f}"
        
        # Format mcap
        if mcap >= 1000000:
            mcap_str = f"${mcap/1000000:.2f}M"
        elif mcap >= 1000:
            mcap_str = f"${mcap/1000:.1f}K"
        else:
            mcap_str = f"${mcap:.0f}"
        
        # Format volume
        if volume >= 1000000:
            vol_str = f"${volume/1000000:.1f}M"
        elif volume >= 1000:
            vol_str = f"${volume/1000:.1f}K"
        else:
            vol_str = f"${volume:.0f}"
        
        # Format price change
        price_str = f"+{price_change:.1f}%" if price_change >= 0 else f"{price_change:.1f}%"
        
        # Signal type
        signal_types = []
        for s in signals:
            if 'HIGH_VOLUME' in s:
                signal_types.append('HIGHVOL')
            if 'BUY_PRESSURE' in s:
                signal_types.append('BUYPRESSURE')
            if 'RAPID' in s:
                signal_types.append('PRICE+' + price_str)
            if 'BUY_MOMENTUM' in s:
                signal_types.append('BUYMOMENTUM')
        
        signal_text = ', '.join(signal_types) if signal_types else 'SIGNAL'
        
        # Dex link
        dex_link = f"https://dexscreener.com/solana/{token_addr}" if token_addr else ""
        
        output = f"""🏐 DEX ALERT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 {symbol}
🔗 CA: {token_addr}
📊 Signal: {signal_text}

💎 FDV: {mcap_str}
💧 Liquidity: {liq_str}
📈 Vol 24h: {vol_str}
📉 Price 24h: {price_str}
⏱️ Age: {age:.0f} min
🔗 {dex_link}

⚙️ Reply GO to execute (manually on GMGN)
⚙️ Or: /buy {token_addr} 0.1 on GMGN bot"""
        
        return output
    
    async def scan_opportunities(self) -> list:
        """Scan for trading opportunities"""
        # Get recent tokens
        url = "https://api.dexscreener.com/token-profiles/latest/v1"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(15), headers=headers) as resp:
                if resp.status != 200:
                    print(f"Error: {resp.status}")
                    return []
                    
                tokens = await resp.json()
                if not tokens:
                    return []
        
        # Check each token for price data
        opportunities = []
        
        for token in tokens[:20]:  # Check top 20 recent tokens
            token_address = token.get('tokenAddress')
            if not token_address or token_address in self.seen_tokens:
                continue
                
            self.seen_tokens.add(token_address)
            
            token_data = await self.get_token_price(token_address)
            if not token_data:
                continue
                
            analysis = self.analyze_token(token_data)
            
            if analysis and analysis.get('signals'):
                opportunities.append(analysis)
                # Print formatted signal
                formatted = self.format_dex_signal(analysis)
                print(f"\n{formatted}")
        
        return opportunities
    
    def check_positions(self):
        """Check open positions for take profit / stop loss"""
        for pos in self.positions:
            if pos.get('status') != 'open':
                continue
                
            entry_price = pos.get('entry_price', 0)
            current_price = pos.get('current_price', entry_price)
            
            if entry_price > 0:
                pnl_pct = (current_price - entry_price) / entry_price
                
                if pnl_pct >= 1.0 and not pos.get('tp1_hit'):
                    print(f"🎯 TP1 HIT: {pos['symbol']} at +{pnl_pct*100:.1f}%")
                    pos['tp1_hit'] = True
                    
                if pnl_pct <= -0.30:
                    print(f"🛑 SL HIT: {pos['symbol']} at {pnl_pct*100:.1f}%")
                    pos['status'] = 'closed'
                    pos['exit_reason'] = 'stop_loss'
    
    def save_signal(self, signal: dict):
        """Save signal to file and log to learning journal"""
        token = signal.get('symbol', 'unknown')
        filename = SIGNALS_DIR / f"dexs_{token}_{int(datetime.utcnow().timestamp())}.json"
        
        with open(filename, 'w') as f:
            json.dump(signal, f, indent=2)
        
        # Log to learning journal
        entry = {
            "type": "signal",
            "timestamp": datetime.utcnow().isoformat(),
            "data": signal
        }
        JOURNAL_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(JOURNAL_FILE, 'a') as f:
            f.write(json.dumps(entry) + '\n')
        
        print(f"   📝 Logged to learning journal")
    
    async def run(self):
        """Main monitoring loop"""
        self.running = True
        print("🚀 DEX Scanner Started")
        print(f"   Scan interval: {self.scan_interval}s")
        
        iteration = 0
        while self.running:
            iteration += 1
            print(f"\n--- Scan #{iteration} [{datetime.now().isoformat()}] ---")
            
            opportunities = await self.scan_opportunities()
            
            if opportunities:
                print(f"   Found {len(opportunities)} opportunities")
                for opp in opportunities:
                    self.save_signal(opp)
            else:
                print("   No opportunities found")
            
            if self.positions:
                self.check_positions()
                open_count = sum(1 for p in self.positions if p.get('status') == 'open')
                print(f"   {open_count} open positions")
            
            await asyncio.sleep(self.scan_interval)
    
    def stop(self):
        self.running = False


if __name__ == "__main__":
    monitor = TradingMonitor(scan_interval=90)
    asyncio.run(monitor.run())