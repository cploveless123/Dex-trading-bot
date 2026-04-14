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
from alert_sender import send_telegram
from trading_constants import (
    MIN_CHG1_FOR_BUY,
    CHG1_DROP_THRESHOLD,
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
    
    # ANTI-MOMENTUM: chg5 >+15% AND chg1 <-3% → REJECT (chasing)
    # If chg1 is None (unavailable), treat as unsafe (negative)
    if m5 > ANTI_MOMENTUM_5M_THRESHOLD:
        chg1_check = chg1 if chg1 is not None else -999
        if chg1_check < ANTI_MOMENTUM_CHG1_THRESHOLD:
            if chg1 is not None:
                return None, f"chg5 {m5:+.1f}% > +{ANTI_MOMENTUM_5M_THRESHOLD}% but chg1 {chg1:+.1f}% < {ANTI_MOMENTUM_CHG1_THRESHOLD}% (momentum chase)"
            else:
                return None, f"chg5 {m5:+.1f}% > +{ANTI_MOMENTUM_5M_THRESHOLD}% but chg1 None (unavailable) (momentum chase)"
    
    # REJECT if chg5 > +100% AND holders < 20 (artificial pump with low organic interest)
    if m5 > 100 and holders < 20:
        return None, f"chg5 {m5:+.1f}% > +100% with only {holders} holders (low organic interest)"
    
    # EXTREME PUMP: chg1 > +50% → REJECT (too parabolic, likely to reverse)
    if chg1 is not None and chg1 > 50:
        return None, f"chg1 {chg1:+.1f}% > +50% (extreme pump)"
    
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
        # PARABOLIC EXCEPTION: h1 >+100% AND chg5 >+25% AND age <15 AND chg1 >0
        # → monitor 30s more, if chg1 >+1% then allow (skip to cooldown check)
        if h1 > 100 and m5 > 25 and age < 15 and chg1 is not None and chg1 > 0:
            # This is a parabolic candidate - mark for extra 30s cooldown monitoring
            # Will be handled in cooldown recheck - need chg1 > +1% to buy
            result['_parabolic_candidate'] = True
            result['_parabolic_chg1_target'] = 1.0  # chg1 must be > +1%
            # Allow this dip for now - cooldown logic will handle final check
            pass
        else:
            return None, f"Dip {dip:.1f}% < {DIP_MIN}%"
    if dip > DIP_MAX:
        return None, f"Dip {dip:.1f}% > {DIP_MAX}%"
    
    # 8b. ATH distance check - must be > 30% below ATH
    ath_mc = float(token_data.get('history_highest_market_cap', 0) or 0)
    if ath_mc > 0 and mcap < ath_mc:
        ath_distance = ((ath_mc - mcap) / ath_mc) * 100
        if ath_distance < 30:
            return None, f"ATH distance {ath_distance:.1f}% (need >30% below ATH)"
    
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
        
        # Preserve parabolic candidate flag
        if result.get('_parabolic_candidate'):
            result2['_parabolic_candidate'] = True
        
        if elapsed >= data['cooldown_secs']:
            # Cooldown passed - now in recheck phase
            # OPTION A+C: Get FRESH GMGN data on recheck (not stale cache)
            fresh_token_data = None
            try:
                result_gmgn = subprocess.run(
                    ['gmgn-cli', 'token', 'info', '--chain', 'sol', '--address', addr],
                    capture_output=True, text=True, timeout=15
                )
                if result_gmgn.returncode == 0:
                    fresh_token_data = json.loads(result_gmgn.stdout)
            except:
                pass
            
            if fresh_token_data:
                # Re-run scan with fresh GMGN data
                result2, reason2 = scan_gmgn_token(fresh_token_data, whales)
            else:
                # Fall back to cached data
                result2, reason2 = scan_gmgn_token(data['token_data'], whales)
            
            # OPTION B: Check if key metrics jumped >2x from previous check (unstable - reject)
            prev_h1 = data.get('prev_h1')
            prev_m5 = data.get('prev_m5')
            if prev_h1 is not None and result2:
                curr_h1 = result2.get('h1_change', 0)
                curr_m5 = result2.get('m5_change', 0)
                if prev_h1 and curr_h1:
                    h1_ratio = max(curr_h1, prev_h1) / max(min(curr_h1, prev_h1), 0.001)
                    if h1_ratio > 3:  # More than 3x jump = very unstable
                        print(f"   ❌ {result['token']}: h1 jumped {prev_h1:.1f}% → {curr_h1:.1f}% ({h1_ratio:.1f}x) - too unstable, rejecting")
                        to_remove.append(addr)
                        continue
                data['prev_h1'] = curr_h1
                data['prev_m5'] = curr_m5
            elif result2:
                data['prev_h1'] = result2.get('h1_change', 0)
                data['prev_m5'] = result2.get('m5_change', 0)
            
            if result2 is None:
                # No longer passing filters - remove from cooldown
                to_remove.append(addr)
                continue
            
            # Get fresh chg1 from DexScreener
            chg1 = None
            try:
                r = requests.get(f'https://api.dexscreener.com/latest/dex/tokens/{addr}', timeout=5)
                if r.status_code == 200:
                    pairs = r.json().get('pairs', [])
                    if pairs:
                        chg1_raw = pairs[0].get('priceChange', {}).get('m1')
                        if chg1_raw is not None:
                            chg1 = float(chg1_raw)
            except:
                pass
            
            # Update peak mcap if current is higher
            needs_peak_tracking = data.get('needs_peak_tracking', False)
            current_mcap_recheck = result2.get('current_mcap', 0)
            peak_mcap = data.get('peak_mcap', 0)
            if needs_peak_tracking and current_mcap_recheck > peak_mcap:
                peak_mcap = current_mcap_recheck
                data['peak_mcap'] = peak_mcap
            
            # Initialize previous chg1 for improvement tracking
            prev_chg1 = data.get('prev_chg1')
            
            # Check if this is a parabolic candidate
            is_parabolic = data.get('parabolic_candidate', False)
            
            # For parabolic candidates: check if chg1 > +1%
            if is_parabolic:
                if chg1 is not None and chg1 > 1:
                    # Check dip from peak > 15% AND chg1 > +3%
                    if needs_peak_tracking and peak_mcap > 0:
                        dip_from_peak = ((peak_mcap - current_mcap_recheck) / peak_mcap) * 100
                        if dip_from_peak < 15 or chg1 < 3:
                            # Not enough dip from peak or chg1 not strong enough - continue watching
                            data['cooldown_secs'] += 15
                            data['first_seen'] = time.time()
                            print(f"   ⏳ {result['token']}: dip {dip_from_peak:.1f}% (need >15%) chg1 {chg1:+.1f}% (need >+3%) - waiting 15s more")
                            continue
                    # OPTION 1: Check MIN_CHG1 - chg1 must be > +5% to buy
                    if chg1 is not None and chg1 >= MIN_CHG1_FOR_BUY:
                        # Increment recheck count for consecutive positive checks
                        data['recheck_count'] = data.get('recheck_count', 0) + 1
                        data['prev_chg1'] = chg1
                        
                        # Require 2+ consecutive positive rechecks before buying
                        if data['recheck_count'] < 2:
                            print(f"   ⏳ {result['token']}: recheck #{data['recheck_count']} positive (chg1={chg1:.1f}%), need 1 more - waiting 15s")
                            data['cooldown_secs'] += 15
                            data['first_seen'] = time.time()
                            continue
                        
                        # Consecutive rechecks confirmed - BUY
                        should_buy_flag, buy_reason = should_buy(result2, whales)
                    else:
                        # chg1 not strong enough - continue watching
                        print(f"   ⏳ {result['token']}: parabolic chg1={chg1:+.1f}% (need >={MIN_CHG1_FOR_BUY}%) - waiting 15s more")
                        data['cooldown_secs'] += 15
                        data['first_seen'] = time.time()
                        to_remove.append(addr)
                        continue
                    if should_buy_flag:
                        trade = buy_token(addr, result2)
                        if trade:
                            print(f"   🟢 BUY (parabolic confirmed, chg1={chg1:+.1f}%): {result2['token']} @ ${result2['mcap']:,.0f}")
                            to_remove.append(addr)
                        else:
                            to_remove.append(addr)
                    else:
                        to_remove.append(addr)
                else:
                    # chg1 not > +1% yet - wait 15s more
                    data['cooldown_secs'] += 15
                    data['first_seen'] = time.time()
                    chg1_str = f"{chg1:+.1f}%" if chg1 is not None else "None"
                    print(f"   ⏳ {result['token']}: parabolic candidate chg1={chg1_str}% (need >+1%), waiting 15s")
                    continue
            
            # If chg1 is None or negative, wait and recheck
            if chg1 is None or chg1 < 0:
                data['cooldown_secs'] += 15
                data['first_seen'] = time.time()
                chg1_str = f"{chg1:+.1f}%" if chg1 is not None else "None"
                print(f"   ⏳ {result['token']}: chg1={chg1_str}% (need +2% improvement), waiting 15s")
                data['prev_chg1'] = chg1
                continue
            
            # chg1 >= 0 - check if improved by 2% from previous
            if prev_chg1 is not None and chg1 is not None:
                # OPTION 2: Chg1 deterioration check - if chg1 dropped >50% from previous, reject
                if prev_chg1 > 0 and chg1 < prev_chg1 * 0.5:
                    print(f"   ❌ {result['token']}: chg1 dropped {prev_chg1:.1f}% → {chg1:.1f}% (>{CHG1_DROP_THRESHOLD}% drop) - rejecting")
                    to_remove.append(addr)
                    continue
                
                improvement = chg1 - prev_chg1
                if improvement >= 2:
                    # Increment recheck count
                    data['recheck_count'] = data.get('recheck_count', 0) + 1
                    
                    # Require 2+ consecutive positive rechecks
                    if data['recheck_count'] < 2:
                        print(f"   ⏳ {result['token']}: recheck #{data['recheck_count']} positive (chg1={chg1:.1f}%), need 1 more - waiting 15s")
                        data['cooldown_secs'] += 15
                        data['first_seen'] = time.time()
                        continue
                    
                    # Improvement detected - do final confirmation check
                    print(f"   ⏳ {result['token']}: chg1 improved {improvement:+.1f}% to {chg1:+.1f}% - doing final confirmation...")
                    
                    # Final check - get fresh chg1
                    final_chg1 = None
                    try:
                        r2 = requests.get(f'https://api.dexscreener.com/latest/dex/tokens/{addr}', timeout=5)
                        if r2.status_code == 200:
                            pairs2 = r2.json().get('pairs', [])
                            if pairs2:
                                final_chg1_raw = pairs2[0].get('priceChange', {}).get('m1')
                                if final_chg1_raw is not None:
                                    final_chg1 = float(final_chg1_raw)
                    except:
                        pass
                    
                    # OPTION 1: Check MIN_CHG1 - chg1 must be > +3% to buy
                    if final_chg1 is not None and final_chg1 >= MIN_CHG1_FOR_BUY:
                        # Final confirmation passed - BUY
                        should_buy_flag, buy_reason = should_buy(result2, whales)
                        if should_buy_flag:
                            trade = buy_token(addr, result2)
                            if trade:
                                print(f"   🟢 BUY (after {elapsed:.0f}s cooldown): {result2['token']} @ ${result2['mcap']:,.0f}")
                                to_remove.append(addr)
                            else:
                                to_remove.append(addr)
                        else:
                            to_remove.append(addr)
                    else:
                        # Final check failed - continue watching
                        print(f"   ⏳ {result['token']}: final check chg1={final_chg1:+.1f}% not positive, continuing to watch")
                        data['cooldown_secs'] += 15
                        data['first_seen'] = time.time()
                        data['prev_chg1'] = final_chg1 if final_chg1 is not None else chg1
                        continue
                else:
                    # Not enough improvement yet
                    data['cooldown_secs'] += 15
                    data['first_seen'] = time.time()
                    print(f"   ⏳ {result['token']}: chg1={chg1:+.1f}% (improvement {improvement:+.1f}% < +2%), waiting 15s")
                    data['prev_chg1'] = chg1
                    continue
            else:
                # First recheck or previous was None - just waiting for improvement
                data['cooldown_secs'] += 15
                data['first_seen'] = time.time()
                print(f"   ⏳ {result['token']}: chg1={chg1:+.1f}%, waiting for +2% improvement")
                data['prev_chg1'] = chg1
                continue
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
        print(f"⚠️ Could not verify DEX: {e} - not buying")
        return None
    
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
                    dip_val = result.get('dip') or 0
                    
                    print(f"✅ {result['token']}{pump}{bond} [{addr[:8]}...] | Mcap ${result['mcap']:,.0f} | Age {result['age']:.1f}min | Dip {dip_val:.1f}% | h1 {result['h1']:+.1f}% | 5m {result['m5']:+.1f}%")
                    
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
                        
                        # NEW RULE: If m5 > +100%, track peak and require dip > 15% + chg1 > +3%
                        _needs_peak_tracking = False
                        if result['m5'] > 100:
                            _needs_peak_tracking = True
                            cooldown_secs = 150  # Wait 150s first
                        elif age < 15 and result['m5'] > 50:
                            cooldown_secs = 120  # Young + parabolic
                        elif age >= 15 and result['m5'] > 1:
                            cooldown_secs = 120  # Older + positive chg5
                        else:
                            cooldown_secs = 0
                        
                        # If chg1 (1min change) is negative, add 60s extra cooldown
                        if result.get('chg1', 0) < 0:
                            cooldown_secs += 60
                        
                        if cooldown_secs > 0:
                            if addr not in COOLDOWN_WATCH:
                                COOLDOWN_WATCH[addr] = {
                                    'first_seen': time.time(),
                                    'result': result,
                                    'token_data': token_data,
                                    'cooldown_secs': cooldown_secs,
                                    'parabolic_candidate': result.get('_parabolic_candidate', False),
                                    'peak_mcap': result.get('mcap', 0),
                                    'needs_peak_tracking': _needs_peak_tracking,
                                    'recheck_count': 0,  # Count consecutive positive rechecks
                                    'prev_chg1': None
                                }
                                peak_msg = " [PEAK TRACK]" if _needs_peak_tracking else ""
                                parabolic_msg = " [PARABOLIC]" if result.get('_parabolic_candidate') else ""
                                print(f"   ⏳ {result['token']} [{addr[:8]}...]: Added to cooldown for {cooldown_secs}s (chg5={result['m5']:+.1f}%, age={result['age']:.1f}min){peak_msg}{parabolic_msg}")
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