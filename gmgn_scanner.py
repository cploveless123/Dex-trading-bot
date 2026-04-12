#!/usr/bin/env python3
"""
GMGN-Native Scanner v1.0 - Wilson Bot
Uses GMGN trending as primary data source instead of DexScreener
Much faster - all data in ONE call per interval
"""

import requests
import json
import time
import subprocess
from datetime import datetime
from pathlib import Path

# === TRADING CONSTANTS ===
MIN_MCAP = 4000
MAX_MCAP = 75000
DIP_MIN = 15
DIP_MAX = 40
MIN_MOMENTUM = 50  # h1 or 24h must be > +50%
MIN_HOLDERS = 15
MAX_TOP10 = 50
MIN_BS_RATIO = 1.5
MIN_VOLUME_5M = 1000
MAX_AGE_MINUTES = 180
FOCUS_AGE_MINUTES = 15
POSITION_SIZE = 0.1
MAX_OPEN_POSITIONS = 9
STOP_LOSS = 20

# === FILES ===
TRADES_FILE = Path("/root/Dex-trading-bot/trades/sim_trades.jsonl")
WHALE_DB = Path("/root/Dex-trading-bot/whales/whale_db.json")
SIM_RESET_TIMESTAMP = "2026-04-11T20:53:55.000000"
BUY_TIMEOUT = 30

# === STATE ===
_sold_tokens = set()
_peak_prices = {}
_token_first_seen = {}
_buy_prices = {}
_open_positions = {}

def init_sold_tokens():
    """Load all closed positions into permanent blacklist"""
    global _sold_tokens
    if TRADES_FILE.exists():
        with open(TRADES_FILE) as f:
            for line in f:
                try:
                    t = json.loads(line)
                    if t.get('action') == 'BUY' and t.get('closed_at'):
                        _sold_tokens.add(t['token_address'])
                except:
                    pass

def load_whales():
    """Load whale wallets with >= 50% winrate and >= 3 buys"""
    if not WHALE_DB.exists():
        return []
    with open(WHALE_DB) as f:
        d = json.loads(f.read())
    return [w['wallet'] for w in d.get('whales', []) if w.get('winrate', 0) >= 0.5 and w.get('buy_count', 0) >= 3]

def get_gmgn_trending(limit=30):
    """Get trending tokens from GMGN - ALL data in one call"""
    try:
        result = subprocess.run(
            ['gmgn-cli', 'market', 'trending', '--chain', 'sol', '--interval', '5m', '--limit', str(limit)],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get('data', {}).get('rank', [])
        return []
    except Exception as e:
        print(f"GMGN error: {e}")
        return []

def get_pair_age_minutes(creation_ts):
    """Calculate token age from creation timestamp"""
    if not creation_ts:
        return 999
    now_ts = int(time.time())
    return (now_ts - creation_ts) / 60

def calculate_age_dip(token_data):
    """
    Calculate 'dip' from ATH on GMGN data:
    - Use history_highest_market_cap as the peak
    - Dip = (1 - current_mcap / ath_mcap) * 100
    - This is the TRUE dip from the token's actual all-time high
    """
    mc = float(token_data.get('market_cap', 0) or 0)
    ath_mc = float(token_data.get('history_highest_market_cap', 0) or 0)
    
    if ath_mc > 0 and mc < ath_mc:
        # Token has pulled back from ATH
        dip = (1 - mc / ath_mc) * 100
        return max(0, dip)
    elif ath_mc > 0 and mc >= ath_mc:
        # Token is AT or ABOVE ATH - no dip, it's pumping
        return 0.0
    else:
        # No ATH data - use m5/h1 ratio as proxy
        h1 = float(token_data.get('price_change_percent1h', 0) or 0)
        m5 = float(token_data.get('price_change_percent5m', 0) or 0)
        if h1 > 50 and m5 > 0:
            return 5.0  # Young pump, treat as minimal dip
        return 0.0

def scan_gmgn_token(token_data, whales):
    """
    Apply v5.7 filters to a GMGN token
    Returns (result_dict, reason_string) if passes, (None, reason) if fails
    """
    addr = token_data.get('address', '')
    name = token_data.get('name', 'Unknown')
    symbol = token_data.get('symbol', '?')
    
    # Basic fields from GMGN
    mcap = float(token_data.get('market_cap', 0) or 0)
    h1 = float(token_data.get('price_change_percent1h', 0) or 0)
    m5 = float(token_data.get('price_change_percent5m', 0) or 0)
    holders = int(token_data.get('holder_count', 0) or 0)
    top10 = float(token_data.get('top_10_holder_rate', 0) or 0) * 100
    liq = float(token_data.get('liquidity', 0) or 0)
    creation_ts = int(token_data.get('creation_timestamp', 0) or 0)
    age = get_pair_age_minutes(creation_ts)
    burn_status = token_data.get('burn_status', '')
    launchpad = token_data.get('launchpad', '')
    is_honeypot = token_data.get('is_honeypot', 0)
    buys = int(token_data.get('buys', 0) or 0)
    sells = int(token_data.get('sells', 0) or 0)
    volume = float(token_data.get('volume', 0) or 0)
    
    # Calculate BS ratio
    bs = (buys / sells) if sells > 0 else (1.0 if buys > sells else 0.5)
    
    # Calculate estimated dip
    dip = calculate_age_dip(token_data)
    
    # ===== FILTERS =====
    
    # 1. Honeypot check
    if is_honeypot == 1:
        return None, f"Honeypot"
    
    # 2. Exchange check - only Pump.fun or Raydium
    # Indicators: pump.fun address ends in "pump", or exchange contains "pump"/"raydium"
    # Reject meteora, orinoco, or other DEXes
    launchpad_platform = token_data.get('launchpad_platform', '').lower()
    exchange = token_data.get('exchange', '').lower()
    addr_lower = addr.lower()
    
    is_pump = ('pump' in launchpad_platform or 'pump' in exchange or 
                addr.endswith('pump') or 'pump.fun' in launchpad_platform)
    is_raydium = 'raydium' in exchange
    
    # Reject known bad exchanges
    bad_exchanges = ['meteora', 'orcan', 'lifinity', 'saber', 'crema', 'cykura', 'port']
    is_bad = any(bad in exchange for bad in bad_exchanges)
    
    if is_bad or (exchange and not is_pump and not is_raydium):
        return None, f"Exchange: {exchange} ({launchpad_platform}) - not pump.fun/raydium"
    
    # 3. Mcap range
    if mcap < MIN_MCAP:
        return None, f"Mcap ${mcap:,.0f} < ${MIN_MCAP:,}"
    if mcap > MAX_MCAP:
        return None, f"Mcap ${mcap:,.0f} > ${MAX_MCAP:,}"
    
    # 3. Age limit
    if age > MAX_AGE_MINUTES:
        return None, f"Age {age:.1f}min > {MAX_AGE_MINUTES}min"
    
    # 4. Holders
    if holders < MIN_HOLDERS:
        return None, f"Holders {holders} < {MIN_HOLDERS}"
    
    # 5. Top 10% 
    if top10 > MAX_TOP10:
        return None, f"Top10 {top10:.1f}% > {MAX_TOP10}%"
    
    # 6. Momentum (h1 or 24h)
    if h1 < MIN_MOMENTUM:
        return None, f"h1 {h1:+.1f}% < +{MIN_MOMENTUM}%"
    
    # 7. No falling knife (m5 must be positive for momentum)
    if m5 < 0:
        return None, f"m5 {m5:+.1f}% < 0 (falling)"
    
    # 8. Dip filter (15-40%)
    if dip < DIP_MIN:
        # PARABOLIC EXCEPTION: h1 > +150% AND age < 10 min AND m5 > 0
        if h1 >= 150 and age < 10 and m5 > 0:
            dip = 5.0  # Treat as shallow dip
        else:
            return None, f"Dip {dip:.1f}% < {DIP_MIN}%"
    if dip > DIP_MAX:
        return None, f"Dip {dip:.1f}% > {DIP_MAX}%"
    
    # 9. Volume filter (for older tokens)
    if age >= 20 and volume < MIN_VOLUME_5M:
        return None, f"Vol ${volume:,.0f} < ${MIN_VOLUME_5M:,}"
    
    # 10. Liquidity - Chris's rule:
    # mcap > $60K: require > $1,000 liquidity
    # mcap <= $60K: don't check (pump.fun coins still building)
    if mcap > 60000 and liq < 1000:
        return None, f"LiQ ${liq:,.0f} < $1K (mcap ${mcap:,.0f} > $60K)"
    
    # 11. Pump.fun preferred
    lp_burnt = burn_status == 'burn'
    
    return {
        'token': symbol,
        'address': addr,
        'name': name,
        'mcap': mcap,
        'h1': h1,
        'm5': m5,
        'holders': holders,
        'top10': top10,
        'liq': liq,
        'age': age,
        'dip': dip,
        'bs': bs,
        'is_pump': is_pump,
        'lp_burnt': lp_burnt,
        'entry_price': float(token_data.get('price', 0) or 0)
    }, "PASS"

def check_whale_momentum(addr, whales):
    """Check if any tracked whale has momentum in this token"""
    # Simplified - just return True if we have whale data
    # Full implementation would check whale buy history
    return len(whales) > 0

def should_buy(result, whales):
    """Final check before buying"""
    if not result:
        return False, "No result"
    
    addr = result['address']
    
    # Already open?
    if addr in _open_positions:
        return False, "Already open"
    
    # Blacklisted?
    if addr in _sold_tokens:
        return False, "Blacklisted"
    
    # Check open positions limit - count from TRADE FILE (not in-memory)
    open_count = 0
    if TRADES_FILE.exists():
        with open(TRADES_FILE) as f:
            for line in f:
                try:
                    t = json.loads(line)
                    if t.get('action') == 'BUY' and not t.get('closed_at') and t.get('status') in ('open', 'open_partial'):
                        open_count += 1
                except:
                    pass
    
    if open_count >= MAX_OPEN_POSITIONS:
        return False, f"{open_count}/{MAX_OPEN_POSITIONS} positions open"
    
    # Whales check
    if not check_whale_momentum(addr, whales):
        return False, "No whale signal"
    
    return True, "OK"

def buy_token(addr, result):
    """Execute buy - adds to trade file"""
    now = datetime.utcnow().isoformat()
    trade = {
        'action': 'BUY',
        'token_address': addr,
        'token_name': result['token'],
        'entry_price': result['entry_price'],
        'entry_mcap': result['mcap'],
        'opened_at': now,
        'closed_at': None,
        'entry_sol': POSITION_SIZE,
        'status': 'open',
        'tp_status': {
            'tp1_hit': False,
            'tp2_hit': False,
            'tp3_hit': False,
            'tp4_hit': False,
            'peak_price': result['entry_price']
        }
    }
    
    with open(TRADES_FILE, 'a') as f:
        f.write(json.dumps(trade) + '\n')
    
    _open_positions[addr] = trade
    _buy_prices[addr] = result['entry_price']
    _peak_prices[addr] = result['entry_price']
    
    return trade

def main():
    print("🚀 GMGN Scanner v1.0 - Wilson Bot")
    print(f"   Mcap: ${MIN_MCAP:,}-${MAX_MCAP:,} | Dip: {DIP_MIN}-{DIP_MAX}% | Age <{MAX_AGE_MINUTES}min")
    
    init_sold_tokens()
    print(f"   Blacklist: {len(_sold_tokens)} tokens")
    whales = load_whales()
    print(f"   Whales: {len(whales)} loaded")
    print("Starting GMGN scans...\n")
    
    scan_count = 0
    buy_count = 0
    
    while True:
        try:
            tokens = get_gmgn_trending(limit=30)
            scan_count += len(tokens)
            
            passed = 0
            for token_data in tokens:
                addr = token_data.get('address', '')
                if not addr:
                    continue
                
                # Skip blacklisted
                if addr in _sold_tokens:
                    continue
                
                # Skip if already open
                if addr in _open_positions:
                    continue
                
                result, reason = scan_gmgn_token(token_data, whales)
                
                if result:
                    passed += 1
                    should_buy_flag, buy_reason = should_buy(result, whales)
                    
                    bond = " [BURNED]" if result.get('lp_burnt') else ""
                    pump = " [PUMP]" if result.get('is_pump') else ""
                    
                    print(f"✅ {result['token']}{pump}{bond} | Mcap ${result['mcap']:,.0f} | Age {result['age']:.1f}min | Dip {result['dip']:.1f}% | h1 {result['h1']:+.1f}% | 5m {result['m5']:+.1f}%")
                    
                    if should_buy_flag:
                        trade = buy_token(addr, result)
                        buy_count += 1
                        print(f"   🟢 BUY #{buy_count}: {result['token']} @ ${result['mcap']:,.0f}")
                else:
                    # Show rejections for interesting tokens
                    h1 = float(token_data.get('price_change_percent1h', 0) or 0)
                    if h1 > 100:  # Only show rejections for big movers
                        print(f"❌ {token_data.get('symbol','?')} | h1 {h1:+.1f}% | {reason}")
            
            if passed > 0:
                print(f"   [{datetime.now().strftime('%H:%M:%S')}] GMGN scan: {len(tokens)} tokens, {passed} passed filters")
            
            # Show stats
            if buy_count > 0:
                print(f"\n   📊 Buys this session: {buy_count}")
            
        except Exception as e:
            print(f"Error: {e}")
        
        time.sleep(15)  # Scan every 15 seconds

if __name__ == "__main__":
    main()