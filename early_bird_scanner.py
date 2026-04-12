#!/usr/bin/env python3
"""
Early Bird Scanner v1.0 - Wilson Bot
Monitors brand new coins (< 2 min old) every 5 seconds
Tracks peak/bottom to find early pumpers
Does NOT execute trades - only alerts
"""

import requests
import json
import time
import subprocess
from datetime import datetime
from pathlib import Path
import pytz

# === SETTINGS ===
MAX_AGE_MINUTES = 2
SCAN_INTERVAL = 5  # seconds
MIN_MCAP = 3000
MAX_MCAP = 12000
TELEGRAM_CHAT_ID = "6402511249"
TELEGRAM_BOT_TOKEN = "8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg"

# Track coins we're monitoring
# {addr: {"symbol": str, "first_seen": ts, "peak_price": float, "bottom_price": float, "entry_count": int}}
monitored_coins = {}

def get_new_coins():
    """Get newest coins from GMGN"""
    try:
        result = subprocess.run(
            ['gmgn-cli', 'market', 'trending', '--chain', 'sol', '--interval', '1m', '--limit', '100'],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get('data', {}).get('rank', [])
        return []
    except:
        return []

def get_token_price(addr):
    """Get current price/mcap from DexScreener"""
    try:
        r = requests.get(f'https://api.dexscreener.com/latest/dex/tokens/{addr}', timeout=5)
        if r.status_code == 200:
            data = r.json()
            pairs = data.get('pairs', [])
            if pairs:
                p = max(pairs, key=lambda x: x.get('liquidity', {}).get('usd', 0))
                return {
                    'price': float(p.get('priceUsd', 0) or 0),
                    'mcap': float(p.get('marketCap', 0) or 0),
                    'liq': float(p.get('liquidity', {}).get('usd', 0) or 0),
                    'vol5': float(p.get('volume', {}).get('m5', 0) or 0),
                    'dex': p.get('dexId', '')
                }
    except:
        pass
    return None

def get_eastern_time():
    return datetime.now(pytz.timezone('US/Eastern')).strftime("%H:%M %Z")

def send_telegram(msg):
    """Send alert to Telegram"""
    try:
        import urllib.request
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({
            'chat_id': TELEGRAM_CHAT_ID,
            'text': msg,
            'parse_mode': 'HTML'
        }).encode()
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=5)
    except:
        pass

def analyze_coin(addr, token_data):
    """Analyze a new coin"""
    now_ts = time.time()
    
    # Get price data
    price_data = get_token_price(addr)
    if not price_data:
        return None
    
    mc = price_data['mcap']
    price = price_data['price']
    
    # Check mcap range
    if mc < MIN_MCAP or mc > MAX_MCAP:
        return None
    
    # Check if pump.fun or pumpswap
    if price_data['dex'] not in ('pumpfun', 'pumpswap'):
        return None
    
    # Initialize or update monitoring
    if addr not in monitored_coins:
        # New coin we're tracking
        symbol = token_data.get('symbol', '?')
        created = int(token_data.get('creation_timestamp', 0))
        age_mins = (now_ts - created) / 60 if created else 999
        
        monitored_coins[addr] = {
            'symbol': symbol,
            'first_seen': now_ts,
            'age_at_discovery': age_mins,
            'peak_price': price,
            'bottom_price': price,
            'current_price': price,
            'peak_mcap': mc,
            'check_count': 0,
            'alerts_sent': []
        }
        
        msg = f"""🆕 NEW COIN DETECTED ({get_eastern_time()})
━━━━━━━━━━━━━━━
💰 {symbol}
📍 Mcap: ${mc:,.0f} | Price: ${price:.10f}
⏱ Age: {age_mins:.1f} min old
💵 Liquidity: ${price_data['liq']:,.0f}
📊 Vol (5m): ${price_data['vol5']:,.0f}

🔗 https://dexscreener.com/solana/{addr}
🥧 https://pump.fun/{addr}

👀 Monitoring every {SCAN_INTERVAL}s for 2 minutes..."""
        send_telegram(msg)
        return monitored_coins[addr]
    else:
        # Update existing coin
        coin = monitored_coins[addr]
        coin['current_price'] = price
        coin['check_count'] += 1
        
        # Update peak
        if price > coin['peak_price']:
            coin['peak_price'] = price
            coin['peak_mcap'] = mc
        
        # Update bottom
        if price < coin['bottom_price']:
            coin['bottom_price'] = price
        
        # Calculate stats
        from_peak = (1 - price / coin['peak_price']) * 100 if coin['peak_price'] > 0 else 0
        from_bottom = (price / coin['bottom_price'] - 1) * 100 if coin['bottom_price'] > 0 else 0
        
        return coin

def check_monitoring():
    """Check all monitored coins"""
    to_remove = []
    
    for addr, coin in monitored_coins.items():
        age_mins = (time.time() - coin['first_seen']) / 60
        
        # Remove coins older than 2 minutes
        if age_mins > 2:
            to_remove.append(addr)
            continue
        
        price_data = get_token_price(addr)
        if not price_data:
            continue
            
        coin['current_price'] = price_data['price']
        current_mcap = price_data['mcap']
        
        # Update peak/bottom
        if price_data['price'] > coin['peak_price']:
            coin['peak_price'] = price_data['price']
            coin['peak_mcap'] = current_mcap
        if price_data['price'] < coin['bottom_price']:
            coin['bottom_price'] = price_data['price']
        
        from_peak = (1 - price_data['price'] / coin['peak_price']) * 100 if coin['peak_price'] > 0 else 0
        from_bottom = (price_data['price'] / coin['bottom_price'] - 1) * 100 if coin['bottom_price'] > 0 else 0
        
        # Send update every 15 seconds
        if coin['check_count'] % 3 == 0 and coin['check_count'] > 0:
            # Check for good entry point (pulled back 20-40% from peak)
            if 20 <= from_peak <= 40 and 'entry' not in coin['alerts_sent']:
                coin['alerts_sent'].append('entry')
                msg = f"""🎯 ENTRY ZONE ({get_eastern_time()})
━━━━━━━━━━━━━━━
💰 {coin['symbol']}
📍 Mcap: ${current_mcap:,.0f}
📉 From peak: {from_peak:.1f}%
📈 From bottom: {from_bottom:+.1f}%

⏱ Monitoring: {age_mins:.0f}s / 2min
💰 Peak so far: ${coin['peak_mcap']:,.0f}
💵 Bottom so far: ${coin['bottom_price']:.10f}

🔗 https://dexscreener.com/solana/{addr}
🥧 https://pump.fun/{addr}"""
                send_telegram(msg)
            
            # Check for momentum (new high)
            elif from_peak < 10 and coin['check_count'] > 3 and 'momentum' not in coin['alerts_sent']:
                coin['alerts_sent'].append('momentum')
                msg = f"""🚀 MOMENTUM BUILDING ({get_eastern_time()})
━━━━━━━━━━━━━━━
💰 {coin['symbol']}
📍 Mcap: ${current_mcap:,.0f}
📈 Still within {from_peak:.1f}% of peak

⏱ Monitoring: {age_mins:.0f}s / 2min
💰 Peak: ${coin['peak_mcap']:,.0f}

🔗 https://dexscreener.com/solana/{addr}"""
                send_telegram(msg)
    
    # Clean up old coins
    for addr in to_remove:
        del monitored_coins[addr]

def main():
    print(f"🆕 Early Bird Scanner v1.0")
    print(f"   Monitoring coins < {MAX_AGE_MINUTES} min old, every {SCAN_INTERVAL}s")
    print(f"   Looking for: ${MIN_MCAP:,}-${MAX_MCAP:,} mcap pump.fun/pumpswap")
    print(f"   Starting at {get_eastern_time()}")
    
    scan_count = 0
    
    while True:
        try:
            tokens = get_new_coins()
            scan_count += 1
            
            for token in tokens:
                addr = token.get('address', '')
                if not addr:
                    continue
                
                # Check if this is a new coin
                created = int(token.get('creation_timestamp', 0))
                if created:
                    age_mins = (time.time() - created) / 60
                    if age_mins <= MAX_AGE_MINUTES:
                        analyze_coin(addr, token)
            
            # Check all monitored coins
            check_monitoring()
            
            if scan_count % 12 == 0:  # Every minute
                print(f"[{get_eastern_time()}] Scanning... | Monitoring: {len(monitored_coins)} coins | Scans: {scan_count}")
            
        except Exception as e:
            print(f"Error: {e}")
        
        time.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    main()