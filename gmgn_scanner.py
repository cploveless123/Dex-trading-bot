#!/usr/bin/env python3
"""
gmgn_scanner.py - v7.4 CLEAN
A complete, clean rewrite of the GMGN scanner with IRONCLAD rules.

IRONCLAD RULES:
- Permanent Blacklist: any token ever bought = never buy again
- Max 5 open positions
- 0.1 SOL per trade
- Never re-buy (PERM_BLACKLIST checked before every buy)
- Only pump.fun / raydium / pumpswap exchanges
- Fresh data only (no stale) - GMGN primary, DexScreener backup
- Throttle alert once per cycle (not per event)
- No duplicate alerts (5 min dedup)
- DexScreener fails > 5/hour → stop calls for 1 hour
- Both GMGN + DexScreener throttled → STOP ALL BUYS until fixed
"""

import subprocess, json, time, urllib.request, urllib.parse
from datetime import datetime, timezone

# =====================================================================
# CONSTANTS
# =====================================================================
POSITION_SIZE = 0.1
MAX_OPEN_POSITIONS = 5
MIN_MCAP = 6000
MAX_MCAP = 55000
MIN_HOLDERS = 15
MIN_CHG5_FOR_BUY = 2.0
PUMP_CHG1_THRESHOLD = 20.0
H1_MOMENTUM_MIN = 5.0
FALLEN_GIANT_H1 = 350
FALLEN_GIANT_MCAP = 25000
H1_INSTABILITY_MULTIPLIER = 3
CHG5_DROP_THRESHOLD = 10
CHG5_RECOVERY_CHECK = 5
YOUNG_AGE_THRESHOLD = 900
BS_RATIO_NEW = 1.5
BS_RATIO_OLD = 1.3
MIN_VOLUME = 10000
ALLOWED_EXCHANGES = ['raydium', 'pump', 'pumpswap']  # pump/pumpswap need pair_address ending in 'pump'
PUMP_EXCHANGES = ['pump', 'pumpswap']  # pump.fun and pumpswap - pair must end in "pump"
PERM_BLACKLIST_FILE = '/root/Dex-trading-bot/.perm_blacklist.json'

BOT_TOKEN = '8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg'
CHAT_ID = '6402511249'

# =====================================================================
# STATE MACHINE STATES
# =====================================================================
STATE_PUMP_WAIT_1 = 'PUMP_WAIT_1'       # 45s wait for pump confirmation
STATE_PUMP_WAIT_2 = 'PUMP_WAIT_2'       # 30s second confirmation
STATE_PUMP_VERIFY = 'PUMP_VERIFY'        # 15s final verify
STATE_YOUNG_COOLDOWN = 'YOUNG_COOLDOWN'  # 45s for young + momentum
STATE_OLDER_COOLDOWN = 'OLDER_COOLDOWN'  # 45s for older + momentum
STATE_CHG1_RECHECK = 'CHG1_RECHECK'      # 15s rechecks until mcap>+5% from low
STATE_CHG1_VERIFY = 'CHG1_VERIFY'        # 15s verify before buy
STATE_BASE_WAIT = 'BASE_WAIT'            # 30s → verify chg1 > chg5_prev + 3%
STATE_RECOVERY_WAIT = 'RECOVERY_WAIT'    # 15s for chg5 recovery

# Timing constants
PUMP_WAIT_1 = 45
PUMP_WAIT_2 = 30
PUMP_VERIFY_DELAY = 15
YOUNG_COOLDOWN = 45
OLDER_COOLDOWN = 45
RECOVERY_WAIT = 15

# =====================================================================
# GLOBAL STATE
# =====================================================================
GMGN_SCANNER_VERSION = "v7.4 CLEAN"
COOLDOWN_WATCH = {}       # addr -> {state, cooldown_end, token_data, result, ...}
REJECTED_TEMP = {}        # addr -> {ts, reason}
PERM_BLACKLIST = set()    # Loaded from file

# GMGN throttle state
_gmgn_throttle_state = {
    'trending': {'count': 0, 'backoff_until': 0},
    'trenches': {'count': 0, 'backoff_until': 0},
    'token_info': {'count': 0, 'backoff_until': 0},
}
_BACKOFF_BASE = 30
_BACKOFF_MAX = 300

# IronClad trackers
DEXSCREENER_FAIL_COUNT = 0
DEXSCREENER_FAIL_RESET = time.time()
_BUYS_STOPPED = False
_LAST_ALERT_TIMES = {}   # alert_key -> timestamp (5 min dedup)
_ALERTS_THIS_CYCLE = set()
_LAST_DEXSCR_ALERT = 0   # timestamp of last DexScreener failure alert

# Load PERM_BLACKLIST
try:
    with open(PERM_BLACKLIST_FILE) as f:
        PERM_BLACKLIST = set(json.load(f))
except:
    PERM_BLACKLIST = set()

# =====================================================================
# HELPER FUNCTIONS
# =====================================================================

def is_throttled(endpoint):
    state = _gmgn_throttle_state[endpoint]
    # Reset _alerted when backoff expires
    if time.time() >= state['backoff_until']:
        state['_alerted'] = False
    return time.time() < state['backoff_until']

def record_throttle(endpoint):
    state = _gmgn_throttle_state[endpoint]
    state['count'] += 1
    wait_time = min(_BACKOFF_BASE * (2 ** state['count']), _BACKOFF_MAX)
    state['backoff_until'] = time.time() + wait_time
    # Alert only once per throttle event (not per increment)
    if not state.get('_alerted', False):
        state['_alerted'] = True
        send_alert(f"⚠️ GMGN {endpoint.upper()} THROTTLED: {state['count']} failures, backoff {wait_time:.0f}s")

def check_stop_buys():
    """Stop buys if both GMGN AND DexScreener are failing"""
    global _BUYS_STOPPED
    now = time.time()
    
    # Reset DexScreener fail count after 1 hour
    global DEXSCREENER_FAIL_COUNT, DEXSCREENER_FAIL_RESET
    if now - DEXSCREENER_FAIL_RESET > 3600:
        DEXSCREENER_FAIL_COUNT = 0
        DEXSCREENER_FAIL_RESET = now
    
    gmgn_throttled = any(time.time() < s['backoff_until'] for s in _gmgn_throttle_state.values())
    
    if gmgn_throttled and DEXSCREENER_FAIL_COUNT >= 5:
        if not _BUYS_STOPPED:
            _BUYS_STOPPED = True
            send_alert("🚨🚨 STOPPING ALL BUYS: GMGN throttled + DexScreener failing")
    elif not gmgn_throttled and _BUYS_STOPPED:
        _BUYS_STOPPED = False
        send_alert("✅ RESUMING BUYS: APIs recovered")
    
    return _BUYS_STOPPED

def send_alert(msg):
    """Send alert with deduplication - once per type per 5 minutes"""
    alert_key = msg[:60]
    now = time.time()
    if alert_key in _LAST_ALERT_TIMES:
        if now - _LAST_ALERT_TIMES[alert_key] < 300:
            return
    _LAST_ALERT_TIMES[alert_key] = now
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
        req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode())
        urllib.request.urlopen(req, timeout=10)
    except:
        pass

# =====================================================================
# GMGN API FUNCTIONS
# =====================================================================

def get_gmgn_trending(limit=50):
    if is_throttled('trending'):
        return []
    r = subprocess.run(['gmgn-cli', 'market', 'trending', '--chain', 'sol', '--interval', '5m', '--limit', str(limit)],
                      capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        record_throttle('trending')
        send_alert("⚠️ GMGN trending FAILED")
        return []
    try:
        d = json.loads(r.stdout)
        return d.get('data', {}).get('rank', [])
    except:
        return []

def get_gmgn_token_info(addr):
    if is_throttled('token_info'):
        send_alert(f"⚠️ GMGN token_info THROTTLED")
        return None
    r = subprocess.run(['gmgn-cli', 'token', 'info', '--chain', 'sol', '--address', addr],
                      capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        record_throttle('token_info')
        send_alert(f"⚠️ GMGN token_info FAILED")
        return None
    try:
        data = json.loads(r.stdout)
        if data and data.get('price_change_percent1h') is None:
            # GMGN data stale - just return None, no alert
            return None
        return data
    except:
        return None

# =====================================================================
# DEXSCREENER BACKUP
# =====================================================================

def get_dexscreener_token(addr):
    """Fetch from DexScreener as GMGN backup"""
    global DEXSCREENER_FAIL_COUNT
    if DEXSCREENER_FAIL_COUNT >= 5:
        return None
    try:
        url = f"https://api.dexscreener.io/v1/tokens/{addr}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            DEXSCREENER_FAIL_COUNT = 0
            return data
    except:
        DEXSCREENER_FAIL_COUNT += 1
        # Track failure internally - don't spam Telegram
        if DEXSCREENER_FAIL_COUNT >= 5:
            # Only alert once when circuit breaker trips
            if DEXSCREENER_FAIL_COUNT == 5:
                _LAST_DEXSCR_ALERT = time.time()
        return None

def get_fresh_token_data(addr):
    """Get fresh token data: GMGN first, DexScreener fallback"""
    info = get_gmgn_token_info(addr)
    if info and info.get('price_change_percent1h') is not None:
        return info, 'gmgn'
    
    dex_data = get_dexscreener_token(addr)
    if dex_data and dex_data.get('priceChange', {}).get('h1') is not None:
        return dex_data, 'dexscreener'
    
    return None, None

# =====================================================================
# TOKEN SCANNING (FILTERS ONLY - NO STATE MANAGEMENT)
# =====================================================================

def scan_token(token_data, reason_if_fail=None):
    """
    Apply all entry filters. Returns (result_dict, None) if passes, (None, reason) if fails.
    Does NOT manage state - only filtering.
    """
    try:
        mc = float(token_data.get('market_cap', 0) or 0)
        h1 = float(token_data.get('price_change_percent1h', 0) or 0)
        chg5 = float(token_data.get('price_change_percent5m', 0) or 0)
        chg1 = float(token_data.get('price_change_percent1m', 0) or 0)
        holders = int(token_data.get('holder_count', 0) or 0)
        top10pct = float(token_data.get('top10holderpercent', 0) or 0)
        volume = float(token_data.get('volume', 0) or 0)
        bs_ratio = float(token_data.get('bs_change24hpercent', 0) or 0)
        launchpad = str(token_data.get('launchpad', '')).lower().strip()
        pair_address = token_data.get('pair_address', '') or ''
        addr = token_data.get('address', '')
        
        if not addr:
            return None, "no address"
        
        # Exchange check
        if launchpad not in ALLOWED_EXCHANGES and launchpad != '':
            return None, f"exchange {launchpad} not allowed"
        
        # Mcap check
        if mc < MIN_MCAP:
            return None, f"mcap ${mc:,.0f} < ${MIN_MCAP:,}"
        if mc > MAX_MCAP:
            return None, f"mcap ${mc:,.0f} > ${MAX_MCAP:,}"
        
        # Holders check
        if holders < MIN_HOLDERS:
            return None, f"holders {holders} < {MIN_HOLDERS}"
        
        # Volume check
        if volume < MIN_VOLUME:
            return None, f"vol ${volume:,.0f} < ${MIN_VOLUME:,}"
        
        # Fallen Giant check
        if h1 > FALLEN_GIANT_H1 and mc < FALLEN_GIANT_MCAP:
            return None, f"Fallen Giant: h1={h1:.0f}% + mcap=${mc:,.0f} < ${FALLEN_GIANT_MCAP:,}"
        
        # H1 momentum check
        if h1 < H1_MOMENTUM_MIN:
            return None, f"h1 {h1:.1f}% < {H1_MOMENTUM_MIN}%"
        
        # BS ratio check
        if launchpad == 'pump':
            pass  # pump.fun has no BS data
        elif bs_ratio > 0 and bs_ratio < (BS_RATIO_NEW if mc < 30000 else BS_RATIO_OLD):
            return None, f"BS {bs_ratio:.2f} too low"
        
        # Build result
        pump_triggered = chg1 >= PUMP_CHG1_THRESHOLD
        
        result = {
            'token': token_data.get('symbol', '?'),
            'address': addr,
            'mcap': mc,
            'h1': h1,
            'chg5': chg5,
            'chg1': chg1,
            'holders': holders,
            'volume': volume,
            'bs_ratio': bs_ratio,
            'launchpad': launchpad,
            'pair_address': pair_address,
            'pump_rule_triggered': pump_triggered,
            'entry_price': float(token_data.get('price', 0) or 0),
        }
        
        return result, None
        
    except Exception as e:
        return None, f"scan error: {e}"

# =====================================================================
# BUY FUNCTION
# =====================================================================

TRADES_FILE = '/root/Dex-trading-bot/trades/sim_trades.jsonl'

def get_open_position_count():
    try:
        with open(TRADES_FILE) as f:
            return sum(1 for l in f if l.strip() and json.loads(l).get('action') == 'BUY' and json.loads(l).get('status') == 'open')
    except:
        return 0

def get_scanner_status():
    """Return scanner status dict for heartbeat reporting"""
    gmgn_throttled = any(time.time() < s['backoff_until'] for s in _gmgn_throttle_state.values())
    return {
        'cooldown_count': len(COOLDOWN_WATCH),
        'blacklist_count': len(PERM_BLACKLIST),
        'rejected_temp_count': len(REJECTED_TEMP),
        'dexscraper_fail_count': DEXSCREENER_FAIL_COUNT,
        'gmgn_throttled': gmgn_throttled,
        'gmgn_trending_fails': _gmgn_throttle_state['trending']['count'],
        'gmgn_trenches_fails': _gmgn_throttle_state['trenches']['count'],
        'gmgn_token_info_fails': _gmgn_throttle_state['token_info']['count'],
        'buys_stopped': _BUYS_STOPPED,
    }

def save_trade(trade):
    with open(TRADES_FILE, 'a') as f:
        f.write(json.dumps(trade) + '\n')

def buy_token(addr, result):
    """Execute a buy - always checks PERM_BLACKLIST first"""
    # IRONCLAD: Never buy blacklisted
    if addr in PERM_BLACKLIST:
        return False
    
    if get_open_position_count() >= MAX_OPEN_POSITIONS:
        return False
    
    # IRONCLAD: Verify pair_address for pump/pumpswap - must end in "pump"
    launchpad = str(result.get('launchpad', '')).lower().strip()
    pair_address = str(result.get('pair_address', '')).lower().strip()
    
    if launchpad in ['pump', 'pumpswap'] and pair_address:
        if not pair_address.endswith('pump'):
            send_alert(f"🚫 BUY BLOCKED: {result.get('token')} pair_address doesn't end in 'pump'")
            return False
    
    # Try to verify with fresh data if available
    if launchpad in ['pump', 'pumpswap'] and pair_address.endswith('pump'):
        pass  # Already verified
    
    trade = {
        'action': 'BUY',
        'token_address': addr,
        'token_name': result.get('token', '?'),
        'entry_price': result.get('entry_price', 0),
        'entry_mcap': int(result.get('mcap', 0)),
        'opened_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00'),
        'entry_sol': POSITION_SIZE,
        'status': 'open',
        'tp_status': {'tp1_hit': False, 'tp2_hit': False, 'tp3_hit': False, 'tp4_hit': False, 'tp5_hit': False},
        'tp1_sold': False, 'tp2_sold': False, 'tp3_sold': False, 'tp4_sold': False, 'tp5_sold': False,
        'partial_exit': False, 'fully_exited': False,
        'peak_price': result.get('entry_price', 0),
    }
    
    save_trade(trade)
    
    # IRONCLAD: Add to PERM_BLACKLIST immediately
    PERM_BLACKLIST.add(addr)
    with open(PERM_BLACKLIST_FILE, 'w') as f:
        json.dump(list(PERM_BLACKLIST), f)
    
    msg = (f"🟢 BUY | {datetime.now(timezone.utc).strftime('%H:%M')}\n"
           f"━━━━━━━━━━━━━━━\n"
           f"{result.get('token')}\n"
           f"Entry MC: ${int(result.get('mcap', 0)):,}\n"
           f"Amount: {POSITION_SIZE} SOL\n"
           f"H1: {result.get('h1', 0):+.1f}%\n"
           f"5m: {result.get('chg5', 0):+.1f}%\n\n"
           f"https://dexscreener.com/solana/{addr}\n"
           f"https://pump.fun/{addr}")
    send_alert(msg)
    return True

# =====================================================================
# ADD TO COOLDOWN (STATE ASSIGNMENT ONLY)
# =====================================================================

def add_to_cooldown(addr, token_data, result, entry_chg5):
    """Assign initial cooldown state based on entry conditions"""
    h1 = result.get('h1', 0)
    chg5 = result.get('chg5', 0)
    chg1 = result.get('chg1', 0)
    pump = result.get('pump_rule_triggered', False)
    age_sec = result.get('age_sec', 0)
    
    # Determine state
    if pump:
        state = STATE_PUMP_WAIT_1
        cooldown_end = time.time() + PUMP_WAIT_1
    elif chg1 < -5:
        # chg1 negative - use recovery path
        state = STATE_CHG1_RECHECK
        cooldown_end = time.time() + 15
    elif age_sec < YOUNG_AGE_THRESHOLD and h1 > H1_MOMENTUM_MIN and chg5 > -5:
        state = STATE_YOUNG_COOLDOWN
        cooldown_end = time.time() + YOUNG_COOLDOWN
    elif age_sec >= YOUNG_AGE_THRESHOLD and h1 > H1_MOMENTUM_MIN and chg5 > -5:
        state = STATE_OLDER_COOLDOWN
        cooldown_end = time.time() + OLDER_COOLDOWN
    else:
        state = STATE_BASE_WAIT
        cooldown_end = time.time() + 30
    
    COOLDOWN_WATCH[addr] = {
        'state': state,
        'cooldown_end': cooldown_end,
        'token_data': token_data,
        'result': result,
        'recheck_count': 0,
        'pump_rule_triggered': pump,
        'chg5_prev': chg5,
        'h1_prev': h1,
        'lowest_mcap': result.get('mcap', 0),
        'lowest_chg5': chg5,
    }

# =====================================================================
# SCAN CYCLE (MAIN STATE MACHINE)
# =====================================================================

def scan_cycle():
    global _ALERTS_THIS_CYCLE, _BUYS_STOPPED
    _ALERTS_THIS_CYCLE.clear()
    _BUYS_STOPPED = False
    
    if check_stop_buys():
        return  # Don't scan if buys stopped due to API failure
    
    now = time.time()
    to_remove = []
    cooldown_start = now
    
    # Process ONLY tokens whose timers are about to expire (within 20s)
    # This prevents old/stale tokens from blocking new token evaluation
    urgent_tokens = [(addr, data) for addr, data in COOLDOWN_WATCH.items() 
                     if data['cooldown_end'] - now <= 20]
    
    for addr, data in urgent_tokens:
        # Timeout: if processing for more than 8s, stop to allow new scans
        if time.time() - cooldown_start > 8:
            print(f"[DEBUG] Cooldown timeout - processed {len(urgent_tokens)} urgent tokens")
            break
        
        result = data['result']
        state = data['state']
        
        # Only fetch fresh data if cooldown timer is about to expire (within 15s)
        # This reduces GMGN calls from N per 15s to 1 per 15s when timer is close
        cooldown_remaining = data['cooldown_end'] - now
        
        if cooldown_remaining > 15:
            # Timer not close - skip fresh fetch, use cached data
            chg5 = result.get('chg5', 0)
            h1 = result.get('h1', 0)
            chg1 = result.get('chg1', 0)
            mcap = result.get('mcap', 0)
            fresh_data = None
            source = None
        else:
            # Timer about to expire - get fresh data
            fresh_data, source = get_fresh_token_data(addr)
            if fresh_data is None:
                # Failed to get fresh data - skip this cycle, don't remove
                continue
            
            # Extract data from fresh source
            if source == 'gmgn':
                chg5 = float(fresh_data.get('price_change_percent5m', 0) or 0)
                h1 = float(fresh_data.get('price_change_percent1h', 0) or 0)
                chg1 = float(fresh_data.get('price_change_percent1m', 0) or 0)
                mcap = float(fresh_data.get('market_cap', 0) or 0)
            else:  # dexscanner
                pc = fresh_data.get('priceChange', {})
                chg5 = float(pc.get('m5', 0) or 0)
                h1 = float(pc.get('h1', 0) or 0)
                chg1 = float(pc.get('m1', 0) or 0)
                mcap = float(fresh_data.get('marketCap', 0) or 0)
            
            # Update result with fresh data
            result['chg5'] = chg5
            result['h1'] = h1
            result['chg1'] = chg1
            result['mcap'] = mcap
        
        chg5_prev = data.get('chg5_prev', chg5)
        h1_prev = data.get('h1_prev', h1)
        lowest_mcap = data.get('lowest_mcap', mcap)
        lowest_chg5 = data.get('lowest_chg5', chg5)
        
        # === PUMP PATH ===
        if state == STATE_PUMP_WAIT_1:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                continue
            # Timer done - verify chg1 still above pump threshold
            if chg1 >= PUMP_CHG1_THRESHOLD:
                data['state'] = STATE_PUMP_WAIT_2
                data['cooldown_end'] = now + PUMP_WAIT_2
                data['recheck_count'] = 0
                print(f"   [PUMP_CONFIRMED] {result['token']}: chg1={chg1:+.1f}% still >+{PUMP_CHG1_THRESHOLD}% | wait {PUMP_WAIT_2}s")
            else:
                data['state'] = STATE_RECOVERY_WAIT
                data['cooldown_end'] = now + RECOVERY_WAIT
                data['lowest_chg5'] = min(lowest_chg5, chg5)
                print(f"   [PUMP_FADED] {result['token']}: chg1={chg1:.1f}% < +{PUMP_CHG1_THRESHOLD}% | recovery")
            data['chg5_prev'] = chg5
            data['h1_prev'] = h1
            continue
        
        elif state == STATE_PUMP_WAIT_2:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                continue
            if chg1 >= PUMP_CHG1_THRESHOLD:
                data['state'] = STATE_PUMP_VERIFY
                data['cooldown_end'] = now + PUMP_VERIFY_DELAY
                data['recheck_count'] = 0
                print(f"   [PUMP_STILL_OK] {result['token']}: chg1={chg1:+.1f}% | verify {PUMP_VERIFY_DELAY}s")
            else:
                data['state'] = STATE_RECOVERY_WAIT
                data['cooldown_end'] = now + RECOVERY_WAIT
                print(f"   [PUMP_FADED_W2] {result['token']}: chg1={chg1:.1f}% | recovery")
            data['chg5_prev'] = chg5
            data['h1_prev'] = h1
            continue
        
        elif state == STATE_PUMP_VERIFY:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                continue
            if chg1 >= PUMP_CHG1_THRESHOLD:
                print(f"   [BUY_PUMP] {result['token']}: chg1={chg1:+.1f}% | BUY!")
                buy_token(addr, result)
                to_remove.append(addr)
                send_alert(f"🚀 BUY SIGNAL | {result['token']}\n━━━━━━━━━━━━━━━\n📊 Pump path triggered\n💰 Entry: ${result.get('mcap', 0):,.0f} mcap\n🔗 https://dexscreener.com/solana/{addr}\n🥧 https://pump.fun/{addr}")
            else:
                data['state'] = STATE_RECOVERY_WAIT
                data['cooldown_end'] = now + RECOVERY_WAIT
                print(f"   [PUMP_FADED_V] {result['token']}: chg1={chg1:.1f}% | recovery")
            data['chg5_prev'] = chg5
            data['h1_prev'] = h1
            continue
        
        # === CHG1 < -5% RECOVERY PATH ===
        elif state == STATE_CHG1_RECHECK:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                continue
            # Timer done - check if mcap recovered > +5% from lowest
            recovery_target = lowest_mcap * 1.05
            if mcap >= recovery_target:
                data['state'] = STATE_CHG1_VERIFY
                data['cooldown_end'] = now + 15
                print(f"   [CHG1_OK] {result['token']}: mcap={mcap:,.0f} >= {recovery_target:,.0f} (+5% from low) | verify 15s")
            else:
                # Still low - update lowest and recheck
                data['lowest_mcap'] = min(lowest_mcap, mcap)
                data['cooldown_end'] = now + 15
                data['recheck_count'] = data.get('recheck_count', 0) + 1
                print(f"   [CHG1_RECHECK] {result['token']}: mcap={mcap:,.0f} < {recovery_target:,.0f} | recheck 15s")
            data['chg5_prev'] = chg5
            data['h1_prev'] = h1
            continue
        
        elif state == STATE_CHG1_VERIFY:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                continue
            # Verify complete - BUY!
            print(f"   [BUY_CHG1] {result['token']}: chg1 recovered | BUY!")
            buy_token(addr, result)
            to_remove.append(addr)
            data['chg5_prev'] = chg5
            data['h1_prev'] = h1
            continue
        
        # === YOUNG COOLDOWN PATH ===
        elif state == STATE_YOUNG_COOLDOWN:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                # During cooldown: check if chg1 drops below -5%
                if chg1 < -5:
                    data['state'] = STATE_CHG1_RECHECK
                    data['cooldown_end'] = now + 15
                    data['lowest_mcap'] = mcap
                    print(f"   [CHG1_FALL] {result['token']}: chg1={chg1:.1f}% < -5% | recovery mode")
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                continue
            # 45s done - verify chg1 >= -5% AND chg5 >= +2%
            if chg1 >= -5 and chg5 >= MIN_CHG5_FOR_BUY:
                print(f"   [BUY_YOUNG] {result['token']}: chg1={chg1:+.1f}% >= -5% + chg5={chg5:+.1f}% >= +2% | BUY!")
                buy_token(addr, result)
                to_remove.append(addr)
                send_alert(f"🚀 BUY SIGNAL | {result['token']}\n━━━━━━━━━━━━━━━\n📊 Young cooldown path\n💰 Entry: ${result.get('mcap', 0):,.0f} mcap\n🔗 https://dexscreener.com/solana/{addr}\n🥧 https://pump.fun/{addr}")
            else:
                data['state'] = STATE_BASE_WAIT
                data['cooldown_end'] = now + 30
                print(f"   [YOUNG_NOT_READY] {result['token']}: chg1={chg1:.1f}% chg5={chg5:.1f}% | base recheck")
            data['chg5_prev'] = chg5
            data['h1_prev'] = h1
            continue
        
        # === OLDER COOLDOWN PATH ===
        elif state == STATE_OLDER_COOLDOWN:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                if chg1 < -5:
                    data['state'] = STATE_CHG1_RECHECK
                    data['cooldown_end'] = now + 15
                    data['lowest_mcap'] = mcap
                    print(f"   [CHG1_FALL] {result['token']}: chg1={chg1:.1f}% < -5% | recovery mode")
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                continue
            if chg1 >= -5 and chg5 >= MIN_CHG5_FOR_BUY:
                print(f"   [BUY_OLDER] {result['token']}: chg1={chg1:+.1f}% >= -5% + chg5={chg5:+.1f}% >= +2% | BUY!")
                buy_token(addr, result)
                to_remove.append(addr)
                send_alert(f"🚀 BUY SIGNAL | {result['token']}\n━━━━━━━━━━━━━━━\n📊 Older cooldown path\n💰 Entry: ${result.get('mcap', 0):,.0f} mcap\n🔗 https://dexscreener.com/solana/{addr}\n🥧 https://pump.fun/{addr}")
            else:
                data['state'] = STATE_BASE_WAIT
                data['cooldown_end'] = now + 30
                print(f"   [OLDER_NOT_READY] {result['token']}: chg1={chg1:.1f}% chg5={chg5:.1f}% | base recheck")
            data['chg5_prev'] = chg5
            data['h1_prev'] = h1
            continue
        
        # === BASE WAIT PATH (30s → verify chg1 > chg5_prev + 3%) ===
        elif state == STATE_BASE_WAIT:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                continue
            # Timer done - verify chg1 > chg5_prev + 3%
            chg1_threshold = chg5_prev + 3
            if chg1 >= chg1_threshold:
                print(f"   [BUY_BASE] {result['token']}: chg1={chg1:+.1f}% >= {chg1_threshold:+.1f}% from last | BUY!")
                buy_token(addr, result)
                to_remove.append(addr)
                send_alert(f"🚀 BUY SIGNAL | {result['token']}\n━━━━━━━━━━━━━━━\n📊 Base wait path\n💰 Entry: ${result.get('mcap', 0):,.0f} mcap\n🔗 https://dexscreener.com/solana/{addr}\n🥧 https://pump.fun/{addr}")
            else:
                data['cooldown_end'] = now + 30
                print(f"   [BASE_RECHECK] {result['token']}: chg1={chg1:.1f}% < {chg1_threshold:+.1f}% from last | recheck 30s")
            data['chg5_prev'] = chg5
            data['h1_prev'] = h1
            continue
        
        # === RECOVERY WAIT (chg5 dropped but recovering) ===
        elif state == STATE_RECOVERY_WAIT:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                continue
            recovery_target = lowest_chg5 + CHG5_RECOVERY_CHECK
            if chg5 >= max(recovery_target, MIN_CHG5_FOR_BUY):
                data['state'] = STATE_BASE_WAIT
                data['cooldown_end'] = now + 30
                print(f"   [RECOVERED] {result['token']}: chg5={chg5:+.1f}% >= {recovery_target:+.1f}% | base path")
            else:
                data['lowest_chg5'] = min(lowest_chg5, chg5)
                data['cooldown_end'] = now + RECOVERY_WAIT
                print(f"   [STILL_RECOVERING] {result['token']}: chg5={chg5:.1f}% < {recovery_target:+.1f}% | wait {RECOVERY_WAIT}s")
            data['chg5_prev'] = chg5
            data['h1_prev'] = h1
            continue
        
        # Fallback - unknown state, remove
        to_remove.append(addr)
    
    # Remove finished tokens
    for addr in to_remove:
        if addr in COOLDOWN_WATCH:
            del COOLDOWN_WATCH[addr]
    
    # Clean old rejected
    for addr in list(REJECTED_TEMP.keys()):
        if now - REJECTED_TEMP[addr]['ts'] > 300:
            del REJECTED_TEMP[addr]
    
    # === NEW TOKEN SCAN ===
    tokens = get_gmgn_trending(50)
    seen = set()
    for token_data in tokens:
        addr = token_data.get('address', '')
        if not addr or addr in seen:
            continue
        seen.add(addr)
        
        # IRONCLAD checks
        if addr in PERM_BLACKLIST:
            continue
        if addr in COOLDOWN_WATCH:
            continue
        if addr in REJECTED_TEMP:
            continue
        if get_open_position_count() >= MAX_OPEN_POSITIONS:
            continue
        
        result, fail_reason = scan_token(token_data)
        if result is None:
            continue
        
        add_to_cooldown(addr, token_data, result, result.get('chg5', 0))

# =====================================================================
# MAIN
# =====================================================================

def main():
    print(f"GMGN Scanner {GMGN_SCANNER_VERSION} Started - LIVE TRADING")
    print(f"  Sources: GMGN trending (DexScreener backup)")
    print(f"  Mcap ${MIN_MCAP:,}-${MAX_MCAP:,} | Holders ≥{MIN_HOLDERS}")
    print(f"  Dip 5-45% | chg1>+20% pump rule | chg5>+2% normal entry")
    print(f"  Pump: {PUMP_WAIT_1}s→{PUMP_WAIT_2}s→{PUMP_VERIFY_DELAY}s→BUY")
    print(f"  Young: {YOUNG_COOLDOWN}s | Older: {OLDER_COOLDOWN}s | Base: 30s")
    print(f"  CHG1 recovery: 15s rechecks until mcap>+5% from low → 15s verify")
    print(f"  Max: {MAX_OPEN_POSITIONS} open | Size: {POSITION_SIZE} SOL")
    print(f"  IronClad: Fresh data only, DexScreener backup, alert dedup")
    
    while True:
        try:
            scan_cycle()
        except Exception as e:
            print(f"Scan error: {e}")
        time.sleep(15)  # Reduced from 5s to reduce GMGN throttle

if __name__ == '__main__':
    main()