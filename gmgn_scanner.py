#!/usr/bin/env python3
"""
GMGN Scanner v6.8 - Wilson Bot
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
    MIN_CHG1_FOR_BUY, CHG1_NONE_M5_REJECT, CHG1_IMPROVEMENT_MIN, CHG1_MIN_VALUE,
    DIP_MIN, DIP_MAX, ATH_DIVERGENCE_MAX,
    PUMP_5M_THRESHOLD, BASE_COOLDOWN,
    CHG1_RECHECK_DELAY, CHG1_VERIFY_DELAY,
    CHG1_DROP_REJECT, VERIFY_CONSECUTIVE_OK,
    MAX_RECHECKS, REJECTED_REVISIT_DELAY,
    PRICE_DROP_REJECT, PRICE_DROP_WAIT_1, PRICE_DROP_WAIT_2, PRICE_DROP_WAIT_3, MCAP_INCREASE_CONFIRM,
    H1_INSTABILITY_MULTIPLIER,
    H1_PARABOLIC_REJECT,
    LIQUIDITY_MCAP_THRESHOLD, LIQUIDITY_MIN,
    TP1_PERCENT, TP1_TRAILING_PCT, TP1_SELL_PCT,
    TP2_PERCENT, TP2_TRAILING_PCT, TP2_SELL_PCT,
    TP3_PERCENT, TP3_TRAILING_PCT, TP3_SELL_PCT,
    TP4_PERCENT, TP4_TRAILING_PCT, TP4_SELL_PCT,
    TP5_PERCENT, TP5_TRAILING_PCT, TP5_SELL_PCT,
    TRAILING_STOP_PCT, STOP_LOSS_PERCENT,
    ALLOWED_EXCHANGES, REJECTED_EXCHANGES,
    SIM_RESET_TIMESTAMP,
    MAX_OPEN_POSITIONS, POSITION_SIZE,
    LOW_VOLUME_THRESHOLD, SCAN_INTERVAL,
    STATE_COOLDOWN, STATE_WAITING, STATE_VERIFICATION,
    STATE_PUMP_WAIT, STATE_PUMP_VERIFY,
    PUMP_CHG1_THRESHOLD, PUMP_COOLDOWN_1, PUMP_WAIT_2, PUMP_VERIFY_DELAY,
)

# Files
TRADES_FILE = Path("/root/Dex-trading-bot/trades/sim_trades.jsonl")
WHALE_DB = Path("/root/Dex-trading-bot/wallet_analysis/whale_wallets.jsonl")
SIGNALS_DIR = Path("/root/Dex-trading-bot/signals")
PEAK_CACHE = Path("/root/Dex-trading-bot/position_peak_cache.json")
PERM_BLACKLIST_FILE = Path("/root/Dex-trading-bot/permanent_blacklist.json")

# Cooldown watch: {addr: {"first_seen": ts, "token_data": {}, "result": {}, "cooldown_end": ts, "recheck_count": int, "prev_chg1": float, "peak_mcap": float, "entry_price": float}}
COOLDOWN_WATCH = {}

# Tokens rejected after max rechecks — can revisit after delay
REJECTED_TEMP = {}  # {addr: {"ts": timestamp, "reason": str}}

# Permanent blacklist (once bought, never rebuy)
PERM_BLACKLIST = set()

# GMGN throttle tracking
_gmgn_throttle_count = 0
_gmgn_last_throttle_alert = 0
_gmgn_empty_cycle_count = 0
_gmgn_last_alert_empty = 0

def gmgn_throttle_alert():
    """Send alert if GMGN is throttled"""
    global _gmgn_throttle_count, _gmgn_last_throttle_alert
    _gmgn_throttle_count += 1
    now = time.time()
    if _gmgn_throttle_count >= 3 and (now - _gmgn_last_throttle_alert) > 300:
        # Alert every 5 min if consistently failing
        print(f"🚨 GMGN API THROTTLED: {_gmgn_throttle_count} consecutive failures")
        try:
            from alert_sender import send_telegram_alert
            send_telegram_alert(f"🚨 GMGN API THROTTLED: {_gmgn_throttle_count} failures detected. Check scanner.", "SYSTEM_ALERT")
        except:
            pass
        _gmgn_last_throttle_alert = now

def gmgn_success():
    """Call when GMGN succeeds"""
    global _gmgn_throttle_count
    _gmgn_throttle_count = 0

# State
_buy_prices = {}
_peak_prices = {}

def load_blacklist():
    """Load all ever-bought tokens into permanent blacklist"""
    global PERM_BLACKLIST
    PERM_BLACKLIST = set()
    
    # Load from permanent blacklist file (persists across resets)
    if PERM_BLACKLIST_FILE.exists():
        try:
            with open(PERM_BLACKLIST_FILE) as f:
                PERM_BLACKLIST = set(json.load(f))
        except:
            PERM_BLACKLIST = set()
    
    # Also load from trades file (any buys in current sim_trades)
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
    """Get GMGN market trending tokens (all chains/markets)"""
    try:
        r = subprocess.run(
            ['gmgn-cli', 'market', 'trending', '--chain', 'sol', '--interval', '5m', '--limit', str(limit)],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode == 0:
            gmgn_success()
            data = json.loads(r.stdout)
            return data.get('data', {}).get('rank', [])
        elif r.returncode != 0 and ('rate limit' in r.stderr.lower() or '429' in r.stderr or 'throttl' in r.stderr.lower()):
            gmgn_throttle_alert()
    except Exception as e:
        gmgn_throttle_alert()
    return []

def get_gmgn_pumpfun_lowcap(limit=30):
    """Get pump.fun tokens sorted by ascending marketcap (newest/cheapest first)"""
    try:
        r = subprocess.run(
            ['gmgn-cli', 'market', 'trending', '--chain', 'sol', '--interval', '5m', '--limit', str(limit),
             '--platform', 'Pump.fun', '--order-by', 'marketcap', '--direction', 'asc'],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode == 0:
            gmgn_success()
            data = json.loads(r.stdout)
            return data.get('data', {}).get('rank', [])
        elif r.returncode != 0 and ('rate limit' in r.stderr.lower() or '429' in r.stderr):
            gmgn_throttle_alert()
    except Exception as e:
        gmgn_throttle_alert()
    return []

def get_gmgn_new_pairs(limit=30):
    """Get GMGN new pairs (using trenches endpoint)"""
    try:
        r = subprocess.run(
            ['gmgn-cli', 'market', 'trenches', '--chain', 'sol', '--limit', str(limit)],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode == 0:
            gmgn_success()
            data = json.loads(r.stdout)
            # trenches returns {creating: [], created: [], completed: []}
            all_pairs = []
            all_pairs.extend(data.get('creating', []))
            all_pairs.extend(data.get('created', []))
            all_pairs.extend(data.get('completed', []))
            return all_pairs
        elif r.returncode != 0 and ('rate limit' in r.stderr.lower() or '429' in r.stderr or 'throttl' in r.stderr.lower()):
            gmgn_throttle_alert()
    except Exception as e:
        gmgn_throttle_alert()
    return []

def get_gmgn_token_info(addr):
    """Get fresh GMGN token info"""
    try:
        r = subprocess.run(
            ['gmgn-cli', 'token', 'info', '--chain', 'sol', '--address', addr],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode == 0:
            gmgn_success()
            return json.loads(r.stdout)
        elif 'rate limit' in r.stderr.lower() or '429' in r.stderr:
            gmgn_throttle_alert()
    except Exception as e:
        gmgn_throttle_alert()
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
    
    # DexScreener data (for chg1, m5_vol, holders cross-check)
    chg1 = None
    m5_vol = 0
    ds_holders = 0

    # Source 1: DexScreener m1 price change
    if dex_data:
        chg1 = dex_data.get('priceChange', {}).get('m1')
        if chg1 is not None:
            chg1 = float(chg1)
        m5_vol = float(dex_data.get('volume', {}).get('m5', 0) or 0)
        ds_holders = int(dex_data.get('holderCount', 0) or 0)

    # Source 2: GMGN price_change_percent1m (1-minute change) - use as fallback
    if chg1 is None:
        gmgn_m1 = token_data.get('price_change_percent1m')
        if gmgn_m1 is not None:
            chg1 = float(gmgn_m1)

    # Source 3: GMGN price_change_percent (unknown interval, use as last resort)
    if chg1 is None:
        gmgn_generic = token_data.get('price_change_percent')
        if gmgn_generic is not None:
            chg1 = float(gmgn_generic)
    
    # Fallback holders from DexScreener
    if holders == 0 and ds_holders > 0:
        holders = ds_holders
    
    age_min = get_pair_age_minutes(creation_ts)
    age_sec = age_min * 60
    
    # ATH from GMGN
    ath_mcap = float(token_data.get('history_highest_market_cap', 0) or 0)
    dip = calculate_dip(mcap, ath_mcap)
    
    # === BLACKLIST CHECK ===
    if addr in PERM_BLACKLIST:
        return None, f"PERM_BLACKLIST (ever bought)"
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
    
    # === BOT FARM CHECK: holders=0 on BOTH GMGN and DexScreener = bot farm ===
    # If GMGN shows 0 holders, verify with DexScreener — if also 0, bot farm
    if holders == 0 and ds_holders == 0:
        return None, f"bot farm (gmgn_holders={holders} ds_holders={ds_holders})"
    # top10 = 0 on GMGN = bot farm (DexScreener doesn't have top10% data)
    if top10 == 0:
        return None, f"bot farm (top10={top10:.0f}% on GMGN)"
    
    # === TOP10% FILTER ===
    if top10 > TOP10_HOLDER_MAX:
        return None, f"top10 {top10:.1f}% > {TOP10_HOLDER_MAX}% (dumper)"
    
    # === MOMENTUM FILTER: h1 > +5% OR 24h > +5% ===
    if h1 < H1_MOMENTUM_MIN and h24 < H24_MOMENTUM_MIN:
        return None, f"no momentum (h1={h1:+.1f}% 24h={h24:+.1f}%, need >+5%)"
    
    # === PARABOLIC: no cap (let winners run) ===
    if h1 > H1_PARABOLIC_REJECT:
        return None, f"h1 {h1:+.1f}% > +{H1_PARABOLIC_REJECT}% (parabolic)"
    
    # === CHG1 RULES ===
    # chg1 = None AND m5 > +5% → REJECT immediately (no data = unsafe)
    if chg1 is None and m5 > CHG1_NONE_M5_REJECT:
        return None, f"chg1=None but m5 {m5:+.1f}% > +{CHG1_NONE_M5_REJECT}% (unsafe)"
    
    # === DIP FILTER: 0-50% from local peak ===
    if dip < DIP_MIN:
        return None, f"dip {dip:.1f}% < {DIP_MIN}% (not enough pullback)"
    if dip > DIP_MAX:
        return None, f"dip {dip:.1f}% > {DIP_MAX}% (too deep)"
    
    # === ATH DIVERGENCE: no more than 45% below ATH ===
    if ath_mcap > 0:
        ath_distance = ((ath_mcap - mcap) / ath_mcap) * 100
        if ath_distance > ATH_DIVERGENCE_MAX:
            return None, f"ATH dist {ath_distance:.1f}% > {ATH_DIVERGENCE_MAX}% (too far below ATH)"
    
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
    # Fallback: if GMGN dex_id is empty, use DexScreener's dexId
    exchange_to_check = dex_id
    if not exchange_to_check and dex_data:
        exchange_to_check = dex_data.get('dexId', '')
    valid, dex_reason = check_exchange_valid(exchange_to_check, addr)
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
    """v6.8: cooldown if m5 > -5%"""
    m5 = result['m5']
    if m5 > PUMP_5M_THRESHOLD:
        return BASE_COOLDOWN  # 45s
    return 0  # No cooldown, buy immediately

def add_to_cooldown(addr, token_data, result, dex_data=None):
    """Add token to cooldown watch list - v6.8e pump-aware state machine"""
    cooldown_secs = determine_cooldown(result)
    if cooldown_secs == 0:
        return False  # Buy immediately
    
    now_ts = time.time()
    chg1 = result.get('chg1', 0)
    
    # === PUMP PATH: chg1 > +5% = confirmed pump ===
    # Enter PUMP_WAIT state directly (skip COOLDOWN, go straight to 45s monitoring)
    if chg1 is not None and chg1 > PUMP_CHG1_THRESHOLD:
        pump_state = STATE_PUMP_WAIT
        pump_end = now_ts + PUMP_COOLDOWN_1
        print(f"   🚀 {result['token']}: PUMP CONFIRMED (chg1={chg1:+.1f}%) — 45s monitor")
    else:
        pump_state = STATE_COOLDOWN
        pump_end = now_ts + cooldown_secs
        print(f"   ⏳ {result['token']}: cooldown {cooldown_secs}s (m5={result['m5']:+.1f}%)")
    
    COOLDOWN_WATCH[addr] = {
        'first_seen': now_ts,
        'cooldown_end': pump_end,
        'state': pump_state,
        'token_data': token_data,
        'result': result,
        'dex_data': dex_data,
        'prev_chg1': None,
        'chg1_at_cooldown_start': chg1,
        'consecutive_ok': 0,
        'recheck_count': 0,
        'local_peak_mcap': result['mcap'],
        'lowest_mcap': result['mcap'],
        'price_at_last_check': result['entry_price'],
        'prev_h1': result['h1'],
        'price_drop_consecutive': 0,
        '_pump_confirmed': chg1 is not None and chg1 > PUMP_CHG1_THRESHOLD,
    }
    return True

def check_cooldown_watch():
    """
    v6.8 Cooldown State Machine:
    States: COOLDOWN → WAITING → VERIFICATION → BUY
    
    Unified: m5 > -5% → 45s cooldown for ALL tokens
    After cooldown:
      - chg1 must be > -5% (no falling knife)
      - chg1 must improve > +3% from last check to enter verify
      - in verify: 2 consecutive rechecks with +3% improvement = BUY
      - deterioration >3% from prev check = REJECT (any state)
      - 3 consecutive price drops >3% = REJECT
    """
    to_remove = []
    now = time.time()
    
    for addr, data in COOLDOWN_WATCH.items():
        result = data['result']
        state = data.get('state', STATE_COOLDOWN)
        
        # === GET FRESH DATA ===
        fresh_data = get_gmgn_token_info(addr)
        fresh_dex = get_dexscreener_data(addr)
        
        # Build merged data: fresh GMGN (always overrides) → DexScreener fills gaps
        merged_data = {}
        if fresh_data:
            merged_data = fresh_data.copy()
        if fresh_dex:
            # DexScreener fills only where GMGN gave 0/None
            ds_chg1 = fresh_dex.get('priceChange', {}).get('m1')
            if ds_chg1 is not None:
                merged_data['price_change_percent1m'] = float(ds_chg1)
            ds_price = fresh_dex.get('priceUsd')
            if ds_price and merged_data.get('price') in (None, 0, ''):
                merged_data['price'] = float(ds_price)
            ds_mcap = fresh_dex.get('marketCap')
            if ds_mcap and float(ds_mcap) > 0 and merged_data.get('market_cap', 0) == 0:
                merged_data['market_cap'] = float(ds_mcap)
            ds_m5 = fresh_dex.get('volume', {}).get('m5')
            if ds_m5 and float(ds_m5) > 0 and merged_data.get('volume5m', 0) == 0:
                merged_data['volume5m'] = float(ds_m5)
            ds_holders = fresh_dex.get('holderCount')
            if ds_holders and merged_data.get('holder_count', 0) == 0:
                merged_data['holder_count'] = int(ds_holders)
        
        if not fresh_data and not merged_data:
            print(f"   ❌ {result['token']}: no data (GMGN+DexScreener failed) - removing")
            to_remove.append(addr)
            continue
        
        # === RE-EVALUATE FILTERS with FRESH data ===
        scan_data = merged_data if merged_data else fresh_data
        fresh_result, fresh_reason = scan_token(scan_data, fresh_dex, [])
        
        if fresh_result is None:
            print(f"   ❌ {result['token']}: no longer passing filters ({fresh_reason})")
            to_remove.append(addr)
            continue
        
        data['result'] = fresh_result
        data['token_data'] = merged_data
        data['dex_data'] = fresh_dex
        
        # === UPDATE PEAK/TRACKING ===
        curr_mcap = fresh_result.get('mcap', 0)
        curr_price = fresh_result.get('entry_price', 0)
        if curr_mcap > 0:
            if curr_mcap > data.get('local_peak_mcap', 0):
                data['local_peak_mcap'] = curr_mcap
            if curr_mcap < data.get('lowest_mcap', float('inf')):
                data['lowest_mcap'] = curr_mcap
        
        # === H1 INSTABILITY CHECK ===
        prev_h1 = data.get('prev_h1', 0)
        curr_h1 = fresh_result.get('h1', 0)
        if prev_h1 and curr_h1 and prev_h1 > 0:
            ratio = max(prev_h1, curr_h1) / min(prev_h1, curr_h1)
            if ratio > H1_INSTABILITY_MULTIPLIER:
                print(f"   ❌ {result['token']}: h1 unstable {prev_h1:.0f}% → {curr_h1:.0f}% ({ratio:.1f}x)")
                to_remove.append(addr)
                continue
        data['prev_h1'] = curr_h1
        
        chg1 = fresh_result.get('chg1')
        prev_chg1 = data.get('prev_chg1')
        cooldown_done = now >= data['cooldown_end']
        baseline = data.get('chg1_at_cooldown_start')  # chg1 when cooldown started
        
        def is_deterioration(cur, prev):
            """chg1 dropped >3% from previous check"""
            if prev is None or cur is None: return False
            if prev <= 0: return False
            return (prev - cur) > CHG1_DROP_REJECT
        
        # === STATE MACHINE ===
        if state == STATE_COOLDOWN:
            # COOLDOWN: just monitor, update tracking
            if not cooldown_done:
                remaining = data['cooldown_end'] - now
                print(f"   ⏳ {result['token']}: cooldown {remaining:.0f}s left (chg1={chg1:+.1f}%)")
                data['prev_chg1'] = chg1
                continue
            
            # Cooldown done
            # Check if pump path
            if data.get('_pump_confirmed'):
                # Enter PUMP_WAIT — 30s to recheck
                data['state'] = STATE_PUMP_WAIT
                data['cooldown_end'] = now + PUMP_WAIT_2
                data['prev_chg1'] = chg1
                data['recheck_count'] = 0
                print(f"   ⏳ {result['token']}: cooldown done | chg1={chg1:+.1f}% | PUMP path — wait {PUMP_WAIT_2}s then recheck")
                continue
            else:
                # Enter WAITING (normal path)
                if chg1 is not None:
                    data['chg1_at_cooldown_start'] = chg1
                data['state'] = STATE_WAITING
                data['cooldown_end'] = now + CHG1_RECHECK_DELAY
                data['prev_chg1'] = chg1
                data['recheck_count'] = 0
                data['consecutive_ok'] = 0
                print(f"   ⏳ {result['token']}: cooldown done | baseline chg1={baseline:+.1f}% | need +3% improvement to enter verify")
                continue
        
        elif state == STATE_PUMP_WAIT:
            # PUMP_WAIT: 30s after first cooldown — check if chg1 still > +5%
            if not cooldown_done:
                remaining = data['cooldown_end'] - now
                print(f"   ⏳ {result['token']}: pump wait {remaining:.0f}s left (chg1={chg1:+.1f}%)")
                data['prev_chg1'] = chg1
                continue
            
            # Check if chg1 still > +5% with fresh data
            if chg1 is None or chg1 <= PUMP_CHG1_THRESHOLD:
                # chg1 dropped — exit pump path, go to normal WAITING
                data['state'] = STATE_WAITING
                data['cooldown_end'] = now + CHG1_RECHECK_DELAY
                data['prev_chg1'] = chg1
                data['recheck_count'] = 0
                data['consecutive_ok'] = 0
                print(f"   ❌ {result['token']}: chg1 {chg1:+.1f}% <= +{PUMP_CHG1_THRESHOLD}% — pump faded, switch to normal path")
                continue
            
            # chg1 still > +5% — enter PUMP_VERIFY for final 15s
            data['state'] = STATE_PUMP_VERIFY
            data['cooldown_end'] = now + PUMP_VERIFY_DELAY
            data['prev_chg1'] = chg1
            print(f"   ⏳ {result['token']}: chg1 {chg1:+.1f}% still > +{PUMP_CHG1_THRESHOLD}% — PUMP VERIFY {PUMP_VERIFY_DELAY}s")
            continue
        
        elif state == STATE_PUMP_VERIFY:
            # PUMP_VERIFY: 15s final verify — if chg1 > +5% throughout = BUY
            if not cooldown_done:
                remaining = data['cooldown_end'] - now
                print(f"   ⏳ {result['token']}: pump verify {remaining:.0f}s left (chg1={chg1:+.1f}%)")
                data['prev_chg1'] = chg1
                continue
            
            # Final check — chg1 must be > +5%
            if chg1 is not None and chg1 > PUMP_CHG1_THRESHOLD:
                # BUY!
                print(f"   🟢 BUY (PUMP): {result['token']} @ mcap ${curr_mcap:,.0f} | chg1={chg1:+.1f}% (sustained pump)")
                buy_token(addr, fresh_result)
                to_remove.append(addr)
                continue
            else:
                # Pump faded — exit to normal WAITING
                data['state'] = STATE_WAITING
                data['cooldown_end'] = now + CHG1_RECHECK_DELAY
                data['prev_chg1'] = chg1
                data['recheck_count'] = 0
                data['consecutive_ok'] = 0
                print(f"   ❌ {result['token']}: pump verify chg1 {chg1:+.1f}% <= +{PUMP_CHG1_THRESHOLD}% — switch to normal path")
                continue
        
        elif state == STATE_WAITING:
            # WAITING: monitoring chg1, need +3% improvement from last check to enter verify
            # deterioration >3% from prev = REJECT
            if is_deterioration(chg1, prev_chg1):
                print(f"   ❌ {result['token']}: WAITING — chg1 deteriorated {prev_chg1:+.1f}% → {chg1:+.1f}% (>3% drop) — REJECT")
                REJECTED_TEMP[addr] = {'ts': time.time(), 'reason': 'deterioration'}
                to_remove.append(addr)
                continue
            
            if not cooldown_done:
                remaining = data['cooldown_end'] - now
                print(f"   ⏳ {result['token']}: waiting {remaining:.0f}s left (chg1={chg1:+.1f}% from baseline {baseline:+.1f}%)")
                data['prev_chg1'] = chg1
                continue
            
            # Recheck time
            data['recheck_count'] += 1
            if data['recheck_count'] > MAX_RECHECKS:
                print(f"   ❌ {result['token']}: max rechecks ({MAX_RECHECKS}) — temp reject")
                REJECTED_TEMP[addr] = {'ts': time.time(), 'reason': 'max rechecks'}
                to_remove.append(addr)
                continue
            
            if chg1 is None:
                data['cooldown_end'] = now + CHG1_RECHECK_DELAY
                data['prev_chg1'] = chg1
                print(f"   ⏳ {result['token']}: recheck #{data['recheck_count']} chg1=None")
                continue
            
            # Check improvement from LAST CHECK (prev_chg1), not from baseline
            if prev_chg1 is not None:
                improvement = chg1 - prev_chg1
            else:
                improvement = chg1 - baseline if baseline is not None else 0
            
            if improvement > CHG1_IMPROVEMENT_MIN:
                # +3% improvement from last check → enter VERIFY
                data['state'] = STATE_VERIFICATION
                data['cooldown_end'] = now + CHG1_VERIFY_DELAY
                data['prev_chg1'] = chg1
                data['consecutive_ok'] = 0
                data['recheck_count'] = 0
                print(f"   ⏳ {result['token']}: chg1 {chg1:+.1f}% (improved +{improvement:+.1f}% from {prev_chg1:+.1f}% or baseline {baseline:+.1f}%) — verifying 15s")
                continue
            else:
                # Not enough improvement — keep waiting
                data['cooldown_end'] = now + CHG1_RECHECK_DELAY
                data['prev_chg1'] = chg1
                print(f"   ⏳ {result['token']}: recheck #{data['recheck_count']} chg1={chg1:+.1f}% (improvement +{improvement:+.1f}% < +{CHG1_IMPROVEMENT_MIN}%) — keep waiting")
                continue
        
        elif state == STATE_VERIFICATION:
            # VERIFICATION: 15s verify, need 2 consecutive rechecks with +3% improvement
            # deterioration >3% from prev = REJECT
            if is_deterioration(chg1, prev_chg1):
                print(f"   ❌ {result['token']}: VERIFY — chg1 deteriorated {prev_chg1:+.1f}% → {chg1:+.1f}% (>3% drop) — REJECT")
                REJECTED_TEMP[addr] = {'ts': time.time(), 'reason': 'deterioration'}
                to_remove.append(addr)
                continue
            
            if not cooldown_done:
                remaining = data['cooldown_end'] - now
                print(f"   ⏳ {result['token']}: verifying {remaining:.0f}s left (consecutive_ok={data['consecutive_ok']}/{VERIFY_CONSECUTIVE_OK})")
                data['prev_chg1'] = chg1
                continue
            
            # === PRICE STABILITY CHECK ===
            price_at_last = data.get('price_at_last_check', 0)
            price_drop_count = data.get('price_drop_consecutive', 0)
            
            if price_at_last > 0 and curr_price > 0:
                price_drop = ((price_at_last - curr_price) / price_at_last) * 100
                if price_drop > PRICE_DROP_REJECT:
                    price_drop_count += 1
                    data['price_drop_consecutive'] = price_drop_count
                    wait_times = [PRICE_DROP_WAIT_1, PRICE_DROP_WAIT_2, PRICE_DROP_WAIT_3]
                    wait_time = wait_times[min(price_drop_count - 1, 2)]
                    if price_drop_count >= 3:
                        print(f"   ❌ {result['token']}: 3 consecutive price drops ({price_drop:.1f}%) — REJECT")
                        REJECTED_TEMP[addr] = {'ts': time.time(), 'reason': 'price instability'}
                        to_remove.append(addr)
                        continue
                    print(f"   ⏳ {result['token']}: price down {price_drop:.1f}% ({price_drop_count}/3 drops) — wait {wait_time}s")
                    data['cooldown_end'] = now + wait_time
                    data['price_at_last_check'] = curr_price
                    data['prev_chg1'] = chg1
                    continue
                else:
                    data['price_drop_consecutive'] = 0
            
            data['price_at_last_check'] = curr_price
            
            # Check +3% improvement from last check
            if prev_chg1 is not None:
                improvement = chg1 - prev_chg1
            else:
                improvement = chg1 - baseline if baseline is not None else 0
            
            if improvement > CHG1_IMPROVEMENT_MIN:
                data['consecutive_ok'] += 1
                data['prev_chg1'] = chg1
                print(f"   ⏳ {result['token']}: recheck #{data['consecutive_ok']} chg1={chg1:+.1f}% (improved +{improvement:+.1f}%) | {data['consecutive_ok']}/{VERIFY_CONSECUTIVE_OK} consec")
                
                if data['consecutive_ok'] >= VERIFY_CONSECUTIVE_OK:
                    # BUY!
                    lowest_mcap = data.get('lowest_mcap', 0)
                    if lowest_mcap > 0 and curr_mcap > 0:
                        mcap_recovery = ((curr_mcap - lowest_mcap) / lowest_mcap) * 100
                        if mcap_recovery < MCAP_INCREASE_CONFIRM:
                            print(f"   ⏳ {result['token']}: mcap up {mcap_recovery:.1f}% from low < 2% — recheck 15s")
                            data['cooldown_end'] = now + CHG1_RECHECK_DELAY
                            data['consecutive_ok'] = 0
                            continue
                    print(f"   🟢 BUY: {result['token']} @ mcap ${curr_mcap:,.0f} | chg1={chg1:+.1f}% (+{improvement:+.1f}% from {baseline:+.1f}% baseline)")
                    buy_token(addr, fresh_result)
                    to_remove.append(addr)
                    continue
                else:
                    data['cooldown_end'] = now + CHG1_RECHECK_DELAY
                    continue
            else:
                # Improvement not met — REJECT
                print(f"   ❌ {result['token']}: verify chg1 {chg1:+.1f}% (improvement +{improvement:+.1f}% < +{CHG1_IMPROVEMENT_MIN}%) — REJECT")
                REJECTED_TEMP[addr] = {'ts': time.time(), 'reason': f'insufficient improvement ({improvement:+.1f}%)'}
                to_remove.append(addr)
                continue
    
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
        'entry_reason': 'GMGN_V68',
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
        # Add to permanent blacklist immediately (persists across resets)
        PERM_BLACKLIST.add(addr)
        with open(PERM_BLACKLIST_FILE, 'w') as f:
            json.dump(list(PERM_BLACKLIST), f)
        return True
    except Exception as e:
        print(f"Buy error: {e}")
        return False

def scan_cycle():
    """One scan cycle"""
    global _gmgn_empty_cycle_count, _gmgn_last_alert_empty
    
    load_blacklist()
    
    tokens = get_gmgn_trending(50)
    tokens.extend(get_gmgn_new_pairs(30))
    tokens.extend(get_gmgn_pumpfun_lowcap(30))  # pump.fun ascending mcap — newest tokens
    print(f"[SCAN] Found {len(tokens)} tokens from GMGN (incl. pump.fun lowcap)")
    
    # Track empty responses
    if len(tokens) == 0:
        _gmgn_empty_cycle_count += 1
        now = time.time()
        if _gmgn_empty_cycle_count >= 5 and (now - _gmgn_last_alert_empty) > 300:
            print(f"🚨 GMGN returning empty data for {_gmgn_empty_cycle_count} consecutive cycles")
            try:
                from alert_sender import send_telegram_alert
                send_telegram_alert(f"🚨 GMGN returning empty data for {_gmgn_empty_cycle_count} cycles. Check scanner.", "SYSTEM_ALERT")
            except:
                pass
            _gmgn_last_alert_empty = now
    else:
        _gmgn_empty_cycle_count = 0
    
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
        dex_data = get_dexscreener_data(addr)
        
        # Scan
        result, reason = scan_token(token_data, dex_data, [])
        if result is None:
            # Log rejections (except age - too noisy)
            if reason and 'age' not in reason.lower()[:20]:
                print(f"   ❌ {token_data.get('symbol','?')}: {reason}")
            continue
        
        # Check if needs cooldown
        cooldown_secs = determine_cooldown(result)
        if cooldown_secs > 0:
            if add_to_cooldown(addr, token_data, result, dex_data):
                continue  # Added to cooldown, skip this cycle
            continue
        else:
            # Buy immediately (no cooldown needed)
            # Price stability check before buy: fresh data
            curr_price = result.get('entry_price', 0)
            price_at_add = curr_price
            curr_mcap = result.get('mcap', 0)
            lowest_mcap = curr_mcap  # No cooldown tracking for immediate buys
            
            if price_at_add > 0 and curr_price > 0:
                price_drop = ((price_at_add - curr_price) / price_at_add) * 100
                if price_drop > PRICE_DROP_REJECT:
                    print(f"   ⏳ {result['token']}: immediate — price down {price_drop:.1f}% since scan — rechecking next cycle")
                    continue
            
            if buy_token(addr, result):
                print(f"   🟢 BUY (immediate): {result['token']} @ ${curr_mcap:,.0f}")
                bought += 1
                if bought >= 1:
                    break  # One buy per cycle
            continue
    
    return bought

def main():
    print(f"🚀 GMGN Scanner v6.8e Started")
    print(f"   Data sources: GMGN trending + trenches + pump.fun lowcap")
    print(f"   Filters: Mcap ${MIN_MCAP:,}-${MAX_MCAP:,} | Holders {MIN_HOLDERS}+ | Dip {DIP_MIN}-{DIP_MAX}% | ATH <55% | BS {BS_RATIO_NEW}/{BS_RATIO_OLD}")
    print(f"   Momentum: h1 or 24h > +{H1_MOMENTUM_MIN}% | chg1 > +{MIN_CHG1_FOR_BUY}%")
    print(f"   Cooldown: m5>-5% → {BASE_COOLDOWN}s | +3% improvement req | deterioration>3% = reject | 2 consec rechecks")
    print(f"   🚀 PUMP RULE: chg1>+5% → 45s wait → chg1>+5%? → 30s → verify → BUY if sustained")
    
    while True:
        try:
            scan_cycle()
            check_cooldown_watch()
        except Exception as e:
            print(f"Scan error: {e}")
        time.sleep(SCAN_INTERVAL)

if __name__ == '__main__':
    main()
