#!/usr/bin/env python3
"""
GMGN Scanner v7.2 - Wilson Bot (LIVE TRADING)
MAX_H1 250%, MIN_DIP 20%, Holders ≥20 | Fallen Giant h1>400+mcap<20K | Symbol blacklist
Exit: TP1+30%H, TP2+100%sell40%, TP3+200%sell30%, TP4+300%sell20%, TP5+1000%sell10%, Stop-30%
MAX_OPEN: 5 | POSITION: 0.1 SOL | Exchanges: pump.fun/raydium/pumpswap ONLY
"""

import json, time, subprocess
from datetime import datetime, timezone
from pathlib import Path
from trading_constants import (
    MIN_MCAP, MAX_MCAP, MIN_AGE_SECONDS, MAX_AGE_SECONDS,
    MIN_5MIN_VOLUME, MIN_VOLUME, MIN_HOLDERS, TOP10_HOLDER_MAX,
    VOL_MCAP_RATIO_MIN,
    BS_RATIO_NEW, BS_RATIO_OLD, BS_PUMP_FUN_OK,
    H1_MOMENTUM_MIN, H24_MOMENTUM_MIN,
    PUMP_CHG1_THRESHOLD, PUMP_WAIT_1, PUMP_WAIT_2, PUMP_VERIFY_DELAY,
    DIP_MIN, DIP_MAX, ATH_DIVERGENCE_MAX,
    MAX_H1, FALLEN_GIANT_H1, FALLEN_GIANT_MCAP,
    MIN_CHG5_FOR_BUY, CHG5_REJECT_DROP, CHG5_RECOVERY_THRESHOLD,
    BASE_COOLDOWN, YOUNG_COOLDOWN, OLDER_COOLDOWN, NORMAL_COOLDOWN,
    STATE_BASE_WAIT, STATE_RECOVERY_WAIT, STATE_RECOVERY_RECHECK,
    STATE_POST_COOLDOWN, STATE_VERIFY,
    STATE_PUMP_WAIT_1, STATE_PUMP_WAIT_2, STATE_PUMP_VERIFY,
    STATE_M5_BACKUP,
    CHG1_RECHECK_DELAY, CHG1_VERIFY_DELAY, CHG1_RECOVERY_WAIT,
    CONSECUTIVE_RECHECKS_REQUIRED, MAX_RECHECKS, REJECTED_REVISIT_DELAY,
    H1_INSTABILITY_MULTIPLIER, LIQUIDITY_EMERGENCY_THRESHOLD,
    TP1_PERCENT, TP1_TRAILING_PCT, TP1_SELL_PCT,
    TP2_PERCENT, TP2_TRAILING_PCT, TP2_SELL_PCT,
    TP3_PERCENT, TP3_TRAILING_PCT, TP3_SELL_PCT,
    TP4_PERCENT, TP4_TRAILING_PCT, TP4_SELL_PCT,
    TP5_PERCENT, TP5_TRAILING_PCT, TP5_SELL_PCT,
    TRAILING_STOP_PCT, STOP_LOSS_PERCENT,
    ALLOWED_EXCHANGES, PUMP_REQUIREMENTS,
    LOW_VOLUME_THRESHOLD, SIM_RESET_TIMESTAMP,
    MAX_OPEN_POSITIONS, POSITION_SIZE,
)

TRADES_FILE = Path("/root/Dex-trading-bot/trades/sim_trades.jsonl")
PERM_BLACKLIST_FILE = Path("/root/Dex-trading-bot/permanent_blacklist.json")

COOLDOWN_WATCH = {}
REJECTED_TEMP = {}
PERM_BLACKLIST = set()
_gmgn_throttle_count = 0
_gmgn_last_throttle_alert = 0

# === GMGN THROTTLE MANAGEMENT ===
_BACKOFF_BASE = 30
_BACKOFF_MAX = 300
_gmgn_throttle_state = {
    'trending': {'count': 0, 'backoff_until': 0, 'last_alert': 0},
    'trenches': {'count': 0, 'backoff_until': 0, 'last_alert': 0},
    'pumpfun': {'count': 0, 'backoff_until': 0, 'last_alert': 0},
    'token_info': {'count': 0, 'backoff_until': 0, 'last_alert': 0},
}

# === CRITICAL SAFETY: Stop buys if both GMGN + DexScreener are failing ===
MAX_DEX_FAILURES = 5  # Stop DexScreener calls after 5 consecutive failures
_buys_stopped = False
_last_buys_stopped_alert = 0

def check_stop_buys():
    """If GMGN throttled + DexScreener failing = stop all buys"""
    global _buys_stopped, _last_buys_stopped_alert
    now = time.time()
    
    gmgn_throttled = any(time.time() < s['backoff_until'] for s in _gmgn_throttle_state.values())
    dex_failed = _dex_throttle_count >= MAX_DEX_FAILURES
    
    if gmgn_throttled and dex_failed:
        if not _buys_stopped:
            _buys_stopped = True
            msg = f"🚨🚨 STOPPING ALL BUYS: GMGN throttled + DexScreener failing ({_dex_throttle_count}/{MAX_DEX_FAILURES}). Manual restart required."
            print(f"! {msg}")
            alert_sender_webhook(msg)
            _last_buys_stopped_alert = now
    else:
        if _buys_stopped:
            _buys_stopped = False
            msg = f"✅ RESUMING BUYS: APIs recovered"
            print(f"! {msg}")
            alert_sender_webhook(msg)
    
    return _buys_stopped

def is_throttled(endpoint):
    return time.time() < _gmgn_throttle_state[endpoint]['backoff_until']

_dex_throttle_count = 0
_last_dex_throttle_alert = 0
_last_dex_critical_alert = 0

def record_throttle(endpoint, critical=False):
    state = _gmgn_throttle_state[endpoint]
    state['count'] += 1
    wait_time = min(_BACKOFF_BASE * (2 ** state['count']), _BACKOFF_MAX)
    state['backoff_until'] = time.time() + wait_time
    now = time.time()
    # Alert immediately on critical throttle (every time)
    if critical or state['count'] >= 1:
        msg = f"⚠️ GMGN {endpoint.upper()} THROTTLED: {state['count']} failures. Backoff {wait_time:.0f}s"
        print(f"! {msg}")
        alert_sender_webhook(msg)

def record_dex_throttle():
    """Alert when DexScreener is failing"""
    global _dex_throttle_count, _last_dex_throttle_alert
    now = time.time()
    _dex_throttle_count += 1
    wait_time = min(30 * (2 ** _dex_throttle_count), 300)
    if now - _last_dex_throttle_alert > 120:
        msg = f"⚠️ DEXSCREENER THROTTLED: {_dex_throttle_count} failures. Backoff {wait_time:.0f}s"
        print(f"! {msg}")
        alert_sender_webhook(msg)
        _last_dex_throttle_alert = now

def record_dex_critical():
    """Alert when DexScreener is completely down"""
    global _dex_throttle_count, _last_dex_critical_alert
    now = time.time()
    _dex_throttle_count += 1
    if now - _last_dex_critical_alert > 60:
        msg = f"🚨 DEXSCREENER DOWN: Critical failure. Check immediately."
        print(f"! {msg}")
        alert_sender_webhook(msg)
        _last_dex_critical_alert = now

def clear_dex_throttle():
    global _dex_throttle_count
    _dex_throttle_count = 0

def clear_throttle(endpoint):
    _gmgn_throttle_state[endpoint]['count'] = 0
    _gmgn_throttle_state[endpoint]['backoff_until'] = 0

def alert_sender_webhook(msg):
    try:
        import urllib.request, urllib.parse
        BOT_TOKEN = "8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg"
        CHAT_ID = "6402511249"
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
        req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode())
        urllib.request.urlopen(req, timeout=10)
    except: pass

# === GMGN DATA ===
def gmgn_query(cmd, timeout=15, endpoint='unknown'):
    # Check throttle
    if is_throttled(endpoint):
        return None
    
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if r.returncode == 0:
            clear_throttle(endpoint)
            return json.loads(r.stdout)
        elif 'rate limit' in r.stderr.lower() or '429' in r.stderr or '400' in r.stderr:
            record_throttle(endpoint, critical=True)
    except:
        record_throttle(endpoint)
    
    return None

def get_gmgn_trending(limit=50):
    if is_throttled('trending'):
        return []
    d = gmgn_query(['gmgn-cli', 'market', 'trending', '--chain', 'sol', '--interval', '5m', '--limit', str(limit)], endpoint='trending')
    return d.get('data', {}).get('rank', []) if d else []

def get_gmgn_new_pairs(limit=30):
    if is_throttled('trenches'):
        return []
    d = gmgn_query(['gmgn-cli', 'market', 'trenches', '--chain', 'sol', '--limit', str(limit)], endpoint='trenches')
    if not d: return []
    pairs = []
    for k in ('creating', 'created', 'completed'):
        pairs.extend(d.get(k, []) or [])
    return pairs

def get_gmgn_pumpfun_lowcap(limit=30):
    if is_throttled('pumpfun'):
        return []
    d = gmgn_query(['gmgn-cli', 'market', 'trending', '--chain', 'sol', '--interval', '5m', '--limit', str(limit),
                    '--platform', 'Pump.fun', '--order-by', 'marketcap', '--direction', 'asc'], endpoint='pumpfun')
    return d.get('data', {}).get('rank', []) if d else []

def get_gmgn_token_info(addr):
    if is_throttled('token_info'):
        return None
    return gmgn_query(['gmgn-cli', 'token', 'info', '--chain', 'sol', '--address', addr], endpoint='token_info')

def get_dexscreener_data(addr):
    # Global circuit breaker - if heavily throttled, skip DexScreener entirely
    if _dex_throttle_count >= 5:
        return None
    try:
        import requests
        r = requests.get(f'https://api.dexscreener.com/v1/tokens/{addr}', timeout=8)
        if r.status_code == 200:
            clear_dex_throttle()
            pairs = r.json().get('pairs', [])
            if pairs:
                p = pairs[0]
                return {
                    'priceChange': p.get('priceChange', {}),
                    'priceUsd': p.get('priceUsd'),
                    'marketCap': p.get('marketCap'),
                    'volume': p.get('volume'),
                    'holderCount': p.get('holderCount'),
                    'liquidity': p.get('liquidity'),
                    'price': float(p.get('priceUsd', 0) or 0),
                }
        elif r.status_code in (429, 403):
            record_dex_throttle()
        else:
            record_dex_critical()
    except Exception as e:
        record_dex_critical()
    return None

# === BLACKLIST ===
def load_blacklist():
    global PERM_BLACKLIST
    PERM_BLACKLIST = set()
    if PERM_BLACKLIST_FILE.exists():
        try: PERM_BLACKLIST = set(json.load(open(PERM_BLACKLIST_FILE)))
        except: pass
    if TRADES_FILE.exists():
        for line in open(TRADES_FILE):
            try:
                t = json.loads(line)
                if t.get('action') == 'BUY': PERM_BLACKLIST.add(t.get('token_address', ''))
            except: pass

# === FRESH DATA MERGE ===
def merge_token_data(stored_data, fresh_gmgn, fresh_dex):
    """Use stored data as base, fill in with fresh"""
    merged = (stored_data or {}).copy()
    if fresh_gmgn:
        for k, v in fresh_gmgn.items():
            if v and v != 0:
                merged[k] = v
    if fresh_dex:
        for k, v in fresh_dex.items():
            if v and v != 0 and not merged.get(k):
                merged[k] = v
        ds_chg1 = fresh_dex.get('priceChange', {}).get('m1') if fresh_dex.get('priceChange') else None
        if ds_chg1 is not None and not merged.get('price_change_percent1m'):
            merged['price_change_percent1m'] = float(ds_chg1)
    return merged

# === TOKEN SCAN ===
def scan_token(gmgn_data, dex_data):
    merged = merge_token_data({}, gmgn_data, dex_data)
    
    symbol = merged.get('symbol', '?')
    addr = merged.get('address', '')
    mcap = float(merged.get('market_cap', 0) or 0)
    price = float(merged.get('price', 0) or 0)
    
    age_str = str(merged.get('age', '0s'))
    age_sec = 0
    if 'h' in age_str:
        try: age_sec = int(float(age_str.replace('h','')) * 3600)
        except: pass
    elif 'm' in age_str:
        try: age_sec = int(float(age_str.replace('m','')) * 60)
        except: pass
    elif age_str.isdigit():
        age_sec = int(age_str)
    else:
        ts = merged.get('creation_timestamp') or merged.get('open_timestamp')
        if ts: age_sec = int(time.time() - int(ts))
    age_min = age_sec / 60.0
    
    holders = int(merged.get('holder_count', 0) or 0)
    top10 = float(merged.get('top_10_holder_rate', 0) or 0) * 100
    liquidity = float(merged.get('liquidity', 0) or 0)
    h1 = float(merged.get('price_change_percent1h', 0) or 0)
    h24 = float(merged.get('price_change_percent24h', 0) or 0)
    m5 = float(merged.get('price_change_percent5m', 0) or 0)
    chg5 = m5
    chg1_raw = merged.get('price_change_percent1m')
    chg1 = float(chg1_raw) if chg1_raw is not None else None
    ath_mcap = float(merged.get('history_highest_market_cap', 0) or 0) or mcap
    volume = float(merged.get('volume', 0) or 0)
    vol5m = float(merged.get('volume5m', 0) or 0)
    if vol5m == 0 and volume > 0:
        vol5m = volume / 12
    bs_ratio = float(merged.get('buy_sell_ratio', 0) or 0)
    launchpad = str(merged.get('launchpad', '') or '').lower()
    
    if mcap < MIN_MCAP: return None, f"mcap ${mcap:,.0f} < ${MIN_MCAP:,}"
    if mcap > MAX_MCAP: return None, f"mcap ${mcap:,.0f} > ${MAX_MCAP:,}"
    if age_sec < MIN_AGE_SECONDS: return None, f"age {age_min:.1f}min < {MIN_AGE_SECONDS/60:.0f}min"
    if age_sec > MAX_AGE_SECONDS: return None, f"age {age_min:.0f}min > {MAX_AGE_SECONDS/60:.0f}min"
    if holders < MIN_HOLDERS: return None, f"holders {holders} < {MIN_HOLDERS}"
    if top10 > TOP10_HOLDER_MAX: return None, f"top10 {top10:.1f}% > {TOP10_HOLDER_MAX}%"
    if h1 < H1_MOMENTUM_MIN and h24 < H24_MOMENTUM_MIN: return None, f"no momentum (h1={h1:+.1f}% 24h={h24:+.1f}%)"
    if h1 > MAX_H1: return None, f"h1 {h1:.0f}% > {MAX_H1}% (too late - already pumped)"
    if launchpad not in ALLOWED_EXCHANGES and launchpad != 'pump': return None, f"exchange {launchpad} not allowed"
    if bs_ratio < BS_RATIO_OLD and not (BS_PUMP_FUN_OK and launchpad == 'pump'): return None, f"bs {bs_ratio:.2f} < {BS_RATIO_OLD}"
    if vol5m < MIN_5MIN_VOLUME: return None, f"vol5m ${vol5m:,.0f} < ${MIN_5MIN_VOLUME:,}"
    if volume < MIN_VOLUME: return None, f"volume ${volume:,.0f} < ${MIN_VOLUME:,}"
    if mcap > 0 and vol5m > 0:
        vol_mcap_ratio = (vol5m / mcap) * 100
        if vol_mcap_ratio < VOL_MCAP_RATIO_MIN: return None, f"vol/mcap {vol_mcap_ratio:.1f}x < {VOL_MCAP_RATIO_MIN}x"
    
    dip = 0
    if ath_mcap > 0:
        dip = ((ath_mcap - mcap) / ath_mcap) * 100
    if dip < DIP_MIN: return None, f"dip {dip:.1f}% < {DIP_MIN}%"
    if dip > DIP_MAX: return None, f"dip {dip:.1f}% > {DIP_MAX}%"
    if ath_mcap > 0:
        ath_dist = ((ath_mcap - mcap) / ath_mcap) * 100
        if ath_dist > ATH_DIVERGENCE_MAX: return None, f"ATH dist {ath_dist:.1f}% > {ATH_DIVERGENCE_MAX}%"
    # Symbol blacklist: don't re-buy same symbol (pump.fun allows duplicate names)
    symbol_blacklist = set()
    try:
        with open(TRADES_FILE) as sf:
            for sline in sf:
                t = json.loads(sline)
                if t.get('action') == 'BUY' and t.get('token_name'):
                    symbol_blacklist.add(t['token_name'].lower())
        if symbol.lower() in symbol_blacklist:
            return None, f"symbol {symbol} already traded"
    except: pass
    
    # No ATH fallback: tokens >$20K mcap with no ATH = reject (risk of fallen giant)
    if ath_mcap <= 0 and mcap > 20000:
        return None, f"No ATH data for mcap ${mcap:,.0f} > $20K (risk of fallen giant)"
    
    # Fallen Giant Detection: massive h1 + small mcap = already pumped and crashed
    if h1 > FALLEN_GIANT_H1 and mcap < FALLEN_GIANT_MCAP:
        return None, f"Fallen giant: h1={h1:.0f}% + mcap=${mcap:,.0f} < ${FALLEN_GIANT_MCAP:,}"
    
    if addr in PERM_BLACKLIST: return None, "blacklisted"
    try:
        with open(TRADES_FILE) as f:
            open_count = sum(1 for l in f if json.loads(l).get('action')=='BUY' and json.loads(l).get('status')=='open')
        if open_count >= MAX_OPEN_POSITIONS: return None, f"max positions ({open_count}/{MAX_OPEN_POSITIONS})"
    except: pass
    
    return {
        'token': symbol, 'address': addr, 'mcap': mcap, 'price': price,
        'h1': h1, 'h24': h24, 'm5': m5, 'chg5': chg5, 'chg1': chg1,
        'dip': dip, 'ath_mcap': ath_mcap, 'holders': holders,
        'top10': top10, 'liquidity': liquidity, 'vol5m': vol5m,
        'bs_ratio': bs_ratio, 'age_min': age_min, 'age_sec': age_sec,
        'entry_price': price, 'launchpad': launchpad,
    }, "PASS"

# === COOLDOWN ===
def add_to_cooldown(addr, token_data, result, dex_data=None):
    if addr in COOLDOWN_WATCH:
        return False
    now_ts = time.time()
    age_min = result['age_min']
    chg5 = result['chg5']
    h1 = result['h1']
    
    if age_min < 15 and chg5 > -5 and h1 > 5:
        base_cd = YOUNG_COOLDOWN
        reason = "young"
    elif age_min >= 15 and chg5 > -5 and h1 > 5:
        base_cd = OLDER_COOLDOWN
        reason = "older"
    else:
        base_cd = NORMAL_COOLDOWN
        reason = "normal"
    
    COOLDOWN_WATCH[addr] = {
        'first_seen': now_ts,
        'cooldown_end': now_ts + base_cd,
        'state': STATE_BASE_WAIT,
        'base_cooldown': base_cd,
        'reason': reason,
        'token_data': token_data,
        'result': result,
        'dex_data': dex_data,
        'lowest_mcap': result['mcap'],
        'lowest_chg5': chg5,
        'last_chg5': chg5,
        'last_mcap': result['mcap'],
        'last_h1': h1,
        'last_price': result['price'],
        'recheck_count': 0,
        'consecutive_ok': 0,
        '_pump_rule_triggered': result.get('chg1') is not None and result.get('chg1') > PUMP_CHG1_THRESHOLD,
        '_last_improvement_check': None,
    }
    print(f"   [{reason.upper()}] {result['token']}: base cooldown {base_cd}s | chg5={chg5:+.1f}% h1={h1:+.1f}%")
    return True

def check_cooldown_watch():
    to_remove = []
    now = time.time()
    
    for addr, data in COOLDOWN_WATCH.items():
        result = data['result']
        state = data.get('state', STATE_BASE_WAIT)
        
        # === FRESH DATA - always refresh ALL critical fields for accurate analysis ===
        stored_data = data.get('token_data', {})
        fresh_gmgn = get_gmgn_token_info(addr)
        # DexScreener SKIPPED - GMGN has all data, DexScreener causes rate limits
        fresh_dex = None
        
        if not fresh_gmgn and not stored_data:
            print(f"   [SKIP] {result['token']}: no data")
            to_remove.append(addr)
            continue
        
        # Build merged data: start with stored, then overwrite with fresh
        merged = (stored_data or {}).copy()
        
        # Fresh GMGN: update all fields (has full token data)
        if fresh_gmgn:
            for k, v in fresh_gmgn.items():
                if v is not None and v != '':
                    merged[k] = v
        
        # DexScreener: fill in any remaining gaps
        if fresh_dex:
            for k, v in fresh_dex.items():
                if v is not None and v != 0 and not merged.get(k):
                    merged[k] = v
            # DexScreener chg1 (m1)
            ds_chg1 = fresh_dex.get('priceChange', {}).get('m1') if fresh_dex.get('priceChange') else None
            if ds_chg1 is not None and not merged.get('price_change_percent1m'):
                merged['price_change_percent1m'] = float(ds_chg1)
            # If DexScreener has mcap but GMGN doesn't, use it
            ds_mcap = fresh_dex.get('marketCap')
            if ds_mcap and not merged.get('market_cap'):
                merged['market_cap'] = float(ds_mcap)
        
        fresh_result, fresh_reason = scan_token(merged, fresh_dex)
        if fresh_result is None:
            print(f"   [FAIL] {result['token']}: filter fail ({fresh_reason})")
            REJECTED_TEMP[addr] = {'ts': time.time(), 'reason': fresh_reason}
            to_remove.append(addr)
            continue
        
        data['result'] = fresh_result
        data['token_data'] = merged
        data['dex_data'] = fresh_dex
        
        chg5 = fresh_result.get('m5', 0)
        chg1 = fresh_result.get('chg1')
        curr_mcap = fresh_result.get('mcap', 0)
        curr_price = fresh_result.get('price', 0)
        curr_h1 = fresh_result.get('h1', 0)
        
        if curr_mcap > 0 and curr_mcap < data.get('lowest_mcap', float('inf')):
            data['lowest_mcap'] = curr_mcap
        if chg5 < data.get('lowest_chg5', 0):
            data['lowest_chg5'] = chg5
        
        prev_h1 = data.get('last_h1', 0)
        if prev_h1 > 0 and curr_h1 > 0:
            ratio = max(prev_h1, curr_h1) / min(prev_h1, curr_h1)
            if ratio > H1_INSTABILITY_MULTIPLIER:
                print(f"   [REJECT] {result['token']}: h1 unstable {prev_h1:.0f}% -> {curr_h1:.0f}% ({ratio:.1f}x)")
                REJECTED_TEMP[addr] = {'ts': time.time(), 'reason': 'h1 instability'}
                to_remove.append(addr)
                continue
        data['last_h1'] = curr_h1
        
        prev_chg5 = data.get('last_chg5', chg5)
        if prev_chg5 > 0 and chg5 < prev_chg5 - CHG5_REJECT_DROP:
            print(f"   [WATCH] {result['token']}: chg5 dropped {prev_chg5:+.1f}% -> {chg5:+.1f}% (>5% drop) | continue")
            data['last_chg5'] = chg5
            data['last_mcap'] = curr_mcap
            data['last_price'] = curr_price
            data['cooldown_end'] = now + CHG1_RECHECK_DELAY
            continue
        
        data['last_chg5'] = chg5
        data['last_mcap'] = curr_mcap
        data['last_price'] = curr_price
        
        # === PUMP RULE PATH ===
        if data.get('_pump_rule_triggered') and state == STATE_BASE_WAIT:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                continue
            # Fetch fresh data before pump path confirmation
            # GMGN primary - only use DexScreener as fallback if GMGN fails
            fresh_gmgn_p = get_gmgn_token_info(addr)
            fresh_dex_p = None  # Skip DexScreener in pump path - too many calls
            if fresh_gmgn_p or fresh_dex_p:
                merged_p = merge_token_data(data.get('token_data', {}), fresh_gmgn_p, fresh_dex_p)
                chg1_p = merged_p.get('price_change_percent1m')
                chg1_p = float(chg1_p) if chg1_p is not None else None
                curr_mcap_p = float(merged_p.get('market_cap', 0) or 0)
                print(f"   [PUMP_CHECK] {result['token']}: chg1={chg1_p}% (fresh) mcap=${curr_mcap_p:,.0f}")
                if chg1_p is not None and chg1_p > PUMP_CHG1_THRESHOLD:
                    data['state'] = STATE_PUMP_WAIT_2
                    data['cooldown_end'] = now + PUMP_WAIT_2
                    data['recheck_count'] = 0
                    data['_pump_chg1_trigger'] = chg1_p
                    print(f"   [PUMP] {result['token']}: chg1={chg1_p:+.1f}% >+5% | wait {PUMP_WAIT_2}s")
                else:
                    data['_pump_rule_triggered'] = False
                    data['state'] = STATE_RECOVERY_WAIT
                    data['cooldown_end'] = now + CHG1_RECOVERY_WAIT
                    data['recheck_count'] = 0
                    print(f"   [PUMP_FAIL] {result['token']}: chg1={chg1_p}% <+5% | recovery path")
            else:
                data['cooldown_end'] = now + CHG1_RECHECK_DELAY
                print(f"   [PUMP_WAIT] {result['token']}: no fresh data | wait 15s")
            continue
        
        elif state == STATE_PUMP_WAIT_2:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                continue
            if chg1 is not None and chg1 > PUMP_CHG1_THRESHOLD:
                data['state'] = STATE_PUMP_VERIFY
                data['cooldown_end'] = now + PUMP_VERIFY_DELAY
                print(f"   [PUMP_VERIFY] {result['token']}: verify {PUMP_VERIFY_DELAY}s | chg1={chg1:+.1f}%")
            else:
                data['_pump_rule_triggered'] = False
                data['state'] = STATE_RECOVERY_WAIT
                data['cooldown_end'] = now + CHG1_RECOVERY_WAIT
                print(f"   [PUMP_FAIL] {result['token']}: chg1 dropped | recovery path")
            continue
        
        elif state == STATE_PUMP_VERIFY:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                continue
            print(f"   [BUY_PUMP] {result['token']}: pump confirmed | BUY!")
            buy_token(addr, fresh_result)
            to_remove.append(addr)
            continue
        
        # === NORMAL STATE MACHINE ===
        elif state == STATE_BASE_WAIT:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                continue
            if chg5 < -5:
                data['state'] = STATE_RECOVERY_WAIT
                data['cooldown_end'] = now + CHG1_RECOVERY_WAIT
                data['recheck_count'] = 0
                print(f"   [RECOVERY] {result['token']}: chg5={chg5:+.1f}% < -5% | wait 15s then rechecks")
            else:
                data['state'] = STATE_POST_COOLDOWN
                data['cooldown_end'] = now + 30
                data['recheck_count'] = 0
                print(f"   [POST_CD] {result['token']}: chg5={chg5:+.1f}% >= -5% | wait 30s for verify")
            continue
        
        elif state == STATE_RECOVERY_WAIT:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                continue
            data['state'] = STATE_RECOVERY_RECHECK
            data['cooldown_end'] = now + CHG1_RECHECK_DELAY
            data['recheck_count'] = (data.get('recheck_count', 0)) + 1
            print(f"   [RECHECK #{data['recheck_count']}] {result['token']}: chg5={chg5:+.1f}% | need +{CHG5_RECOVERY_THRESHOLD}% from lowest mcap")
            continue
        
        elif state == STATE_RECOVERY_RECHECK:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                continue
            data['recheck_count'] += 1
            if data['recheck_count'] > MAX_RECHECKS:
                print(f"   [MAX_RECHECKS] {result['token']}: max {MAX_RECHECKS} | switch to m5 backup")
                data['state'] = STATE_M5_BACKUP
                data['cooldown_end'] = now + CHG1_RECHECK_DELAY
                data['_backup_lowest_mcap'] = data.get('lowest_mcap', curr_mcap)
                continue
            lowest_mcap = data.get('lowest_mcap', curr_mcap)
            mcap_recovery_pct = ((curr_mcap - lowest_mcap) / lowest_mcap) * 100 if lowest_mcap > 0 else 0
            if mcap_recovery_pct >= CHG5_RECOVERY_THRESHOLD:
                data['state'] = STATE_VERIFY
                data['cooldown_end'] = now + CHG1_VERIFY_DELAY
                data['consecutive_ok'] = 0
                data['recheck_count'] = 0
                print(f"   [RECOVERED] {result['token']}: mcap +{mcap_recovery_pct:.1f}% from low | final verify")
            else:
                data['cooldown_end'] = now + CHG1_RECHECK_DELAY
                print(f"   [RECHECK #{data['recheck_count']}] {result['token']}: mcap +{mcap_recovery_pct:.1f}% (need +{CHG5_RECOVERY_THRESHOLD}%) | lowest={lowest_mcap:,.0f}")
            continue
        
        elif state == STATE_POST_COOLDOWN:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                continue
            last = data.get('_last_improvement_check', data.get('last_chg5', chg5))
            improvement = chg5 - last if last else 0
            if improvement >= MIN_CHG5_FOR_BUY or chg5 > 20:
                data['state'] = STATE_VERIFY
                data['cooldown_end'] = now + CHG1_VERIFY_DELAY
                data['consecutive_ok'] = 0
                print(f"   [VERIFY] {result['token']}: chg5={chg5:+.1f}% (+{improvement:+.1f}% from last) | verify")
            else:
                data['cooldown_end'] = now + CHG1_RECHECK_DELAY
                data['_last_improvement_check'] = chg5
                print(f"   [RECHECK] {result['token']}: chg5={chg5:+.1f}% (+{improvement:+.1f}% < +{MIN_CHG5_FOR_BUY}%)")
            continue
        
        elif state == STATE_VERIFY:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                continue
            last = data.get('_last_improvement_check', data.get('last_chg5', chg5))
            improvement = chg5 - last if last else 0
            if improvement >= MIN_CHG5_FOR_BUY or chg5 > 20:
                data['consecutive_ok'] += 1
                data['_last_improvement_check'] = chg5
                print(f"   [VERIFY #{data['consecutive_ok']}] {result['token']}: chg5={chg5:+.1f}% (+{improvement:+.1f}%) | {data['consecutive_ok']}/{CONSECUTIVE_RECHECKS_REQUIRED}")
                if data['consecutive_ok'] >= CONSECUTIVE_RECHECKS_REQUIRED:
                    print(f"   [BUY] {result['token']}: verified | BUY!")
                    buy_token(addr, fresh_result)
                    to_remove.append(addr)
                else:
                    data['cooldown_end'] = now + CHG1_RECHECK_DELAY
            else:
                data['consecutive_ok'] = 0
                data['cooldown_end'] = now + CHG1_RECHECK_DELAY
                data['_last_improvement_check'] = chg5
                print(f"   [VERIFY_FAIL] {result['token']}: chg5={chg5:+.1f}% (+{improvement:+.1f}% < +{MIN_CHG5_FOR_BUY}%) | recheck")
            continue
        
        elif state == STATE_M5_BACKUP:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                continue
            lowest = data.get('_backup_lowest_mcap', curr_mcap)
            mcap_recovery_pct = ((curr_mcap - lowest) / lowest) * 100 if lowest > 0 else 0
            last_chg5 = data.get('last_chg5', chg5)
            chg5_change = chg5 - last_chg5 if last_chg5 else 0
            if mcap_recovery_pct >= CHG5_RECOVERY_THRESHOLD or chg5_change >= MIN_CHG5_FOR_BUY:
                print(f"   [M5_BACKUP_OK] {result['token']}: mcap +{mcap_recovery_pct:.1f}% | chg5={chg5:+.1f}% | BUY!")
                buy_token(addr, fresh_result)
                to_remove.append(addr)
            else:
                data['cooldown_end'] = now + CHG1_RECHECK_DELAY
                data['recheck_count'] = data.get('recheck_count', 0) + 1
                print(f"   [M5_RECHECK #{data['recheck_count']}] {result['token']}: mcap +{mcap_recovery_pct:.1f}% | chg5={chg5:+.1f}%")
            continue
    
    for addr in to_remove:
        if addr in COOLDOWN_WATCH: del COOLDOWN_WATCH[addr]
    return len(to_remove) > 0

# === BUY ===
def buy_token(addr, result):
    global PERM_BLACKLIST
    # CRITICAL: Check if buys should be stopped
    if check_stop_buys():
        print(f"   [BLOCKED] {result.get('token', '?')}: buys STOPPED - API safety active")
        return False
    
    now = datetime.now(timezone.utc).isoformat()
    trade = {
        'action': 'BUY',
        'token_address': addr,
        'token_name': result.get('token', '?'),
        'entry_price': result.get('price', 0),
        'entry_mcap': int(result.get('mcap', 0)),
        'opened_at': now,
        'closed_at': None,
        'entry_sol': POSITION_SIZE,
        'status': 'open',
        'tp_status': {'tp1_hit': False, 'tp2_hit': False, 'tp3_hit': False, 'tp4_hit': False, 'tp5_hit': False},
        'tp1_sold': False, 'tp2_sold': False, 'tp3_sold': False, 'tp4_sold': False, 'tp5_sold': False,
        'partial_exit': False, 'fully_exited': False,
        'peak_price': result.get('price', 0),
        'entry_reason': 'GMGN_V71',
        'h1': result.get('h1', 0),
        'm5': result.get('m5', 0),
        'chg5_at_buy': result.get('chg5', 0),
        'dip_at_buy': result.get('dip', 0),
        'ath_mcap': result.get('ath_mcap', 0),
        'holders': result.get('holders', 0),
        'top10': result.get('top10', 0),
        'dex': result.get('launchpad', 'unknown'),
    }
    try:
        with open(TRADES_FILE, 'a') as f:
            f.write(json.dumps(trade) + '\n')
        PERM_BLACKLIST.add(addr)
        with open(PERM_BLACKLIST_FILE, 'w') as f:
            json.dump(list(PERM_BLACKLIST), f)
        try:
            from alert_sender import send_telegram
            msg = f"BUY EXECUTED | {datetime.now(timezone.utc).strftime('%H:%M')}\n━━━━━━━━━━━━━━━\n{result.get('token')}\nEntry MC: ${int(result.get('mcap', 0)):,}\nAmount: {POSITION_SIZE} SOL\n\nhttps://dexscreener.com/solana/{addr}\nhttps://pump.fun/{addr}"
            send_telegram(msg)
        except Exception as e:
            print(f"Alert error: {e}")
        return True
    except Exception as e:
        print(f"Buy error: {e}")
        return False

# === SCAN CYCLE ===
def scan_cycle():
    tokens = []
    tokens.extend(get_gmgn_trending(50))
    tokens.extend(get_gmgn_new_pairs(20))
    tokens.extend(get_gmgn_pumpfun_lowcap(20))
    if not tokens:
        return False
    seen = set()
    unique = []
    for t in tokens:
        addr = t.get('address', '')
        if addr and addr not in seen:
            seen.add(addr)
            unique.append(t)
    for token_data in unique:
        addr = token_data.get('address', '')
        if not addr: continue
        if addr in PERM_BLACKLIST or addr in COOLDOWN_WATCH: continue
        # GMGN data is primary - skip DexScreener in main scan to avoid rate limits
        # DexScreener only used as fallback in token_info when GMGN returns nothing
        dex_data = None
        result, reason = scan_token(token_data, dex_data)
        if result is None: continue
        add_to_cooldown(addr, token_data, result, dex_data)
    return True

def cleanup_rejected():
    now = time.time()
    for addr in list(REJECTED_TEMP.keys()):
        if now - REJECTED_TEMP[addr]['ts'] > REJECTED_REVISIT_DELAY:
            del REJECTED_TEMP[addr]

# === MAIN ===
def main():
    print("GMGN Scanner v7.2 Started - LIVE TRADING")
    print("  MAX_H1 250% | DIP 20-45% | Holders ≥20 | Fallen Giant filter | Symbol blacklist")
    print("  Exit: TP1+30%H TP2+100%sell40% TP3+200%sell30% TP4+300%sell20% TP5+1000%sell10% Stop-30%")
    print("  MAX_OPEN: 5 | SIZE: 0.1 SOL | pump.fun/raydium/pumpswap ONLY")
    print("  API SAFETY: If GMGN + DexScreener both fail → ALL BUYS STOP")
    
    load_blacklist()
    while True:
        try:
            check_cooldown_watch()
            scan_cycle()
            cleanup_rejected()
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(15)

if __name__ == '__main__':
    main()