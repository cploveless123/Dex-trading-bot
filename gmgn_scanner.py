#!/usr/bin/env python3
"""
GMGN Scanner v6.3 - Wilson Bot
Primary scanner using GMGN data source

Decision Flow:
1. Fetch tokens from GMGN market trending, new pairs, trenches
2. Skip if: blacklisted OR 9+ open positions
3. For each token passing filters → cooldown monitor → buy
"""

import requests
import json
import time
import subprocess
from datetime import datetime
from pathlib import Path

from trading_constants import (
    MIN_MCAP, MAX_MCAP, MIN_AGE_SECONDS, MAX_AGE_SECONDS,
    MIN_5MIN_VOLUME, MIN_HOLDERS, TOP10_HOLDER_MAX,
    BS_RATIO_NEW, BS_RATIO_OLD, BS_PUMP_FUN_OK,
    H1_MOMENTUM_MIN, H24_MOMENTUM_MIN,
    MIN_CHG1_FOR_BUY, CHG1_DROP_THRESHOLD, CHG1_NONE_M5_REJECT,
    CHG1_COOLDOWN_TRIGGER,
    DIP_MIN, DIP_MAX, ATH_DIVERGENCE_MIN,
    YOUNG_PUMP_5M_THRESHOLD, OLD_PUMP_5M_THRESHOLD,
    YOUNG_COOLDOWN, OLD_COOLDOWN,
    CHG1_COOLDOWN_EXTRA, CHG1_COOLDOWN_VERIFY, MAX_RECHECKS, RECHECK_DELAY,
    PRICE_DROP_THRESHOLD, PRICE_DROP_WAIT_1, PRICE_DROP_WAIT_2, PRICE_DROP_WAIT_3, MCAP_INCREASE_CONFIRM,
    H1_INSTABILITY_MULTIPLIER,
    H1_PARABOLIC_REJECT, FALLING_KNIFE_CONSECUTIVE,
    LIQUIDITY_MCAP_THRESHOLD, LIQUIDITY_MIN,
    TP1_PERCENT, TP1_TRAILING_PCT, TP1_SELL_PCT,
    TP2_PERCENT, TP2_TRAILING_PCT, TP2_SELL_PCT,
    TP3_PERCENT, TP3_TRAILING_PCT, TP3_SELL_PCT,
    TP4_PERCENT, TP4_TRAILING_PCT, TP4_SELL_PCT,
    TP5_PERCENT, TP5_TRAILING_PCT, TP5_SELL_PCT,
    TRAILING_STOP_PCT, STOP_LOSS_PERCENT,
    ALLOWED_EXCHANGES, REJECTED_EXCHANGES,
    MIN_GMGN_SCORE, GMGN_VOL_MCAP_MIN,
    TICKER_BLACKLIST, SIM_RESET_TIMESTAMP,
    MAX_OPEN_POSITIONS, POSITION_SIZE,
    LOW_VOLUME_THRESHOLD, SCAN_INTERVAL
)

# Files
TRADES_FILE = Path("/root/Dex-trading-bot/trades/sim_trades.jsonl")
WHALE_DB = Path("/root/Dex-trading-bot/wallet_analysis/whale_wallets.jsonl")
SIGNALS_DIR = Path("/root/Dex-trading-bot/signals")
PEAK_CACHE = Path("/root/Dex-trading-bot/position_peak_cache.json")

# Cooldown watch: {addr: {"first_seen": ts, "token_data": {}, "result": {}, "cooldown_end": ts, "recheck_count": int, "prev_chg1": float, "peak_mcap": float, "entry_price": float}}
COOLDOWN_WATCH = {}

# Tokens rejected after max rechecks — can revisit after delay
REJECTED_TEMP = {}  # {addr: {"ts": timestamp, "reason": str}}
REJECTED_REVISIT_DELAY = 300  # 5 minutes before circling back

# Permanent blacklist (once bought, never rebuy)
PERM_BLACKLIST = set()

# State
_buy_prices = {}
_peak_prices = {}

def load_blacklist():
    """Load all ever-bought tokens into permanent blacklist"""
    global PERM_BLACKLIST
    PERM_BLACKLIST = set()
    if TRADES_FILE.exists():
        with open(TRADES_FILE) as f:
            for line in f:
                try:
                    t = json.loads(line)
                    if t.get('action') == 'BUY' and t.get('token_address'):
                        PERM_BLACKLIST.add(t['token_address'])
                except:
                    pass

def load_whales():
    """Load whale wallets"""
    if not WHALE_DB.exists():
        return []
    whales = []
    with open(WHALE_DB) as f:
        for line in f:
            try:
                w = json.loads(line)
                if w.get('winrate', 0) >= 0.5 and w.get('buy_count', 0) >= 3:
                    whales.append(w.get('wallet', ''))
            except:
                pass
    return whales

def get_open_position_count():
    """Count currently open positions from trade file"""
    count = 0
    reset = SIM_RESET_TIMESTAMP
    if TRADES_FILE.exists():
        with open(TRADES_FILE) as f:
            for line in f:
                try:
                    t = json.loads(line)
                    if t.get('opened_at', '') > reset and not t.get('closed_at') and t.get('status') in ['open', 'open_partial']:
                        count += 1
                except:
                    pass
    return count

def get_gmgn_trending(limit=50):
    """Get GMGN market trending tokens"""
    try:
        r = subprocess.run(
            ['gmgn-cli', 'market', 'trending', '--chain', 'sol', '--interval', '5m', '--limit', str(limit)],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode == 0:
            data = json.loads(r.stdout)
            return data.get('data', {}).get('rank', [])
    except Exception as e:
        print(f"GMGN trending error: {e}")
    return []

def get_gmgn_new_pairs(limit=30):
    """Get GMGN new pairs (using trenches endpoint)"""
    try:
        r = subprocess.run(
            ['gmgn-cli', 'market', 'trenches', '--chain', 'sol', '--limit', str(limit)],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode == 0:
            data = json.loads(r.stdout)
            # trenches returns {creating: [], created: [], completed: []}
            all_pairs = []
            all_pairs.extend(data.get('creating', []))
            all_pairs.extend(data.get('created', []))
            all_pairs.extend(data.get('completed', []))
            return all_pairs
    except Exception as e:
        print(f"GMGN new pairs error: {e}")
    return []

def get_gmgn_token_info(addr):
    """Get fresh GMGN token info"""
    try:
        r = subprocess.run(
            ['gmgn-cli', 'token', 'info', '--chain', 'sol', '--address', addr],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode == 0:
            return json.loads(r.stdout)
    except:
        pass
    return None

def get_dexscreener_data(addr):
    """Get DexScreener data for a token"""
    try:
        r = requests.get(f'https://api.dexscreener.com/latest/dex/tokens/{addr}', timeout=8)
        if r.status_code == 200:
            data = r.json()
            pairs = data.get('pairs', [])
            if pairs:
                best = max(pairs, key=lambda x: x.get('liquidity', {}).get('usd', 0))
                return best
    except:
        pass
    return None

def get_pair_age_minutes(creation_ts):
    """Calculate pair age in minutes"""
    if not creation_ts:
        return 999
    return (time.time() - creation_ts) / 60

def calculate_dip(mcap, ath_mcap):
    """Calculate dip % from ATH"""
    if ath_mcap and ath_mcap > 0 and mcap < ath_mcap:
        return max(0, (1 - mcap / ath_mcap) * 100)
    return 0.0

def check_exchange_valid(dex_id, addr):
    """Validate exchange - pump.fun, pumpswap, raydium only"""
    if not dex_id:
        return False, "No dex"
    
    dex = dex_id.lower()
    addr_lower = addr.lower()
    
    # Check allowed
    if dex in ALLOWED_EXCHANGES:
        # pump.fun/pumpswap must end in "pump"
        if dex in ['pumpfun', 'pumpswap']:
            if addr_lower.endswith('pump'):
                return True, dex
            return False, f"{dex} but addr doesn't end in pump"
        return True, dex
    
    # Check rejected
    for bad in REJECTED_EXCHANGES:
        if bad in dex:
            return False, dex
    
    return False, dex

def scan_token(token_data, dex_data, whales):
    """
    Apply v6.3 filters to a token
    Returns (result_dict, reason) if passes, (None, reason) if fails
    """
    addr = token_data.get('address', '')
    symbol = token_data.get('symbol', '?')
    name = token_data.get('name', 'Unknown')
    
    # GMGN data
    mcap = float(token_data.get('market_cap', 0) or 0)
    h1 = float(token_data.get('price_change_percent1h', 0) or 0)
    h24 = float(token_data.get('price_change_percent24h', 0) or 0)
    m5 = float(token_data.get('price_change_percent5m', 0) or 0)
    holders = int(token_data.get('holder_count', 0) or 0)
    top10 = float(token_data.get('top_10_holder_rate', 0) or 0) * 100
    liq = float(token_data.get('liquidity', 0) or 0)
    creation_ts = int(token_data.get('creation_timestamp', 0) or 0)
    burn_status = token_data.get('burn_status', '')
    dex_id = token_data.get('exchange', '')
    
    # DexScreener data (for chg1, m5_vol, holders backup)
    chg1 = None
    m5_vol = 0
    ds_holders = 0
    ds_top10 = 0
    
    if dex_data:
        chg1 = dex_data.get('priceChange', {}).get('m1')
        if chg1 is not None:
            chg1 = float(chg1)
        m5_vol = float(dex_data.get('volume', {}).get('m5', 0) or 0)
        ds_holders = int(dex_data.get('holderCount', 0) or 0)
        ds_top10 = float(dex_data.get('marketCap', 0) or 0)
    
    # Fallback from DexScreener
    if holders == 0 and ds_holders > 0:
        holders = ds_holders
    if top10 == 0 and ds_top10 > 0:
        top10 = ds_top10
    
    age_min = get_pair_age_minutes(creation_ts)
    age_sec = age_min * 60
    
    # ATH from GMGN
    ath_mcap = float(token_data.get('history_highest_market_cap', 0) or 0)
    dip = calculate_dip(mcap, ath_mcap)
    
    # === BLACKLIST CHECK ===
    if addr in PERM_BLACKLIST:
        return None, f"PERM_BLACKLIST (ever bought)"
    if symbol in TICKER_BLACKLIST:
        return None, f"ticker blacklisted ({symbol})"
    
    # === OPEN POSITIONS CHECK ===
    if get_open_position_count() >= MAX_OPEN_POSITIONS:
        return None, f"MAX_OPEN {get_open_position_count()}/{MAX_OPEN_POSITIONS}"
    
    # === MCAP FILTER ===
    if mcap < MIN_MCAP:
        return None, f"mcap ${mcap:,.0f} < ${MIN_MCAP:,}"
    if mcap > MAX_MCAP:
        return None, f"mcap ${mcap:,.0f} > ${MAX_MCAP:,}"
    
    # === AGE FILTER ===
    if age_sec < MIN_AGE_SECONDS:
        return None, f"age {age_sec:.0f}s < {MIN_AGE_SECONDS}s (too young)"
    if age_sec > MAX_AGE_SECONDS:
        return None, f"age {age_min:.0f}m > {MAX_AGE_SECONDS/60:.0f}m (too old)"
    
    # === HOLDERS FILTER ===
    if holders < MIN_HOLDERS:
        return None, f"holders {holders} < {MIN_HOLDERS}"
    
    # === BOT FARM CHECK: holders=0 OR top10=0 ===
    if holders == 0 or top10 == 0:
        return None, f"bot farm (holders={holders} top10={top10:.0f}%)"
    
    # === TOP10% FILTER ===
    if top10 > TOP10_HOLDER_MAX:
        return None, f"top10 {top10:.1f}% > {TOP10_HOLDER_MAX}% (dumper)"
    
    # === MOMENTUM FILTER: h1 > +50% OR 24h > +50% ===
    if h1 < H1_MOMENTUM_MIN and h24 < H24_MOMENTUM_MIN:
        return None, f"no momentum (h1={h1:+.1f}% 24h={h24:+.1f}%, need >+50%)"
    
    # === PARABOLIC REJECT: h1 > +833% ===
    if h1 > H1_PARABOLIC_REJECT:
        return None, f"h1 {h1:+.1f}% > +{H1_PARABOLIC_REJECT}% (parabolic)"
    
    # === CHG1 RULES ===
    # chg1 = None AND m5 > +15% → REJECT immediately
    if chg1 is None and m5 > CHG1_NONE_M5_REJECT:
        return None, f"chg1=None but m5 {m5:+.1f}% > +{CHG1_NONE_M5_REJECT}% (unsafe)"
    
    # === DIP FILTER: 15-45% ===
    if dip < DIP_MIN:
        return None, f"dip {dip:.1f}% < {DIP_MIN}% (not enough pullback)"
    if dip > DIP_MAX:
        return None, f"dip {dip:.1f}% > {DIP_MAX}% (too deep)"
    
    # === ATH DISTANCE CHECK: must be >15% below ATH ===
    if ath_mcap > 0:
        ath_distance = ((ath_mcap - mcap) / ath_mcap) * 100
        if ath_distance < ATH_DIVERGENCE_MIN:
            return None, f"ATH dist {ath_distance:.1f}% < {ATH_DIVERGENCE_MIN}% (too close to ATH)"
    
    # === BS RATIO ===
    bs_min = BS_RATIO_OLD if age_min >= 15 else BS_RATIO_NEW
    buys = int(token_data.get('buys', 0) or 0)
    sells = int(token_data.get('sells', 0) or 1)
    if sells == 0:
        sells = 1
    bs = buys / sells if buys > 0 else 0
    if not BS_PUMP_FUN_OK and bs == 0 and 'pump' in dex_id.lower():
        pass  # pump.fun BS=0 is OK
    elif bs < bs_min:
        return None, f"BS {bs:.2f} < {bs_min} (age={age_min:.0f}m)"
    
    # === LIQUIDITY: mcap > $60K requires > $1K liq ===
    if mcap > LIQUIDITY_MCAP_THRESHOLD and liq < LIQUIDITY_MIN:
        return None, f"liq ${liq:,.0f} < ${LIQUIDITY_MIN:,} (mcap ${mcap:,.0f} > $60K)"
    
    # === EXCHANGE VALIDATION ===
    valid, dex_reason = check_exchange_valid(dex_id, addr)
    if not valid:
        return None, f"exchange {dex_reason} not allowed"
    
    # === VOLUME FILTER: 5min vol $1K+ ===
    if m5_vol < MIN_5MIN_VOLUME:
        return None, f"m5_vol ${m5_vol:,.0f} < ${MIN_5MIN_VOLUME:,}"
    
    # === FALLING KNIFE CHECK ===
    if chg1 is not None and chg1 < 0:
        return None, f"chg1 {chg1:+.1f}% < 0 (falling knife)"
    
    entry_price = float(token_data.get('price', 0) or 0)
    if dex_data and entry_price == 0:
        entry_price = float(dex_data.get('priceUsd', 0) or 0)
    
    return {
        'token': symbol,
        'address': addr,
        'name': name,
        'mcap': mcap,
        'h1': h1,
        'h24': h24,
        'm5': m5,
        'chg1': chg1,
        'holders': holders,
        'top10': top10,
        'liq': liq,
        'age_min': age_min,
        'age_sec': age_sec,
        'dip': dip,
        'ath_mcap': ath_mcap,
        'bs': bs,
        'dex': dex_reason,
        'm5_vol': m5_vol,
        'entry_price': entry_price,
        'burn_status': burn_status,
    }, "PASS"

def determine_cooldown(result):
    """Determine cooldown period based on age and momentum"""
    age_min = result['age_min']
    m5 = result['m5']
    
    if age_min < 15 and m5 > YOUNG_PUMP_5M_THRESHOLD:
        return YOUNG_COOLDOWN
    elif age_min >= 15 and m5 > OLD_PUMP_5M_THRESHOLD:
        return OLD_COOLDOWN
    return 0  # No cooldown, buy immediately

def add_to_cooldown(addr, token_data, result):
    """Add token to cooldown watch list"""
    cooldown_secs = determine_cooldown(result)
    if cooldown_secs == 0:
        # No cooldown needed, buy immediately
        return False
    
    COOLDOWN_WATCH[addr] = {
        'first_seen': time.time(),
        'cooldown_end': time.time() + cooldown_secs,
        'token_data': token_data,
        'result': result,
        'recheck_count': 0,
        'prev_chg1': None,
        'peak_mcap': result['mcap'],
        'entry_price': result['entry_price'],
        'price_at_add': result['entry_price'],
        'consecutive_drops': 0,
        'instability_count': 0,
        'prev_h1': result['h1'],
    }
    print(f"   ⏳ {result['token']}: added to cooldown ({cooldown_secs}s)")
    return True

def check_cooldown_watch():
    """Check and process cooldown watch list"""
    to_remove = []
    now = time.time()
    
    for addr, data in COOLDOWN_WATCH.items():
        result = data['result']
        elapsed = now - data['first_seen']
        
        # Get fresh GMGN data
        fresh_data = get_gmgn_token_info(addr)
        fresh_dex = get_dexscreener_data(addr)
        
        if fresh_data is None:
            # GMGN failed - remove from cooldown (no buy without fresh data)
            print(f"   ❌ {result['token']}: GMGN data unavailable - removing from cooldown")
            to_remove.append(addr)
            continue
        
        # Re-evaluate with fresh data
        fresh_result, fresh_reason = scan_token(fresh_data, fresh_dex, [])
        
        if fresh_result is None:
            # No longer passing filters
            print(f"   ❌ {result['token']}: no longer passing filters ({fresh_reason})")
            to_remove.append(addr)
            continue
        
        # Update result with fresh data
        data['result'] = fresh_result
        data['token_data'] = fresh_data
        
        # === INSTABILITY CHECK: h1 changed >3x ===
        prev_h1 = data.get('prev_h1', 0)
        curr_h1 = fresh_result.get('h1', 0)
        if prev_h1 and curr_h1 and prev_h1 > 0:
            ratio = max(prev_h1, curr_h1) / min(prev_h1, curr_h1)
            if ratio > H1_INSTABILITY_MULTIPLIER:
                print(f"   ❌ {result['token']}: h1 unstable {prev_h1:.0f}% → {curr_h1:.0f}% ({ratio:.1f}x)")
                to_remove.append(addr)
                continue
        data['prev_h1'] = curr_h1
        
        # === PRICE STABILITY CHECK ===
        prev_price = data.get('price_at_add', 0)
        curr_price = fresh_result.get('entry_price', 0)
        if prev_price > 0 and curr_price > 0:
            price_change = ((prev_price - curr_price) / prev_price) * 100
            if price_change > PRICE_DROP_THRESHOLD:
                # Price dropped >5% since added to cooldown
                data['consecutive_drops'] += 1
                wait_time = [PRICE_DROP_WAIT_1, PRICE_DROP_WAIT_2, PRICE_DROP_WAIT_3][min(data['consecutive_drops']-1, 2)]
                print(f"   ⏳ {result['token']}: price down {price_change:.1f}% since add - wait {wait_time}s")
                data['cooldown_end'] = now + wait_time
                continue
        
        # === CHG1 CHECK DURING COOLDOWN (v6.4) ===
        # Step 1: cooldown is running — chg1 must reach >+5% to proceed
        # Step 2: once chg1 >= +5%, wait 15s to verify
        # Step 3: check improvement (+3% from prev) and deterioration (>{CHG1_DROP_THRESHOLD}% drop = reject)
        # Step 4: 2 consecutive rechecks before buy
        chg1 = fresh_result.get('chg1')
        prev_chg1 = data.get('prev_chg1')
        cooldown_done = now >= data['cooldown_end']
        chg1_reached_trigger = chg1 is not None and chg1 >= CHG1_COOLDOWN_TRIGGER
        
        if not cooldown_done:
            # Cooldown still running — just monitor chg1, don't count as recheck
            data['prev_chg1'] = chg1
            remaining = data['cooldown_end'] - now
            print(f"   ⏳ {result['token']}: cooldown {remaining:.0f}s left (chg1={chg1:+.1f}% if available)")
            continue
        
        # Cooldown done — now enforce chg1 rules
        if chg1 is None:
            # No chg1 data — wait more
            data['cooldown_end'] = now + RECHECK_DELAY
            continue
        
        if not chg1_reached_trigger:
            # chg1 < +5% — wait extra 15s and keep checking
            data['cooldown_end'] = now + CHG1_COOLDOWN_EXTRA
            print(f"   ⏳ {result['token']}: chg1 {chg1:+.1f}% (need >+{CHG1_COOLDOWN_TRIGGER}%) — waiting 15s more")
            data['prev_chg1'] = chg1
            continue
        
        # chg1 >= +5% — verify with 15s wait
        if not data.get('_chg1_triggered'):
            data['_chg1_triggered'] = True
            data['cooldown_end'] = now + CHG1_COOLDOWN_VERIFY
            data['prev_chg1'] = chg1
            print(f"   ⏳ {result['token']}: chg1 {chg1:+.1f}% >= +{CHG1_COOLDOWN_TRIGGER}% — verifying 15s")
            continue
        
        # Verified — now check improvement and deterioration
        data['recheck_count'] += 1
        
        if prev_chg1 is not None:
            improvement = chg1 - prev_chg1
            
            # Deterioration: chg1 dropped >1% from previous → continue watching
            if prev_chg1 > 0 and chg1 < prev_chg1 - CHG1_DROP_THRESHOLD:
                print(f"   ⏳ {result['token']}: chg1 deteriorated {prev_chg1:+.1f}% → {chg1:+.1f}% (>{CHG1_DROP_THRESHOLD}% drop) — continue watching")
                data['cooldown_end'] = now + RECHECK_DELAY
                data['prev_chg1'] = chg1
                continue
            
            # Improvement: need +3% from previous
            if improvement >= 3:
                if data['recheck_count'] < 2:
                    data['cooldown_end'] = now + RECHECK_DELAY
                    print(f"   ⏳ {result['token']}: recheck #{data['recheck_count']} — chg1 {chg1:+.1f}% (+{improvement:+.1f}% from prev)")
                    continue
                # 2 consecutive rechecks confirmed — BUY
            elif improvement >= 0:
                data['recheck_count'] = 0
                data['cooldown_end'] = now + RECHECK_DELAY
                data['prev_chg1'] = chg1
                continue
            else:
                data['cooldown_end'] = now + RECHECK_DELAY
                data['prev_chg1'] = chg1
                continue
        else:
            # First valid chg1 reading after trigger
            data['prev_chg1'] = chg1
            data['cooldown_end'] = now + RECHECK_DELAY
            continue
        
        # === MAX RECHECKS CHECK ===
        data['recheck_count'] += 1
        if data['recheck_count'] > MAX_RECHECKS:
            print(f"   ❌ {result['token']}: max rechecks ({MAX_RECHECKS}) - will revisit in {REJECTED_REVISIT_DELAY}s")
            REJECTED_TEMP[addr] = {'ts': time.time(), 'reason': f"max rechecks ({MAX_RECHECKS})"}
            to_remove.append(addr)
            continue
        
        # Still watching
        wait_time = max(0, data['cooldown_end'] - now)
        if wait_time > 0:
            print(f"   ⏳ {result['token']}: cooldown {wait_time:.0f}s remaining (recheck #{data['recheck_count']})")
    
    # Remove expired/invalid
    for addr in to_remove:
        if addr in COOLDOWN_WATCH:
            del COOLDOWN_WATCH[addr]
    
    return len(to_remove) > 0

def buy_token(addr, result):
    """Execute simulated buy"""
    now = datetime.utcnow().isoformat()
    
    trade = {
        'action': 'BUY',
        'token_address': addr,
        'token_name': result['token'],
        'entry_price': result['entry_price'],
        'entry_mcap': int(result['mcap']),
        'opened_at': now,
        'closed_at': None,
        'entry_sol': POSITION_SIZE,
        'status': 'open',
        'tp_status': {
            'tp1_hit': False,
            'tp2_hit': False,
            'tp3_hit': False,
            'tp4_hit': False,
            'tp5_hit': False,
        },
        'tp1_sold': False,
        'tp2_sold': False,
        'tp3_sold': False,
        'tp4_sold': False,
        'tp5_sold': False,
        'partial_exit': False,
        'fully_exited': False,
        'peak_price': result['entry_price'],
        'entry_reason': 'GMGN_V63',
        'h1': result['h1'],
        'm5': result['m5'],
        'chg1_at_buy': result['chg1'],
        'dip_at_buy': result['dip'],
        'ath_mcap': result.get('ath_mcap', 0),
        'holders': result['holders'],
        'top10': result['top10'],
        'dex': result.get('dex', 'unknown'),
    }
    
    try:
        with open(TRADES_FILE, 'a') as f:
            f.write(json.dumps(trade) + '\n')
        # Add to blacklist immediately
        PERM_BLACKLIST.add(addr)
        return True
    except Exception as e:
        print(f"Buy error: {e}")
        return False

def scan_cycle():
    """One scan cycle"""
    load_blacklist()
    
    tokens = get_gmgn_trending(50)
    tokens.extend(get_gmgn_new_pairs(30))
    
    # Deduplicate by address
    seen = set()
    unique_tokens = []
    for t in tokens:
        addr = t.get('address', '')
        if addr and addr not in seen:
            seen.add(addr)
            unique_tokens.append(t)
    
    bought = 0
    for token_data in unique_tokens:
        addr = token_data.get('address', '')
        if not addr:
            continue
        
        if addr in COOLDOWN_WATCH:
            continue  # Already in cooldown
        
        if addr in PERM_BLACKLIST:
            continue  # Already bought
        
        # === CIRCLING BACK: Check if rejected recently ===
        if addr in REJECTED_TEMP:
            rejected_data = REJECTED_TEMP[addr]
            elapsed = time.time() - rejected_data['ts']
            if elapsed < REJECTED_REVISIT_DELAY:
                continue  # Still in quiet period
            else:
                # Time to revisit - remove from rejected, log it
                del REJECTED_TEMP[addr]
                print(f"   🔄 {token_data.get('symbol','?')}: circling back after {elapsed:.0f}s rejection")
        
        # Get DexScreener data for chg1
        
        # Get DexScreener data for chg1
        dex_data = get_dexscreener_data(addr)
        
        # Scan
        result, reason = scan_token(token_data, dex_data, [])
        if result is None:
            continue
        
        # Check if needs cooldown
        cooldown_secs = determine_cooldown(result)
        if cooldown_secs > 0:
            if add_to_cooldown(addr, token_data, result):
                continue
        else:
            # Buy immediately
            if buy_token(addr, result):
                print(f"   🟢 BUY (immediate): {result['token']} @ ${result['mcap']:,.0f}")
                bought += 1
                if bought >= 1:
                    break  # One buy per cycle
        break  # Only process top token per cycle
    
    return bought

def main():
    print(f"🚀 GMGN Scanner v6.3 Started")
    print(f"   Filters: Mcap ${MIN_MCAP:,}-${MAX_MCAP:,} | Holders {MIN_HOLDERS}+ | Dip {DIP_MIN}-{DIP_MAX}% | BS {BS_RATIO_NEW}/{BS_RATIO_OLD}")
    print(f"   Momentum: h1 or 24h > +{H1_MOMENTUM_MIN}% | chg1 > +{MIN_CHG1_FOR_BUY}%")
    print(f"   Cooldown: Young(<15m)+m5>+25% → {YOUNG_COOLDOWN}s | Old+m5>+5% → {OLD_COOLDOWN}s")
    
    while True:
        try:
            scan_cycle()
            check_cooldown_watch()
        except Exception as e:
            print(f"Scan error: {e}")
        time.sleep(SCAN_INTERVAL)

if __name__ == '__main__':
    main()
