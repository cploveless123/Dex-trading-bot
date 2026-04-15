#!/usr/bin/env python3
"""
GMGN Scanner v7.3 - Wilson Bot
Full v7.3 strategy: pump rule, cooldown rules, deterioration, instability
"""
import subprocess, json, time, sys, os
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, '/root/Dex-trading-bot')
from trading_constants import *

BOT_TOKEN = '8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg'
CHAT_ID = '6402511249'
PUMP_REQUIREMENTS = {'pump': 'pump', 'pumpswap': 'pump', 'raydium': None}

# State machine states
STATE_BASE_WAIT = 'BASE_WAIT'
STATE_PUMP_WAIT_1 = 'PUMP_WAIT_1'  # 45s wait after pump trigger
STATE_PUMP_WAIT_2 = 'PUMP_WAIT_2'  # 30s wait
STATE_PUMP_VERIFY = 'PUMP_VERIFY'   # 15s final verify
STATE_RECOVERY_WAIT = 'RECOVERY_WAIT'  # 15s rechecks for deterioration
STATE_POST_COOLDOWN = 'POST_COOLDOWN'  # 15s after cooldown ends

# Cooldown tracking
COOLDOWN_WATCH = {}  # addr -> {state, cooldown_end, token_data, result, recheck_count, pump_rule_triggered, chg5_prev, h1_prev, entry_conditions}
REJECTED_TEMP = {}   # addr -> {ts, reason}

# GMGN throttle management
_gmgn_throttle_state = {
    'trending': {'count': 0, 'backoff_until': 0},
    'trenches': {'count': 0, 'backoff_until': 0},
    'pumpfun': {'count': 0, 'backoff_until': 0},
    'token_info': {'count': 0, 'backoff_until': 0},
}
_BACKOFF_BASE = 30
_BACKOFF_MAX = 300

_dex_throttle_count = 0
_last_dex_throttle_alert = 0
_last_dex_critical_alert = 0
_buys_stopped = False
_last_buys_stopped_alert = 0

PERM_BLACKLIST = set()
try:
    with open(PERM_BLACKLIST_FILE) as f:
        PERM_BLACKLIST = set(json.load(f))
except:
    pass

def is_throttled(endpoint):
    return time.time() < _gmgn_throttle_state[endpoint]['backoff_until']

def record_throttle(endpoint):
    state = _gmgn_throttle_state[endpoint]
    state['count'] += 1
    wait_time = min(_BACKOFF_BASE * (2 ** state['count']), _BACKOFF_MAX)
    state['backoff_until'] = time.time() + wait_time
    msg = f"⚠️ GMGN {endpoint.upper()} THROTTLED: {state['count']} failures. Backoff {wait_time:.0f}s"
    print(f"! {msg}")
    alert_sender_webhook(msg)

def clear_throttle(endpoint):
    _gmgn_throttle_state[endpoint] = {'count': 0, 'backoff_until': 0, 'last_alert': 0}

def check_stop_buys():
    global _buys_stopped, _last_buys_stopped_alert
    now = time.time()
    gmgn_throttled = any(time.time() < s['backoff_until'] for s in _gmgn_throttle_state.values())
    if gmgn_throttled and _dex_throttle_count >= 5:
        if not _buys_stopped:
            _buys_stopped = True
            msg = f"🚨🚨 STOPPING ALL BUYS: GMGN throttled + DexScreener failing"
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

def get_gmgn_trending(limit=50):
    if is_throttled('trending'):
        return []
    r = subprocess.run(['gmgn-cli', 'market', 'trending', '--chain', 'sol', '--interval', '5m', '--limit', str(limit)],
                      capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        record_throttle('trending')
        return []
    try:
        data = json.loads(r.stdout)
        return data.get('data', {}).get('rank', [])
    except:
        return []

def get_gmgn_trenches(limit=20):
    if is_throttled('trenches'):
        return []
    r = subprocess.run(['gmgn-cli', 'market', 'trending', '--chain', 'sol', '--interval', '5m', '--limit', str(limit), '--order-by', 'marketcap', '--direction', 'asc'],
                      capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        record_throttle('trenches')
        return []
    try:
        data = json.loads(r.stdout)
        return data.get('data', {}).get('rank', [])
    except:
        return []

def get_gmgn_pumpfun_lowcap(limit=20):
    if is_throttled('pumpfun'):
        return []
    r = subprocess.run(['gmgn-cli', 'market', 'trending', '--chain', 'sol', '--interval', '5m', '--limit', str(limit),
                      '--platform', 'Pump.fun', '--order-by', 'marketcap', '--direction', 'asc'],
                      capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        record_throttle('pumpfun')
        return []
    try:
        data = json.loads(r.stdout)
        return data.get('data', {}).get('rank', [])
    except:
        return []

def get_gmgn_token_info(addr):
    if is_throttled('token_info'):
        return None
    r = subprocess.run(['gmgn-cli', 'token', 'info', '--chain', 'sol', '--address', addr],
                      capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        record_throttle('token_info')
        return None
    try:
        return json.loads(r.stdout)
    except:
        return None

def alert_sender_webhook(msg):
    try:
        import urllib.request, urllib.parse
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
        req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode())
        urllib.request.urlopen(req, timeout=10)
    except:
        pass

def get_open_position_count():
    count = 0
    try:
        with open(TRADES_FILE) as f:
            for line in f:
                t = json.loads(line)
                if t.get('action') == 'BUY' and t.get('status') == 'open':
                    count += 1
    except:
        pass
    return count

def parse_age(age_str):
    """Convert age string to seconds"""
    if not age_str:
        return 0
    try:
        if 'h' in age_str:
            return int(float(age_str.replace('h','')) * 3600)
        elif 'm' in age_str:
            return int(float(age_str.replace('m','')) * 60)
        elif 's' in age_str:
            return int(float(age_str.replace('s','')))
        else:
            return int(float(age_str))
    except:
        return 0

def scan_token(token_data, reason_if_fail=None):
    """Returns (result_dict, fail_reason)"""
    symbol = token_data.get('symbol', '?')
    addr = token_data.get('address', '')
    mcap = float(token_data.get('market_cap', 0) or 0)
    price = float(token_data.get('price', 0) or 0)
    h1 = float(token_data.get('price_change_percent1h', 0) or 0)
    h24 = float(token_data.get('price_change_percent24h', 0) or 0)
    chg5 = float(token_data.get('price_change_percent5m', 0) or 0)
    holders = int(token_data.get('holder_count', 0) or 0)
    top10 = float(token_data.get('top10holderpercent', 0) or 0)
    liquidity = float(token_data.get('liquidity', 0) or 0)
    age_sec = parse_age(str(token_data.get('age', '0s')))
    ath_mcap = float(token_data.get('history_highest_market_cap', 0) or 0)
    volume = float(token_data.get('volume', 0) or 0)
    vol_mcap_ratio = volume / mcap if mcap > 0 else 0
    bs_ratio = float(token_data.get('bs_change24hpercent', 0) or 0)
    launchpad = token_data.get('launchpad', '')
    pair_address = token_data.get('pair_address', '')

    # Mcap check
    if mcap < MIN_MCAP: return None, f"mcap ${mcap:,.0f} < ${MIN_MCAP:,}"
    if mcap > MAX_MCAP: return None, f"mcap ${mcap:,.0f} > ${MAX_MCAP:,}"

    # Age check
    if age_sec < MIN_AGE_SECONDS: return None, f"age {age_sec}s < {MIN_AGE_SECONDS}s"
    if age_sec > MAX_AGE_SECONDS: return None, f"age {age_sec}s > {MAX_AGE_SECONDS}s"

    # Holders check
    if holders < MIN_HOLDERS: return None, f"holders {holders} < {MIN_HOLDERS}"

    # Top 10 check
    if top10 >= TOP10_HOLDER_MAX: return None, f"top10 {top10:.1f}% >= {TOP10_HOLDER_MAX}%"

    # Momentum check
    if h1 < H1_MOMENTUM_MIN and h24 < H24_MOMENTUM_MIN:
        return None, f"no momentum h1={h1:+.1f}% 24h={h24:+.1f}%"

    # chg1 check (no falling knife)
    chg1 = float(token_data.get('price_change_percent1m', 0) or 0)
    if chg1 < CHG1_MIN:
        return None, f"chg1 {chg1:.1f}% < {CHG1_MIN}% (falling knife)"

    # Pump rule trigger: chg5 > +20%
    pump_triggered = chg5 > PUMP_CHG5_THRESHOLD

    # Dip from local peak
    dip = 0
    if ath_mcap > 0:
        dip = ((ath_mcap - mcap) / ath_mcap) * 100
        if dip > ATH_DIVERGENCE_MAX:
            return None, f"ATH dist {dip:.1f}% > {ATH_DIVERGENCE_MAX}%"
        # If NOT in pump rule, must be in dip range
        if not pump_triggered and (dip < DIP_MIN or dip > DIP_MAX):
            return None, f"dip {dip:.1f}% not in {DIP_MIN}-{DIP_MAX}%"
    elif mcap > 25000:
        return None, f"No ATH data for mcap ${mcap:,.0f} > $25K"

    # Fallen Giant: h1 > +500% AND mcap < $25K
    if h1 > 500 and mcap < 25000:
        return None, f"Fallen giant: h1={h1:.0f}% + mcap=${mcap:,.0f} < $25K"

    # Volume check
    if volume < MIN_VOLUME: return None, f"vol ${volume:,.0f} < ${MIN_VOLUME:,}"
    vol_5m = float(token_data.get('volume5m', 0) or 0)
    if vol_5m < MIN_5MIN_VOLUME: return None, f"5m vol ${vol_5m:,.0f} < ${MIN_5MIN_VOLUME:,}"

    # Vol/Mcap ratio
    if vol_mcap_ratio < VOL_MCAP_RATIO_MIN: return None, f"vol/mcap {vol_mcap_ratio:.2f} < {VOL_MCAP_RATIO_MIN}"

    # Buy/Sell ratio
    if not BS_PUMP_FUN_OK or launchpad != 'pump':
        if age_sec < 900:  # <15 min
            if bs_ratio < BS_RATIO_NEW: return None, f"BS {bs_ratio:.2f} < {BS_RATIO_NEW} (<15min)"
        else:
            if bs_ratio < BS_RATIO_OLD: return None, f"BS {bs_ratio:.2f} < {BS_RATIO_OLD} (>15min)"

    # Exchange check
    if launchpad not in ALLOWED_EXCHANGES:
        return None, f"exchange {launchpad} not allowed"
    if launchpad in PUMP_REQUIREMENTS:
        req = PUMP_REQUIREMENTS[launchpad]
        if req and not pair_address.endswith(req):
            return None, f"pair {pair_address[-10:]} doesn't end with {req}"

    # Passed all filters
    return {
        'token': symbol,
        'address': addr,
        'price': price,
        'mcap': mcap,
        'h1': h1,
        'h24': h24,
        'chg5': chg5,
        'chg1': chg1,
        'holders': holders,
        'top10': top10,
        'liquidity': liquidity,
        'volume': volume,
        'vol_mcap_ratio': vol_mcap_ratio,
        'bs_ratio': bs_ratio,
        'age_sec': age_sec,
        'ath_mcap': ath_mcap,
        'dip': dip,
        'launchpad': launchpad,
        'pair_address': pair_address,
        'pump_rule_triggered': pump_triggered,
    }, None

def buy_token(addr, result):
    global PERM_BLACKLIST
    if check_stop_buys():
        print(f"   [BLOCKED] {result['token']}: buys STOPPED - API safety active")
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
        'entry_reason': 'GMGN_V73',
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
            msg = f"🟢 BUY | {datetime.now(timezone.utc).strftime('%H:%M')}\n━━━━━━━━━━━━━━━\n{result.get('token')}\nEntry MC: ${int(result.get('mcap', 0)):,}\nAmount: {POSITION_SIZE} SOL\nH1: {result.get('h1', 0):+.1f}%\nDip: {result.get('dip', 0):.1f}%\n\nhttps://dexscreener.com/solana/{addr}\nhttps://pump.fun/{addr}"
            send_telegram(msg)
        except Exception as e:
            print(f"Alert error: {e}")
        return True
    except Exception as e:
        print(f"Buy error: {e}")
        return False

def add_to_cooldown(addr, token_data, result, entry_chg5):
    """Add token to cooldown watch"""
    global COOLDOWN_WATCH
    age_sec = result.get('age_sec', 0)
    h1 = result.get('h1', 0)
    chg5 = result.get('chg5', 0)
    pump_triggered = result.get('pump_rule_triggered', False)
    
    # Determine initial state
    if pump_triggered:
        state = STATE_PUMP_WAIT_1
        cooldown_end = time.time() + STATE_PUMP_WAIT_1
    elif age_sec < YOUNG_AGE_THRESHOLD and h1 > H1_MOMENTUM_MIN and chg5 > -5:
        state = STATE_PUMP_WAIT_1  # Use pump wait as base for young+momentum
        cooldown_end = time.time() + YOUNG_COOLDOWN
    elif age_sec >= YOUNG_AGE_THRESHOLD and h1 > H1_MOMENTUM_MIN and chg5 > -5:
        state = STATE_PUMP_WAIT_1  # Use pump wait as base for older+momentum
        cooldown_end = time.time() + OLDER_COOLDOWN
    else:
        state = STATE_BASE_WAIT
        cooldown_end = time.time() + NORMAL_COOLDOWN
    
    COOLDOWN_WATCH[addr] = {
        'state': state,
        'cooldown_end': cooldown_end,
        'token_data': token_data,
        'result': result,
        'recheck_count': 0,
        'pump_rule_triggered': pump_triggered,
        'chg5_prev': chg5,
        'h1_prev': h1,
        'age_sec': age_sec,
        'entry_chg5': entry_chg5,
        'lowest_chg5': chg5,  # Track lowest chg5 for recovery
    }

def scan_cycle():
    tokens = []
    tokens.extend(get_gmgn_trending(50))
    tokens.extend(get_gmgn_trenches(20))
    tokens.extend(get_gmgn_pumpfun_lowcap(20))
    if not tokens:
        return False
    
    # Deduplicate
    seen = set()
    unique = []
    for t in tokens:
        addr = t.get('address', '')
        if addr and addr not in seen:
            seen.add(addr)
            unique.append(t)
    
    now = time.time()
    open_count = get_open_position_count()
    
    to_remove = []
    
    for addr, data in list(COOLDOWN_WATCH.items()):
        result = data['result']
        state = data.get('state', STATE_BASE_WAIT)
        pump_triggered = data.get('pump_rule_triggered', False)
        age_sec = data.get('age_sec', 0)
        chg5_prev = data.get('chg5_prev', 0)
        h1_prev = data.get('h1_prev', 0)
        lowest_chg5 = data.get('lowest_chg5', 0)
        entry_chg5 = data.get('entry_chg5', 0)
        
        # Fresh GMGN data for recheck
        fresh = get_gmgn_token_info(addr)
        if not fresh:
            to_remove.append(addr)
            continue
        
        # Update fields from fresh data
        chg5 = float(fresh.get('price_change_percent5m', 0) or 0)
        h1 = float(fresh.get('price_change_percent1h', 0) or 0)
        chg1 = float(fresh.get('price_change_percent1m', 0) or 0)
        mcap = float(fresh.get('market_cap', 0) or 0)
        result['chg5'] = chg5
        result['h1'] = h1
        result['chg1'] = chg1
        result['mcap'] = mcap
        
        print(f"   [{state[:6]}] {result['token']}: chg5={chg5:+.1f}% h1={h1:+.1f}%")
        
        # === PUMP PATH ===
        if state == STATE_PUMP_WAIT_1:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                continue
            # Fetch fresh GMGN
            if chg5 > PUMP_CHG5_THRESHOLD:
                data['state'] = STATE_PUMP_WAIT_2
                data['cooldown_end'] = now + PUMP_WAIT_2
                data['recheck_count'] = 0
                print(f"   [PUMP_CONFIRMED] {result['token']}: chg5={chg5:+.1f}% still >+{PUMP_CHG5_THRESHOLD}% | wait {PUMP_WAIT_2}s")
            else:
                # Pump faded - go to recovery
                data['state'] = STATE_RECOVERY_WAIT
                data['cooldown_end'] = now + STATE_RECOVERY_WAIT
                data['lowest_chg5'] = min(lowest_chg5, chg5)
                data['recheck_count'] = 0
                print(f"   [PUMP_FADED] {result['token']}: chg5={chg5:.1f}% < +{PUMP_CHG5_THRESHOLD}% | recovery path")
            continue
        
        elif state == STATE_PUMP_WAIT_2:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                continue
            # Final verify with fresh data
            if chg5 > PUMP_CHG5_THRESHOLD:
                data['state'] = STATE_PUMP_VERIFY
                data['cooldown_end'] = now + PUMP_VERIFY_DELAY
                print(f"   [PUMP_VERIFY] {result['token']}: chg5={chg5:+.1f}% | verify {PUMP_VERIFY_DELAY}s")
            else:
                data['state'] = STATE_RECOVERY_WAIT
                data['cooldown_end'] = now + STATE_RECOVERY_WAIT
                data['lowest_chg5'] = min(lowest_chg5, chg5)
                print(f"   [PUMP_FAIL] {result['token']}: chg5={chg5:.1f}% | recovery")
            continue
        
        elif state == STATE_PUMP_VERIFY:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                continue
            if chg5 > PUMP_CHG5_THRESHOLD:
                print(f"   [BUY_PUMP] {result['token']}: confirmed | BUY!")
                buy_token(addr, result)
                to_remove.append(addr)
                continue
            else:
                data['state'] = STATE_RECOVERY_WAIT
                data['cooldown_end'] = now + STATE_RECOVERY_WAIT
                data['lowest_chg5'] = min(lowest_chg5, chg5)
                print(f"   [PUMP_FAIL] {result['token']}: chg5={chg5:.1f}% | recovery path")
                continue
        
        # === DETERIORATION CHECK (all states) ===
        chg5_drop = chg5_prev - chg5 if chg5_prev else 0
        h1_change_ratio = abs(h1 / h1_prev) if h1_prev else 1
        
        # H1 instability: >3x change → reject immediately
        if h1_prev > 0 and h1_change_ratio > H1_INSTABILITY_MULTIPLIER * 3:
            print(f"   [REJECT_H1_INSTABLE] {result['token']}: h1 {h1_prev:.0f}% → {h1:.0f}% (>{H1_INSTABILITY_MULTIPLIER}x change)")
            REJECTED_TEMP[addr] = {'ts': now, 'reason': 'h1 instability'}
            to_remove.append(addr)
            continue
        
        # Deterioration: chg5 dropped > CHG5_DROP_THRESHOLD from previous
        if chg5_drop > CHG5_DROP_THRESHOLD:
            lowest_chg5 = min(lowest_chg5, chg5)
            data['lowest_chg5'] = lowest_chg5
            data['chg5_prev'] = chg5
            data['h1_prev'] = h1
            data['recheck_count'] += 1
            data['cooldown_end'] = now + STATE_RECOVERY_WAIT
            print(f"   [DETERIORATING] {result['token']}: chg5 {chg5_prev:+.1f}% → {chg5:+.1f}% (dropped {chg5_drop:.1f}%) | watching for recovery")
            # Check if recovered: chg5 > +5% from lowest AND must be > +2%
            recovery_target = lowest_chg5 + CHG5_RECOVERY_CHECK
            if chg5 >= max(recovery_target, MIN_CHG5_FOR_BUY):
                data['state'] = STATE_POST_COOLDOWN
                data['cooldown_end'] = now + STATE_POST_COOLDOWN
                print(f"   [RECOVERED] {result['token']}: chg5={chg5:+.1f}% >= {recovery_target:+.1f}% | verify {STATE_POST_COOLDOWN}s")
            continue
        
        # === YOUNG COOLDOWN PATH (<15min + h1>5% + chg5>-5%) ===
        if state == STATE_BASE_WAIT and age_sec < YOUNG_AGE_THRESHOLD and h1 > H1_MOMENTUM_MIN and chg5 > -5:
            if chg5 < MIN_CHG5_FOR_BUY:
                # Not ready - wait in base
                data['cooldown_end'] = now + STATE_BASE_WAIT
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                print(f"   [YOUNG_WAIT] {result['token']}: chg5={chg5:+.1f}% < +{MIN_CHG5_FOR_BUY}% | wait {STATE_BASE_WAIT}s")
            else:
                # Ready - start young cooldown
                data['state'] = STATE_POST_COOLDOWN
                data['cooldown_end'] = now + YOUNG_COOLDOWN
                data['lowest_chg5'] = chg5
                print(f"   [YOUNG_COOLDOWN] {result['token']}: chg5={chg5:+.1f}% | wait {YOUNG_COOLDOWN}s")
            data['chg5_prev'] = chg5
            data['h1_prev'] = h1
            continue
        
        # === OLDER COOLDOWN PATH (>15min + h1>5% + chg5>-5%) ===
        if state == STATE_BASE_WAIT and age_sec >= YOUNG_AGE_THRESHOLD and h1 > H1_MOMENTUM_MIN and chg5 > -5:
            if chg5 < MIN_CHG5_FOR_BUY:
                data['cooldown_end'] = now + STATE_BASE_WAIT
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                print(f"   [OLDER_WAIT] {result['token']}: chg5={chg5:+.1f}% < +{MIN_CHG5_FOR_BUY}% | wait {STATE_BASE_WAIT}s")
            else:
                data['state'] = STATE_POST_COOLDOWN
                data['cooldown_end'] = now + OLDER_COOLDOWN
                data['lowest_chg5'] = chg5
                print(f"   [OLDER_COOLDOWN] {result['token']}: chg5={chg5:+.1f}% | wait {OLDER_COOLDOWN}s")
            data['chg5_prev'] = chg5
            data['h1_prev'] = h1
            continue
        
        # === RECOVERY PATH (from deterioration, chg5 dropped but now recovering) ===
        if state == STATE_RECOVERY_WAIT:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                continue
            recovery_target = data['lowest_chg5'] + CHG5_RECOVERY_CHECK
            if chg5 >= max(recovery_target, MIN_CHG5_FOR_BUY):
                data['state'] = STATE_POST_COOLDOWN
                data['cooldown_end'] = now + STATE_POST_COOLDOWN
                print(f"   [RECOVERED] {result['token']}: chg5={chg5:+.1f}% >= {recovery_target:+.1f}% | verify {STATE_POST_COOLDOWN}s")
            else:
                data['lowest_chg5'] = min(data['lowest_chg5'], chg5)
                data['cooldown_end'] = now + STATE_RECOVERY_WAIT
                print(f"   [STILL_RECOVERING] {result['token']}: chg5={chg5:+.1f}% < {recovery_target:+.1f}% | wait {STATE_RECOVERY_WAIT}s")
            data['chg5_prev'] = chg5
            continue
        
        # === POST-COOLDOWN: Verify then BUY ===
        if state == STATE_POST_COOLDOWN:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                continue
            # Verify chg5 still > +2%
            if chg5 >= MIN_CHG5_FOR_BUY:
                # Final filter check
                final_result, fail_reason = scan_token(data['token_data'])
                if final_result:
                    print(f"   [BUY_READY] {result['token']}: verified | BUY!")
                    buy_token(addr, final_result)
                    to_remove.append(addr)
                    continue
                else:
                    print(f"   [REJECT_V73] {result['token']}: {fail_reason}")
                    REJECTED_TEMP[addr] = {'ts': now, 'reason': fail_reason}
                    to_remove.append(addr)
                    continue
            else:
                # chg5 dropped - back to base
                data['state'] = STATE_BASE_WAIT
                data['cooldown_end'] = now + STATE_BASE_WAIT
                data['lowest_chg5'] = min(data['lowest_chg5'], chg5)
                print(f"   [POST_COOLDOWN_DROP] {result['token']}: chg5={chg5:.1f}% < +{MIN_CHG5_FOR_BUY}% | base wait")
            data['chg5_prev'] = chg5
            data['h1_prev'] = h1
            continue
        
        # === BASE WAIT: Standard rechecks ===
        if state == STATE_BASE_WAIT:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                continue
            # Check chg5
            if chg5 >= MIN_CHG5_FOR_BUY:
                # Ready - verify and buy
                final_result, fail_reason = scan_token(data['token_data'])
                if final_result:
                    print(f"   [BUY_NORMAL] {result['token']}: chg5={chg5:+.1f}% | BUY!")
                    buy_token(addr, final_result)
                    to_remove.append(addr)
                    continue
                else:
                    print(f"   [REJECT_V73] {result['token']}: {fail_reason}")
                    REJECTED_TEMP[addr] = {'ts': now, 'reason': fail_reason}
                    to_remove.append(addr)
                    continue
            else:
                data['cooldown_end'] = now + STATE_BASE_WAIT
                print(f"   [BASE_RECHECK] {result['token']}: chg5={chg5:+.1f}% < +{MIN_CHG5_FOR_BUY}% | wait {STATE_BASE_WAIT}s")
            data['chg5_prev'] = chg5
            data['h1_prev'] = h1
            continue
    
    # Remove finished tokens
    for addr in to_remove:
        if addr in COOLDOWN_WATCH:
            del COOLDOWN_WATCH[addr]
    
    # Clean old rejected
    for addr in list(REJECTED_TEMP.keys()):
        if now - REJECTED_TEMP[addr]['ts'] > 300:
            del REJECTED_TEMP[addr]
    
    # === NEW TOKEN SCAN ===
    for token_data in unique:
        addr = token_data.get('address', '')
        if not addr: continue
        if addr in PERM_BLACKLIST or addr in COOLDOWN_WATCH: continue
        if addr in REJECTED_TEMP: continue
        if get_open_position_count() >= MAX_OPEN_POSITIONS:
            print(f"   [MAX_POSITIONS] {addr[:20]}: {MAX_OPEN_POSITIONS} open, skipping")
            continue
        
        result, fail_reason = scan_token(token_data)
        if result is None:
            continue
        
        entry_chg5 = result.get('chg5', 0)
        add_to_cooldown(addr, token_data, result, entry_chg5)
        print(f"   [FOUND] {result['token']}: mc=${result['mcap']:,.0f} h1={result['h1']:+.1f}% chg5={entry_chg5:+.1f}% dip={result.get('dip', 0):.1f}% | cooldown started")
    
    return True

def main():
    print("GMGN Scanner v7.3 Started - LIVE TRADING")
    print(f"  Mcap $6K-$55K | Age 3-90min | Holders ≥15")
    print(f"  Dip 5-45% | chg5>+20% pump rule | chg5>+2% normal entry")
    print(f"  Cooldown: 45s young/older+momentum | 30s base | 15s deterioration rechecks")
    print(f"  Exit: TP1+50%H TP2+100%sell35% TP3+200%sell30% TP4+300%sell20% TP5+1000%sell15% Stop-30%")
    print(f"  MAX_OPEN: {MAX_OPEN_POSITIONS} | SIZE: {POSITION_SIZE} SOL | pump.fun/raydium/pumpswap ONLY")
    
    while True:
        try:
            scan_cycle()
        except Exception as e:
            print(f"Scan error: {e}")
        time.sleep(1)  # 1 second between cycles

if __name__ == '__main__':
    main()
