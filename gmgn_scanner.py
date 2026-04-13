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

# === IMPORT FROM TRADING CONSTANTS ===
from trading_constants import (
    MIN_MCAP, MAX_MCAP, MIN_HOLDERS, TOP10_HOLDER_MAX as MAX_TOP10,
    DIP_MIN, DIP_MAX, MIN_5MIN_VOLUME as MIN_VOLUME_5M,
    MIN_AGE_SECONDS, MAX_AGE_SECONDS, MAX_OPEN_POSITIONS, POSITION_SIZE,
    STOP_LOSS_PERCENT as STOP_LOSS, BS_RATIO_NEW, BS_RATIO_OLD, TP1_PERCENT,
    ALLOWED_EXCHANGES, REJECTED_EXCHANGES, LIQUIDITY_MCAP_THRESHOLD,
    LIQUIDITY_MIN, PARABOLIC_DIP_EXCEPTION, H1_PARABOLIC_REJECT,
    ANTI_MOMENTUM_5M_THRESHOLD, ANTI_MOMENTUM_CHG1_THRESHOLD, FALLING_KNIFE_CONSECUTIVE,
    NEW_PUMP_COOLDOWN, OLD_PUMP_COOLDOWN, NEW_PUMP_5M_THRESHOLD,
    OLD_PUMP_5M_THRESHOLD, MAX_RECHECKS, RECHECK_DELAY, SIM_RESET_TIMESTAMP
)

# Additional hardcoded
FOCUS_AGE_MINUTES = 15
MIN_MOMENTUM = 50  # h1 or 24h must be > +50%

# === FILES ===
TRADES_FILE = Path("/root/Dex-trading-bot/trades/sim_trades.jsonl")
WHALE_DB = Path("/root/Dex-trading-bot/whales/whale_db.json")
SIM_RESET_TIMESTAMP = "2026-04-11T20:53:55.000000"
BUY_TIMEOUT = 30
COOLDOWN_WATCH = {}  # {addr: {"first_seen": ts, "result": result_dict, "cooldown_secs": int}}

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
    
    # Get chg1 and m5 volume from DexScreener
    chg1 = 0.0
    m5_vol = 0.0
    try:
        r = requests.get(f'https://api.dexscreener.com/latest/dex/tokens/{addr}', timeout=5)
        if r.status_code == 200:
            pairs = r.json().get('pairs', [])
            if pairs:
                chg1 = float(pairs[0].get('priceChange', {}).get('m1', 0) or 0)
                m5_vol = float(pairs[0].get('volume', {}).get('m5', 0) or 0)
                
                # Liquidity check: mcap > $60K requires > $1K liquidity
                if mcap > LIQUIDITY_MCAP_THRESHOLD and liq < LIQUIDITY_MIN:
                    return None, f"Mcap ${mcap:,.0f} > $60K but liq ${liq:,.0f} < $1K"
    except:
        pass
    
    # Volume sanity: m5 volume should be > 5% of mcap (organic momentum, not one wallet)
    if mcap > 0 and m5_vol > 0:
        vol_ratio = m5_vol / mcap
        if vol_ratio < 0.05:
            return None, f"m5 vol ${m5_vol:.0f} < 5% of mcap ${mcap:.0f} (suspect pump)"
    
    # REJECT if chg5 > +200% (too parabolic - likely to reverse)
    if m5 > 200:
        return None, f"chg5 {m5:+.1f}% > +200% (too parabolic)"
    
    # ANTI-MOMENTUM: chg5 > +15% AND chg1 < 0% → REJECT (chasing)
    if m5 > ANTI_MOMENTUM_5M_THRESHOLD and chg1 < ANTI_MOMENTUM_CHG1_THRESHOLD:
        return None, f"chg5 {m5:+.1f}% > +{ANTI_MOMENTUM_5M_THRESHOLD}% but chg1 {chg1:+.1f}% < {ANTI_MOMENTUM_CHG1_THRESHOLD}% (momentum chase)"
    
    # REJECT if chg5 > +100% AND holders < 20 (artificial pump with low organic interest)
    if m5 > 100 and holders < 20:
        return None, f"chg5 {m5:+.1f}% > +100% with only {holders} holders (low organic interest)"
    
    # REJECT if GMGN has no history (all fields are 0/None) — too risky, no data
    if mcap == 0 and h1 == 0 and m5 == 0:
        return None, "No GMGN history (mcap=0, h1=0, m5=0) - too risky"
    
    # REJECT if too young (< 3 min) or too old (> 180 min)
    if age < MIN_AGE_SECONDS / 60:
        return None, f"Age {age:.1f}min < 3min (too young)"
    if age > MAX_AGE_SECONDS / 60:
        return None, f"Age {age:.1f}min > 180min (too old)"
    
    # Calculate BS ratio - different thresholds by age
    if age < 10:
        bs_min = BS_RATIO_NEW  # 0.1 for very young pairs
    else:
        bs_min = BS_RATIO_OLD  # 0.8 for older pairs
    
    bs = (buys / sells) if sells > 0 else (1.0 if buys > sells else 0.5)
    
    # Calculate estimated dip
    dip = calculate_age_dip(token_data)
    
    # ===== FILTERS =====
    
    # 1. Honeypot check
    if is_honeypot == 1:
        return None, f"Honeypot"
    
    # 2. Exchange check - only Pump.fun or Raydium
    # Indicators: pump.fun address ends in "pump", or exchange contains "pump"/"raydium"/"pumpswap"
    # Reject meteora, orinoco, or other DEXes
    launchpad_platform = token_data.get('launchpad_platform', '').lower()
    exchange = token_data.get('exchange', '').lower()
    addr_lower = addr.lower()
    
    is_pump = ('pump' in launchpad_platform or 'pump' in exchange or 
                addr.endswith('pump') or 'pump.fun' in launchpad_platform)
    is_raydium = 'raydium' in exchange
    is_pumpswap = 'pumpswap' in exchange
    
    # Reject known bad exchanges
    bad_exchanges = ['meteora', 'orcan', 'lifinity', 'saber', 'crema', 'cykura', 'port']
    is_bad = any(bad in exchange for bad in bad_exchanges)
    
    if is_bad or (exchange and not is_pump and not is_raydium and not is_pumpswap):
        return None, f"Exchange: {exchange} ({launchpad_platform}) - not pump.fun/raydium/pumpswap"
    
    # 3. Mcap range
    if mcap < MIN_MCAP:
        return None, f"Mcap ${mcap:,.0f} < ${MIN_MCAP:,} (too low)"
    if mcap > MAX_MCAP:
        return None, f"Mcap ${mcap:,.0f} > ${MAX_MCAP:,} (too high)"
    
    # 3. Age limit
    if age > int(MAX_AGE_SECONDS / 60):
        return None, f"Age {age:.1f}min > {int(MAX_AGE_SECONDS / 60)}min"
    
    # 4. Holders
    if holders < MIN_HOLDERS:
        return None, f"Holders {holders} < {MIN_HOLDERS}"
    
    # 5. Top 10% 
    if top10 > MAX_TOP10:
        return None, f"Top10 {top10:.1f}% > {MAX_TOP10}% (dumper risk)"
    
    # 6. Momentum (h1 or chg5 as proxy)
    # For very young coins (< 10 min), require h1 > +30% (they're just starting)
    # For older coins, require h1 > +50%
    # If h1 is low but chg5 shows strong momentum AND coin is young, allow it
    # REJECT if h1 > +500% (too parabolic - likely to reverse)
    if h1 > H1_PARABOLIC_REJECT:
        return None, f"h1 {h1:+.1f}% > +{H1_PARABOLIC_REJECT}% (too parabolic)"
    
    min_h1 = 30 if age < 10 else MIN_MOMENTUM
    if h1 >= min_h1:
        pass  # Good momentum
    elif age < 15 and m5 >= min_h1:
        # For young coins: use chg5 as momentum proxy when h1 is low
        pass  # chg5 shows momentum
    else:
        return None, f"h1 {h1:+.1f}% < +{min_h1}% ({'young' if age < 10 else 'normal'})"
    
    # 7. No falling knife (m5 must be positive for momentum)
    if m5 < 0:
        return None, f"m5 {m5:+.1f}% < 0 (falling)"
    
    # 8. Dip filter (15-45%)
    if dip < DIP_MIN:
        # PARABOLIC EXCEPTION: h1 > +100% AND age < 15 min AND chg1 > 0 → allow dip as low as 5%
        if h1 >= 100 and age < 15 and chg1 > 0:
            dip = PARABOLIC_DIP_EXCEPTION  # Treat as 5% dip
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
    
    # Blacklisted? Check BOTH in-memory set AND trade file
    if addr in _sold_tokens:
        return False, "Blacklisted (memory)"
    
    # Also check trade file for permanently closed OR currently open positions
    if TRADES_FILE.exists():
        with open(TRADES_FILE) as f:
            for line in f:
                try:
                    t = json.loads(line)
                    # Reject if ever bought (closed OR still open - either way, don't rebuy)
                    if t.get('token_address') == addr and t.get('action') == 'BUY':
                        return False, "Blacklisted (trade file)"
                except:
                    pass
    
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

def check_cooldown(whales):
    """Check and process cooldown watch list"""
    global COOLDOWN_WATCH
    to_remove = []
    
    for addr, data in COOLDOWN_WATCH.items():
        elapsed = time.time() - data['first_seen']
        result = data['result']
        
        # Check if still passing filters (re-verify)
        result2, reason2 = scan_gmgn_token(data['token_data'], whales)
        
        if result2 is None:
            # No longer passing filters - remove from cooldown
            to_remove.append(addr)
            continue
        
        # Update current mcap and price
        result2['current_mcap'] = result2.get('mcap', 0)
        
        if elapsed >= data['cooldown_secs']:
            # Cooldown passed - get fresh chg1 from DexScreener
            chg1 = 0.0
            try:
                r = requests.get(f'https://api.dexscreener.com/latest/dex/tokens/{addr}', timeout=5)
                if r.status_code == 200:
                    pairs = r.json().get('pairs', [])
                    if pairs:
                        chg1 = float(pairs[0].get('priceChange', {}).get('m1', 0) or 0)
            except:
                pass
            
            # If chg1 < 0%, wait 15s more and recheck
            if chg1 < 0:
                data['cooldown_secs'] += 15
                data['first_seen'] = time.time()  # Reset timer to avoid repeated prints
                print(f"   ⏳ {result['token']}: chg1={chg1:+.1f}% < 0%, waiting 15s more to recheck")
                continue
            
            # chg1 >= 0 - safe to proceed
            should_buy_flag, buy_reason = should_buy(result2, whales)
            if should_buy_flag:
                trade = buy_token(addr, result2)
                if trade:
                    print(f"   🟢 BUY (after {elapsed:.0f}s cooldown): {result2['token']} @ ${result2['mcap']:,.0f}")
                    to_remove.append(addr)
                else:
                    to_remove.append(addr)
            else:
                # Didn't pass should_buy for some reason
                to_remove.append(addr)
        else:
            # Still in cooldown
            remaining = data['cooldown_secs'] - elapsed
            print(f"   ⏳ {result['token']}: {remaining:.0f}s left in cooldown")
    
    for addr in to_remove:
        if addr in COOLDOWN_WATCH:
            del COOLDOWN_WATCH[addr]

def buy_token(addr, result):
    """Execute buy - adds to trade file"""
    # VERIFY via DexScreener before buying - only pump.fun, pumpswap, or raydium
    try:
        r = requests.get(f'https://api.dexscreener.com/latest/dex/tokens/{addr}', timeout=10)
        if r.status_code == 200:
            data = r.json()
            pairs = data.get('pairs', [])
            if pairs:
                p = max(pairs, key=lambda x: x.get('liquidity', {}).get('usd', 0))
                dex = p.get('dexId', '').lower()
                pair_addr = p.get('pairAddress', '').lower()
                
                if dex not in ('pumpfun', 'raydium', 'raydium2', 'pumpswap'):
                    print(f"❌ {result['token']}: DexScreener says {dex} - not buying")
                    return None
                
                # For pump.fun and pumpswap: pair address must end in "pump"
                # For raydium: no such requirement
                if dex in ('pumpfun', 'pumpswap'):
                    if not (pair_addr.endswith('pump') or addr.lower().endswith('pump')):
                        print(f"❌ {result['token']}: {dex} pair doesn't end in 'pump' - not buying")
                        return None
    except Exception as e:
        print(f"⚠️ Could not verify DEX: {e}")
    
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
    print(f"   Mcap: ${MIN_MCAP:,}-${MAX_MCAP:,} | Dip: {DIP_MIN}-{DIP_MAX}% | Age <{int(MAX_AGE_SECONDS / 60)}min (<10min: h1>+30%)")
    
    init_sold_tokens()
    print(f"   Blacklist: {len(_sold_tokens)} tokens")
    whales = load_whales()
    print(f"   Whales: {len(whales)} loaded")
    print("Starting GMGN scans...\n")
    
    scan_count = 0
    buy_count = 0
    
    while True:
        try:
            # Check cooldown watch list first
            check_cooldown(whales)
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
                        # COOLDOWN LOGIC: Add to watch list instead of buying immediately
                        # If GMGN age=0, try to get age from DexScreener
                        age = result['age']
                        if age == 0:
                            # Try DexScreener fallback for age
                            try:
                                r = requests.get(f'https://api.dexscreener.com/latest/dex/tokens/{addr}', timeout=5)
                                if r.status_code == 200:
                                    pairs = r.json().get('pairs', [])
                                    if pairs:
                                        created_ts = int(pairs[0].get('pairCreatedAt', 0) or 0)
                                        if created_ts:
                                            age = (time.time() - created_ts / 1000) / 60
                            except:
                                pass
                        
                        # Calculate cooldown based on chg5 and age
                        cooldown_secs = 0
                        
                        if age < 10 and result['m5'] > 50:
                            cooldown_secs = 120  # Young + parabolic
                        elif age >= 10 and result['m5'] > 1:
                            cooldown_secs = 120  # Older + positive chg5
                        
                        # If chg5 > +100% (very parabolic), add 60s extra
                        if result['m5'] > 100:
                            cooldown_secs += 60
                        
                        # If chg1 (1min change) is negative, add 60s extra cooldown
                        if result.get('chg1', 0) < 0:
                            cooldown_secs += 60
                        
                        if cooldown_secs > 0:
                            if addr not in COOLDOWN_WATCH:
                                COOLDOWN_WATCH[addr] = {
                                    'first_seen': time.time(),
                                    'result': result,
                                    'token_data': token_data,
                                    'cooldown_secs': cooldown_secs
                                }
                                print(f"   ⏳ {result['token']}: Added to cooldown for {cooldown_secs}s (chg5={result['m5']:+.1f}%, age={result['age']:.1f}min)")
                            # else already in cooldown
                        else:
                            # No cooldown needed - buy immediately
                            trade = buy_token(addr, result)
                            if trade:
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