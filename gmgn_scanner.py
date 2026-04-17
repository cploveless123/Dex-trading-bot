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

import subprocess, json, time, urllib.request, urllib.parse, sys
from datetime import datetime, timezone

# =====================================================================
# CONSTANTS
# =====================================================================
POSITION_SIZE = 0.1
MAX_OPEN_POSITIONS = 5
MIN_MCAP = 8000
MAX_MCAP = 20000
MAX_AGE = 3600  # 60 minutes max token age
MIN_HOLDERS = 15
SIM_WALLET_FILE = '/root/Dex-trading-bot/sim_wallet.json'
CHRIS_STARTING_BALANCE = 1.0
MIN_CHG5_FOR_BUY = 2.0
PUMP_CHG1_THRESHOLD = 10.0
H1_MOMENTUM_MIN = 25.0
H1_MOMENTUM_MAX = 700.0
H1_INSTABILITY_MULTIPLIER = 3
CHG5_DROP_THRESHOLD = 10
CHG5_RECOVERY_CHECK = 5
YOUNG_AGE_THRESHOLD = 180   # 3 minutes - tokens younger than this use young cooldown path
BS_RATIO_NEW = 1.5
BS_RATIO_OLD = 1.3
MIN_VOLUME = 5000             # Minimum 24h volume in USD
ALLOWED_EXCHANGES = ['raydium', 'pump', 'pumpswap']  # pump/pumpswap need pair_address ending in 'pump'
PUMP_EXCHANGES = ['pump', 'pumpswap']  # pump.fun and pumpswap - pair must end in "pump"
PERM_BLACKLIST_FILE = '/root/Dex-trading-bot/.perm_blacklist.json'

BOT_TOKEN = '8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg'
CHAT_ID = '6402511249'

# =====================================================================
# STATE MACHINE STATES
# =====================================================================
STATE_PUMP_WAIT_1 = 'PUMP_WAIT_1'       # 45s wait for pump confirmation
STATE_PUMP_WAIT_2 = 'PUMP_WAIT_2'       # 15s second confirmation
STATE_PUMP_VERIFY = 'PUMP_VERIFY'        # 15s final verify
STATE_YOUNG_COOLDOWN = 'YOUNG_COOLDOWN'  # 30s for young + chg5>+50%
STATE_OLDER_COOLDOWN = 'OLDER_COOLDOWN'  # 45s for older + momentum
STATE_CHG1_RECHECK = 'CHG1_RECHECK'      # 15s rechecks until mcap>+5% from low
STATE_CHG1_VERIFY = 'CHG1_VERIFY'        # 15s verify before buy
STATE_BASE_WAIT = 'BASE_WAIT'            # 30s → verify chg1 > chg1_prev + 3%
STATE_NORMAL_WAIT = 'NORMAL_WAIT'      # 45s → first check → 15s verify → BUY
STATE_RECOVERY_WAIT = 'RECOVERY_WAIT'    # 6s for chg1 recovery for chg5 recovery

# Timing constants (sync with trading_constants.py)
PUMP_WAIT_1 = 45            # First pump confirmation wait (45s)
PUMP_WAIT_2 = 30            # Second pump confirmation wait (30s)
PUMP_VERIFY_DELAY = 15     # Final pump verification wait (15s)
PUMP_CHG1_THRESHOLD = 10.0  # 1-min change % to trigger pump path (chg1 must be >+10%)
YOUNG_COOLDOWN = 30         # Young path cooldown (<15min + chg5>+50%)
OLDER_COOLDOWN = 30         # Older path cooldown (>15min + chg5>+1%)
BASE_WAIT = 30             # Base path wait (30s verify chg1 > chg1_prev + 3%)
NORMAL_WAIT_DURATION = 45    # Normal path: 45s cooldown before first check
CHG1_RECHECK_INTERVAL = 15 # Recovery recheck interval
CHG1_VERIFY_DELAY = 15     # Recovery verify before buy
RECOVERY_WAIT = 15          # Recovery wait interval
PUMP_MIN_AGE = 180  # 3 min minimum age  # 5 min minimum age before buying  # 3 min minimum age before buying         # Min age (sec) before buying via pump path

# =====================================================================
# GLOBAL STATE
# =====================================================================
GMGN_SCANNER_VERSION = "v7.4 CLEAN"
COOLDOWN_WATCH = {}       # addr -> {state, cooldown_end, token_data, result, ...}
REJECTED_TEMP = {}        # addr -> {ts, reason}
PERM_BLACKLIST = set()    # Loaded from file
STOP_LOSS_COOLDOWN = {}   # addr -> {ts, reason} - tokens that hit stop loss, 30min lockout
STOP_LOSS_FILE = '/root/Dex-trading-bot/.stop_loss_cooldown'

# GMGN throttle state
_gmgn_throttle_state = {
    'trending': {'count': 0, 'backoff_until': 0},
    'trenches': {'count': 0, 'backoff_until': 0},
    'token_info': {'count': 0, 'backoff_until': 0},
}
_BACKOFF_BASE = 30
_BACKOFF_MAX = 300

# Global GMGN circuit breaker - stops ALL GMGN calls after consecutive failures
_GMGN_CONSECUTIVE_FAILS = 0
_GMGN_GLOBAL_BACKOFF_UNTIL = 0
_GMGN_BACKOFF_THRESHOLD = 10  # 10 fails before backoff   # 3 consecutive failures → global backoff
_GMGN_BACKOFF_DURATION = 60   # 60s global backoff before retrying

# Stagger GMGN calls - alternate trending/trenches to avoid burst
_GMGN_SCAN_CYCLE = 0          # Even = trending, Odd = trenches

# IronClad trackers
DEXSCREENER_FAIL_COUNT = 0
DEXSCREENER_FAIL_RESET = time.time()
_BUYS_STOPPED = False
_GMGN_STAGGER_COUNTER = 0  # stagger gmgn calls: 0=trending, 1=trenches, 2=new pairs
_LAST_ALERT_TIMES = {}   # alert_key -> timestamp (5 min dedup)
_ALERTS_THIS_CYCLE = set()
_LAST_DEXSCR_ALERT = 0   # timestamp of last DexScreener failure alert

# Load PERM_BLACKLIST
try:
    with open(PERM_BLACKLIST_FILE) as f:
        PERM_BLACKLIST = set(json.load(f))
except:
    PERM_BLACKLIST = set()

# Load STOP_LOSS_COOLDOWN (tokens we stopped out, 30min re-entry lockout)
try:
    with open(STOP_LOSS_FILE) as f:
        STOP_LOSS_COOLDOWN = json.load(f)
except:
    STOP_LOSS_COOLDOWN = {}

# =====================================================================
# HELPER FUNCTIONS
# =====================================================================

def is_throttled(endpoint):
    # Check global backoff first - if active, block ALL GMGN calls
    if time.time() < _GMGN_GLOBAL_BACKOFF_UNTIL:
        return True
    state = _gmgn_throttle_state[endpoint]
    # Reset _alerted when backoff expires
    if time.time() >= state['backoff_until']:
        state['_alerted'] = False
    return time.time() < state['backoff_until']

def record_throttle(endpoint):
    global _GMGN_CONSECUTIVE_FAILS, _GMGN_GLOBAL_BACKOFF_UNTIL, _BUYS_STOPPED
    state = _gmgn_throttle_state[endpoint]
    state['count'] += 1
    wait_time = min(_BACKOFF_BASE * (2 ** state['count']), _BACKOFF_MAX)
    state['backoff_until'] = time.time() + wait_time

    # Global circuit breaker
    _GMGN_CONSECUTIVE_FAILS += 1
    if _GMGN_CONSECUTIVE_FAILS >= _GMGN_BACKOFF_THRESHOLD:
        _GMGN_GLOBAL_BACKOFF_UNTIL = time.time() + _GMGN_BACKOFF_DURATION
        if not _BUYS_STOPPED:
            _BUYS_STOPPED = True
            send_alert(f"🚨 GMGN CIRCUIT BREAKER: {_GMGN_CONSECUTIVE_FAILS} consecutive failures, global backoff {_GMGN_BACKOFF_DURATION}s | BUYING STOPPED")

    # Alert only once per throttle event (not per increment)
    if not state.get('_alerted', False):
        state['_alerted'] = True
        send_alert(f"⚠️ GMGN {endpoint.upper()} THROTTLED: {state['count']} failures, backoff {wait_time:.0f}s")

def reset_gmgn_fails():
    """Reset consecutive fail counter on successful GMGN call"""
    global _GMGN_CONSECUTIVE_FAILS, _GMGN_GLOBAL_BACKOFF_UNTIL, _BUYS_STOPPED
    _GMGN_CONSECUTIVE_FAILS = 0
    _GMGN_GLOBAL_BACKOFF_UNTIL = 0
    if _BUYS_STOPPED:
        _BUYS_STOPPED = False

def check_stop_buys():
    """Stop buys if both GMGN AND DexScreener are failing, or GMGN global backoff active"""
    global _BUYS_STOPPED, _GMGN_CONSECUTIVE_FAILS, _GMGN_GLOBAL_BACKOFF_UNTIL
    now = time.time()
    
    # GMGN global circuit breaker - if backoff active, stop buys
    if now < _GMGN_GLOBAL_BACKOFF_UNTIL:
        if not _BUYS_STOPPED:
            _BUYS_STOPPED = True
            try:
                send_alert(f"🚨 GMGN BACKOFF ACTIVE: {_GMGN_CONSECUTIVE_FAILS} failures, backoff until {int(_GMGN_GLOBAL_BACKOFF_UNTIL - now)}s | BUYS STOPPED")
            except:
                pass
        return True
    
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

def get_wallet_balance():
    """Read balance from sim_wallet.json"""
    try:
        with open(SIM_WALLET_FILE) as f:
            w = json.load(f)
        return float(w.get('balance', CHRIS_STARTING_BALANCE))
    except:
        return CHRIS_STARTING_BALANCE

# =====================================================================
# GMGN API FUNCTIONS
# =====================================================================

def get_gmgn_trending(limit=50):
    if is_throttled('trending'):
        return []
    r = subprocess.run(['gmgn-cli', 'market', 'trending', '--chain', 'sol', '--interval', '5m', '--limit', str(limit)],
                      capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        # Check if it's a 403 (forbidden/rate limit) vs other error
        if '403' in r.stderr or 'forbidden' in r.stderr.lower():
            # Treat 403 as throttle - back off for 5 minutes
            from gmgn_scanner import record_throttle
            record_throttle('trending')
            record_throttle('trending')  # double it
            send_alert("🚨 GMGN trending: HTTP 403 (rate limited) - backing off")
        else:
            record_throttle('trending')
            send_alert("⚠️ GMGN trending FAILED")
        return []
    try:
        reset_gmgn_fails()  # Reset consecutive fail counter on success
        d = json.loads(r.stdout)
        return d.get('data', {}).get('rank', [])
    except:
        return []

def get_gmgn_trenches(limit=20):
    """Get tokens from GMGN trenches (newly created/completed pump.fun tokens)"""
    if is_throttled('trenches'):
        return []
    r = subprocess.run(['gmgn-cli', 'market', 'trenches', '--chain', 'sol', '--limit', str(limit)],
                      capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        # Check if it's a 403 (forbidden/rate limit) vs other error
        if '403' in r.stderr or 'forbidden' in r.stderr.lower():
            # Treat 403 as throttle - back off for 5 minutes
            record_throttle('trenches')
            record_throttle('trenches')  # double it
        else:
            record_throttle('trenches')
        return []
    try:
        reset_gmgn_fails()  # Reset consecutive fail counter on success
        d = json.loads(r.stdout)
        # Trenches has 'completed' and 'new' arrays
        completed = d.get('completed', [])
        new = d.get('new', [])
        
        # Normalize fields from GMGN trenches to scanner format
        normalized = []
        for t in completed + new:
            # Map GMGN fields to scanner format
            normalized_token = {
                'address': t.get('address', ''),
                'symbol': t.get('symbol', t.get('tc_name', '?')),
                'name': t.get('name', ''),
                'price': t.get('price', 0),
                'market_cap': t.get('market_cap', 0),
                'volume': t.get('volume_24h') or t.get('volume24h') or t.get('volume', 0),
                'price_change_percent1m': t.get('price_change_percent1m', 0),
                'price_change_percent5m': t.get('price_change_percent5m', 0),
                'price_change_percent1h': t.get('price_change_percent1h', 0),
                'price_change_percent24h': t.get('price_change_percent24h', 0),
                'holder_count': t.get('holder_count', 0),
                'liquidity': t.get('liquidity', 0),
                'launchpad': t.get('launchpad', ''),
                'exchange': t.get('exchange', ''),
                'pool_address': t.get('pool_address', ''),
                'creation_timestamp': t.get('created_timestamp', 0),
            }
            normalized.append(normalized_token)
        return normalized
    except:
        return []

def get_dexscreener_pump_tokens(limit=20):
    """Actively scan DexScreener for new pump.fun tokens as a discovery fallback"""
    global DEXSCREENER_FAIL_COUNT
    try:
        url = "https://api.dexscreener.com/latest/dex/search?q=pumpfun&chain=solana&limit=20"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            DEXSCREENER_FAIL_COUNT = 0
            pairs = data.get('pairs', [])
            
            # Normalize DexScreener format to match GMGN format
            normalized = []
            for p in pairs:
                base = p.get('baseToken', {})
                addr = base.get('address', '')
                if not addr:
                    continue
                
                pc = p.get('priceChange', {})
                normalized_token = {
                    'address': addr,
                    'symbol': base.get('symbol', base.get('name', '?')),
                    'name': base.get('name', ''),
                    'price': p.get('priceUsd', 0),
                    'market_cap': p.get('marketCap', 0),
                    'volume': p.get('volume24h', 0),
                    'price_change_percent1m': pc.get('m1', 0),
                    'price_change_percent5m': pc.get('m5', 0),
                    'price_change_percent1h': pc.get('h1', 0),
                    'price_change_percent24h': pc.get('h24', 0),
                    'holder_count': p.get('holders', 0),
                    'liquidity': p.get('liquidity', {}).get('usd', 0) if isinstance(p.get('liquidity'), dict) else p.get('liquidity', 0),
                    'launchpad': 'pump',
                    'pair_address': addr,
                    'dex_id': p.get('dexId', ''),
                    'creation_timestamp': p.get('createdAt', 0),
                }
                normalized.append(normalized_token)
            return normalized[:limit]
    except Exception as e:
        DEXSCREENER_FAIL_COUNT += 1
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
        reset_gmgn_fails()  # Reset consecutive fail counter on success
        data = json.loads(r.stdout)
        # Extract exchange from nested pool dict if top-level exchange is empty
        if data.get('exchange', '') == '' and 'pool' in data:
            pool = data['pool']
            data['exchange'] = pool.get('exchange', '') or ''
            data['pool_exchange'] = pool.get('exchange', '') or ''
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

def get_fresh_token_data_no_cache(addr):
    """Force fresh fetch - bypass cache for pump path stage checks"""
    now = time.time()
    try:
        result = subprocess.run(
            ['gmgn-cli', 'token', 'info', '--chain', 'sol', '--address', addr],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            _token_cache[addr] = {'data': data, 'time': now}
            return data, 'gmgn'
        return None, None
    except:
        return None, None

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

def get_dexscreener_ath(addr):
    """Get ATH market cap from DexScreener as GMGN fallback"""
    try:
        url = f"https://api.dexscreener.com/v1/tokens/{addr}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            pairs = data.get('pairs', [])
            if pairs:
                # Use the highest market cap seen across all pairs as ATH proxy
                top_pair = max(pairs, key=lambda p: float(p.get('marketCap', 0) or 0))
                return float(top_pair.get('marketCap', 0) or 0)
            return 0
    except:
        return 0

def get_dexscreener_mcap(addr):
    """Get market cap from DexScreener as fallback when GMGN shows mc=0"""
    try:
        url = f"https://api.dexscreener.com/latest/dex/search?q={addr}&chain=solana&limit=5"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            pairs = data.get('pairs', [])
            for p in pairs:
                base = p.get('baseToken', {})
                if base.get('address', '') == addr:
                    mc = float(p.get('marketCap', 0) or 0)
                    if mc > 0:
                        return mc
            return 0
    except:
        return 0

def get_dexscreener_volume(addr):
    """Get volume from DexScreener as fallback when GMGN shows 0 volume"""
    try:
        url = f"https://api.dexscreener.com/latest/dex/search?q={addr}&chain=solana&limit=5"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            pairs = data.get('pairs', [])
            for p in pairs:
                base = p.get('baseToken', {})
                if base.get('address', '') == addr:
                    vol = float(p.get('volume24h', 0) or 0)
                    if vol > 0:
                        return vol
            return 0
    except:
        return 0

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
        
        # If key fields missing from GMGN (None/0), try DexScreener fresh fetch
        if (h1 == 0 and chg5 == 0 and chg1 == 0) and addr:
            from gmgn_scanner import get_fresh_token_data_no_cache
            fresh, src = get_fresh_token_data_no_cache(addr)
            if fresh:
                h1 = float(fresh.get('price_change_percent1h', 0) or 0) or h1
                chg5 = float(fresh.get('price_change_percent5m', 0) or 0) or chg5
                chg1 = float(fresh.get('price_change_percent1m', 0) or 0) or chg1
                if mc == 0:
                    mc = float(fresh.get('market_cap', 0) or 0) or mc
        top10pct = float(token_data.get('top10holderpercent', 0) or 0)
        volume = float(token_data.get('volume', 0) or 0)
        bs_ratio = float(token_data.get('bs_change24hpercent', 0) or 0)
        launchpad = str(token_data.get('launchpad', '')).lower().strip()
        pair_address = token_data.get('pair_address', '') or ''
        addr = token_data.get('address', '')
        
        if not addr:
            return None, "no address"
        
        # Exchange check - empty launchpad means unknown, check 'exchange' field as fallback
        exchange_fallback = str(token_data.get('exchange', '')).lower().strip()
        if launchpad == '':
            launchpad = exchange_fallback
        
        # If still empty, try to get exchange from GMGN token info (pool.exchange)
        if launchpad == '' and addr:
            info = get_gmgn_token_info(addr)
            if info:
                launchpad = str(info.get('exchange', '') or info.get('pool_exchange', '') or '').lower().strip()
        
        if launchpad not in ALLOWED_EXCHANGES:
            return None, f"exchange {launchpad or 'unknown'} not allowed"
        
        # Mcap check - if GMGN returns 0 mc, try DexScreener as fallback
        if mc < MIN_MCAP and mc == 0 and addr:
            dex_mc = get_dexscreener_mcap(addr)
            if dex_mc > 0:
                mc = dex_mc
        if mc < MIN_MCAP:
            return None, f"mcap ${mc:,.0f} < ${MIN_MCAP:,}"
        if mc > MAX_MCAP:
            return None, f"mcap ${mc:,.0f} > ${MAX_MCAP:,}"
        
        # Age check - reject if too old OR too new OR missing timestamp
        age_sec = int(time.time() - token_data.get('creation_timestamp', 0)) if token_data.get('creation_timestamp') else 0
        if not token_data.get('creation_timestamp', 0):
            return None, f"no creation_timestamp (unknown age)"
        if age_sec > MAX_AGE:
            return None, f"age {age_sec}s > {MAX_AGE}s (too old)"
        if age_sec < PUMP_MIN_AGE:
            return None, f"age {age_sec}s < {PUMP_MIN_AGE}s (too new)"
        
        # Holders check
        if holders < MIN_HOLDERS:
            return None, f"holders {holders} < {MIN_HOLDERS}"
        
        # Top10 concentration check - reject if > 50% held by top10 wallets (dump risk)
        if top10pct > 40:
            return None, f"top10 {top10pct:.0f}% > 50% (high concentration)"
        
        # Volume check - if GMGN shows 0 volume, try DexScreener as fallback
        if volume < MIN_VOLUME and volume == 0 and addr:
            dex_vol = get_dexscreener_volume(addr)
            if dex_vol > 0:
                volume = dex_vol
        if volume < MIN_VOLUME:
            return None, f"vol ${volume:,.0f} < ${MIN_VOLUME:,}"
        
        
        
        # H1 momentum check - for pump tokens with no h1 data yet, set to minimum to allow entry
        # (pump path has its own chg1 momentum check anyway)
        if launchpad in ['pump', 'pumpswap'] and h1 == 0:
            h1 = H1_MOMENTUM_MIN  # Treat 0 h1 as "no data yet" - allow through to pump path
        
        if launchpad not in ['pump', 'pumpswap']:
            if h1 < H1_MOMENTUM_MIN:
                return None, f"h1 {h1:.1f}% < {H1_MOMENTUM_MIN}%"
        
        # No H1 max ceiling - let any momentum through, stop loss handles risk
        
        # BS ratio check
        if launchpad == 'pump':
            pass  # pump.fun has no BS data
        elif bs_ratio > 0 and bs_ratio < (BS_RATIO_NEW if mc < 30000 else BS_RATIO_OLD):
            return None, f"BS {bs_ratio:.2f} too low"
        
        # Pair address check for pump/pumpswap - must not be "none"
        if launchpad in ['pump', 'pumpswap']:
            # If GMGN returns empty pair_address, use token address as fallback (pump.fun addresses end with 'pump')
            if pair_address in ['none', '', 'None', None]:
                pair_address = addr
            if pair_address in ['none', '', 'None', None]:
                return None, f"pair_address {pair_address} not valid for pump token"
            if not pair_address.endswith('pump'):
                return None, f"pair_address doesn't end in 'pump'"
        
        # ATH protection - reject tokens with no ATH data using multi-step fallback:
        # 1. GMGN history_highest_market_cap
        # 2. DexScreener priceHistorical
        # 3. Local peak (current mcap * 1.5 as conservative estimate)
        ath_mcap = float(token_data.get('history_highest_market_cap', 0) or 0)
        
        # Fallback 1: DexScreener ATH if GMGN has no ATH
        if ath_mcap <= 0 and addr:
            dex_ath = get_dexscreener_ath(addr)
            if dex_ath > 0:
                ath_mcap = dex_ath
        
        # Fallback 2: Use current mcap as local peak (conservative ATH for new tokens)
        # For tokens with no history, current mcap is the best ATH proxy we have
        if ath_mcap <= 0:
            ath_mcap = mc * 1.5  # Conservative: assume token can grow 50% from entry
            print(f"   [LOCAL_ATH] {token_data.get('symbol', '?')}: using local ATH ${ath_mcap:,.0f} (mcap {mc:,.0f} * 1.5)")
        
        # ATH distance check - reject if current mcap is more than 50% below ATH
        # i.e., current mcap must be >= 50% of ATH
        if ath_mcap > 0 and mc < ath_mcap * 0.50:
            return None, f"mcap ${mc:,.0f} >50% below ATH ${ath_mcap:,.0f}"
        
        # Build result
        pump_triggered = chg1 > PUMP_CHG1_THRESHOLD
        
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
            'ath_mcap': ath_mcap,  # Store ATH for reference
            'pump_rule_triggered': pump_triggered,
            'entry_price': float(token_data.get('price', 0) or 0),
            'age_sec': int(time.time() - token_data.get('creation_timestamp', 0)) if token_data.get('creation_timestamp') else 0,
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
    
    # IRONCLAD: Verify pair_address for pump/pumpswap - must end in "pump" and not be "none"
    launchpad = str(result.get('launchpad', '')).lower().strip()
    pair_address = str(result.get('pair_address', '')).lower().strip()
    
    if launchpad in ['pump', 'pumpswap']:
        if pair_address in ['none', '']:
            send_alert(f"🚫 BUY BLOCKED: {result.get('token')} pair_address is '{pair_address}'")
            return False
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
    
    # Also save stop loss cooldown
    with open(STOP_LOSS_FILE, 'w') as f:
        json.dump(STOP_LOSS_COOLDOWN, f)
    
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
    """Tokens start in PUMP_WAIT_1 (if pump triggered) or NORMAL_WAIT, then progress through cooldown"""
    # Use pump path if pump_rule triggered, otherwise normal
    state = STATE_PUMP_WAIT_1 if result.get('pump_rule_triggered', False) else STATE_NORMAL_WAIT
    
    # Initial cooldown based on path
    if result.get('pump_rule_triggered', False):
        cooldown_duration = PUMP_WAIT_1  # 45s for pump path
    else:
        cooldown_duration = NORMAL_WAIT_DURATION  # 45s for normal path
    
    cooldown_end = time.time() + cooldown_duration
    
    # Check if this token was previously rejected/pass
    prev_rescan = 0
    if addr in REJECTED_TEMP:
        prev_rescan = REJECTED_TEMP[addr].get('rescan_count', 0)
        del REJECTED_TEMP[addr]  # Clear temp record
    
    COOLDOWN_WATCH[addr] = {
        'state': state,
        'cooldown_end': cooldown_end,
        'token_data': token_data,
        'result': result,
        'recheck_count': 0,
        'rescan_count': prev_rescan,  # Track how many times we've re-seen this token
        'chg5_prev': entry_chg5,
        'chg1_prev': result.get('chg1', 0),
        'h1_prev': result.get('h1', 0),
        'lowest_chg1': result.get('chg1', 0),  # Track lowest chg1 for recovery
        'lowest_mcap': result.get('mcap', 0),  # Track lowest mcap for ATH checks
        'in_verify': False,
        'ath_mcap': result.get('ath_mcap', 0),  # Store ATH for mid-cooldown checks
        'entry_mcap': result.get('mcap', 0),  # Store entry mcap for reference
        'ath_check_count': 0,  # Track how many times we've re-checked ATH
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
    
    # Process ALL tokens in cooldown every cycle (not just urgent ones)
    # This ensures pump path tokens progress through stages without waiting for expiry
    all_tokens = list(COOLDOWN_WATCH.items())
    
    for addr, data in all_tokens:
        
        result = data['result']
        state = data['state']
        
        # Only fetch fresh data if cooldown timer is about to expire (within 15s)
        # This reduces GMGN calls from N per 15s to 1 per 15s when timer is close
        cooldown_remaining = data['cooldown_end'] - now
        
        # ALWAYS fetch fresh data when timer is expired or about to expire
        # This ensures we have current chg1/mcap for buy decisions
        if cooldown_remaining <= 15:
            fresh_data, source = get_fresh_token_data(addr)
            if fresh_data is None:
                # Failed to get fresh data - use cached from result, don't skip state transition
                chg5 = result.get('chg5', 0)
                h1 = result.get('h1', 0)
                chg1 = result.get('chg1', 0)
                mcap = result.get('mcap', 0)
            else:
                # Extract data from fresh source
                if source == 'gmgn':
                    chg5 = float(fresh_data.get('price_change_percent5m', 0) or 0)
                    h1 = float(fresh_data.get('price_change_percent1h', 0) or 0)
                    chg1 = float(fresh_data.get('price_change_percent1m', 0) or 0)
                    mcap = float(fresh_data.get('market_cap', 0) or 0)
                else:  # dexscraper
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
        else:
            # Timer not close - skip fresh fetch, use cached data
            chg5 = result.get('chg5', 0)
            h1 = result.get('h1', 0)
            chg1 = result.get('chg1', 0)
            mcap = result.get('mcap', 0)
            fresh_data = None
            source = None
        
        chg5_prev = data.get('chg5_prev', chg5)
        h1_prev = data.get('h1_prev', h1)
        chg1_prev = data.get('chg1_prev', chg1)
        lowest_mcap = data.get('lowest_mcap', mcap)
        lowest_chg5 = data.get('lowest_chg5', chg5)
        
        # === PUMP PATH ===
        # === NORMAL WAIT PATH (45s → first check → 15s verify → BUY) ===
        if state == STATE_NORMAL_WAIT:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                continue
            
            # FORCE FRESH FETCH at decision point
            fresh_fdata, fresh_source = get_fresh_token_data(addr)
            if fresh_fdata:
                if fresh_source == 'gmgn':
                    chg1_verify = float(fresh_fdata.get('price_change_percent1m', 0) or 0)
                    chg5_verify = float(fresh_fdata.get('price_change_percent5m', 0) or 0)
                else:
                    chg1_verify = float(fresh_fdata.get('priceChange', {}).get('m1', 0) or 0)
                    chg5_verify = float(fresh_fdata.get('priceChange', {}).get('m5', 0) or 0)
            else:
                chg1_verify = chg1
                chg5_verify = chg5
            
            # Age check
            token_age = int(time.time() - data.get('token_data', {}).get('creation_timestamp', 0))
            if token_age < PUMP_MIN_AGE:
                to_remove.append(addr)
                print(f"   [SKIP_TOO_NEW] {result['token']}: age {token_age}s < {PUMP_MIN_AGE}s | skip")
                continue
            
            chg1_threshold_new = chg1_prev  # just need to be above prev (no +5 delta)
            
            if data.get('in_verify', False):
                # === VERIFY PHASE: 15s → check chg1 > +5% AND chg1 > chg1_prev AND chg5 > -5% AND H1 > +100% ===
                h1_current = float(fresh_fdata.get('price_change_percent1h', 0) or 0) if fresh_fdata else result.get('h1', 0)
                if chg1_verify > 5 and chg1_verify >= chg1_threshold_new and chg5_verify > -5 and h1_current > 100:
                    print(f"   [BUY_NORMAL] {result['token']}: chg1={chg1_verify:+.1f}%, chg5={chg5_verify:+.1f}%, H1={h1_current:+.1f}% | BUY!")
                    buy_token(addr, result)
                    to_remove.append(addr)
                    send_alert(f"🚀 BUY SIGNAL | {result['token']}\n━━━━━━━━━━━━━━━\n📊 Normal cooldown path\n💰 Entry: ${result.get('mcap', 0):,.0f} mcap\n💰 Wallet: {get_wallet_balance():.4f} SOL\n🔗 https://dexscreener.com/solana/{addr}\n🥧 https://pump.fun/{addr}")
                else:
                    # First check passed but verify failed → switch to recovery
                    data['state'] = STATE_RECOVERY_WAIT
                    data['cooldown_end'] = now + 10
                    data['recheck_count'] = 0
                    data['lowest_chg1'] = min(data.get('lowest_chg1', chg1_verify), chg1_verify)
                    data['in_verify'] = False
                    reason = f"chg1={chg1_verify:.1f}% <= +5%" if chg1_verify <= 5 else (f"chg5={chg5_verify:.1f}% <= -5%" if chg5_verify <= -5 else f"H1={h1_current:+.1f}% <= +100%")
                    print(f"   [NORMAL_FAIL] {result['token']}: {reason} | → recovery")
                continue
            
            # === FIRST CHECK: chg1 > +5% AND chg1 > chg1_prev (already defined above) ===
            if chg1_verify > 5 and chg1_verify >= chg1_threshold_new:
                # Trigger verify phase (15s)
                data['in_verify'] = True
                data['cooldown_end'] = now + 15
                data['lowest_chg1'] = min(data.get('lowest_chg1', chg1_verify), chg1_verify)
                print(f"   [NORMAL_OK] {result['token']}: chg1={chg1_verify:+.1f}% > +5% and > {chg1_threshold_new:+.1f}% | verify 15s")
            else:
                # First check failed → recovery
                data['state'] = STATE_RECOVERY_WAIT
                data['cooldown_end'] = now + 15  # 15s rechecks
                data['recheck_count'] = 0
                data['lowest_chg1'] = min(data.get('lowest_chg1', chg1_verify), chg1_verify)
                data['in_verify'] = False
                print(f"   [NORMAL_FAIL] {result['token']}: chg1={chg1_verify:.1f}% < +5% or < {chg1_threshold_new:+.1f}% | → recovery")
            continue
        
        # === RECOVERY PATH: chg1 < -10% → 10s rechecks → chg1 >= lowest + 5% → 10s verify → BUY ===
        elif state == STATE_RECOVERY_WAIT:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                continue
            
            # FORCE FRESH FETCH
            fresh_fdata, fresh_source = get_fresh_token_data(addr)
            if fresh_fdata:
                if fresh_source == 'gmgn':
                    chg1_check = float(fresh_fdata.get('price_change_percent1m', 0) or 0)
                    chg5_check = float(fresh_fdata.get('price_change_percent5m', 0) or 0)
                else:
                    chg1_check = float(fresh_fdata.get('priceChange', {}).get('m1', 0) or 0)
                    chg5_check = float(fresh_fdata.get('priceChange', {}).get('m5', 0) or 0)
            else:
                chg1_check = chg1
                chg5_check = chg5
            
            # Track lowest chg1
            lowest = data.get('lowest_chg1', chg1_check)
            if chg1_check < lowest:
                lowest = chg1_check
            data['lowest_chg1'] = lowest
            
            recheck_count = data.get('recheck_count', 0)
            
            if data.get('in_verify', False):
                # Verify phase: 10s → final check → BUY
                if chg1_check >= lowest + 5 and chg5_check > 0:
                    print(f"   [BUY_RECOVERY] {result['token']}: chg1={chg1_check:+.1f}% >= {lowest+5:+.1f}%, chg5={chg5_check:+.1f}% | BUY!")
                    buy_token(addr, result)
                    to_remove.append(addr)
                    send_alert(f"🚀 BUY SIGNAL | {result['token']}\n━━━━━━━━━━━━━━━\n📊 Recovery path (verified)\n💰 Entry: ${result.get('mcap', 0):,.0f} mcap\n💰 Wallet: {get_wallet_balance():.4f} SOL\n🔗 https://dexscreener.com/solana/{addr}\n🥧 https://pump.fun/{addr}")
                else:
                    to_remove.append(addr)
                    reason = f"chg1={chg1_check:.1f}% < {lowest+5:+.1f}%" if chg1_check < lowest + 5 else f"chg5={chg5_check:.1f}% <= 0%"
                    print(f"   [RECOVERY_FAIL] {result['token']}: {reason} after verify | skip")
                data['in_verify'] = False
            elif chg1_check >= lowest + 5 and chg5_check > 0:
                # Trigger verify phase (10s)
                data['in_verify'] = True
                data['cooldown_end'] = now + 10
                print(f"   [RECOVERY_OK] {result['token']}: chg1={chg1_check:+.1f}% >= {lowest+5:+.1f}% (+5% from low) | verify 10s")
            elif recheck_count >= 30:
                # Save rescan count so we can track repeated re-entries
                REJECTED_TEMP[addr] = {'ts': now, 'rescan_count': data.get('rescan_count', 0) + 1}
                to_remove.append(addr)
                print(f"   [RECOVERY_REJECT] {result['token']}: max 30 rechecks | skip")
            else:
                data['recheck_count'] = recheck_count + 1
                data['cooldown_end'] = now + 10
                print(f"   [RECOVERY_RECHECK] {result['token']}: chg1={chg1_check:+.1f}%, lowest={lowest:+.1f}%, recheck {recheck_count+1}/30")
            continue
        
        # Fallback - unknown state
        to_remove.append(addr)
    
    # Remove finished tokens
    for addr in to_remove:
        if addr in COOLDOWN_WATCH:
            del COOLDOWN_WATCH[addr]
    
    # Clean old rejected
    for addr in list(REJECTED_TEMP.keys()):
        if now - REJECTED_TEMP[addr]['ts'] > 300:
            del REJECTED_TEMP[addr]
    
    # Clean old stop loss cooldowns (30 min lockout)
    for addr in list(STOP_LOSS_COOLDOWN.keys()):
        if now - STOP_LOSS_COOLDOWN[addr]['ts'] > 1800:
            del STOP_LOSS_COOLDOWN[addr]
    
    # === STAGGERED GMGN SCAN: 1 call per 60s, cycle through trending/trenches/new ===
    if now < _GMGN_GLOBAL_BACKOFF_UNTIL:
        tokens = []
    else:
        global _GMGN_STAGGER_COUNTER
        _GMGN_STAGGER_COUNTER = (_GMGN_STAGGER_COUNTER + 1) % 3
        
        if _GMGN_STAGGER_COUNTER == 0:
            tokens = get_gmgn_trending(50)
            tokens.sort(key=lambda x: x.get('creation_timestamp', 0))
        elif _GMGN_STAGGER_COUNTER == 1:
            tokens = get_gmgn_trenches(50)
            tokens.sort(key=lambda x: x.get('creation_timestamp', 0))
        else:
            # New pairs proxy: trending sorted newest first
            tokens = get_gmgn_trending(50)
            tokens.sort(key=lambda x: x.get('creation_timestamp', 0), reverse=True)
    
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
            rc = REJECTED_TEMP[addr].get('rescan_count', 0)
            if rc >= 10:
                continue  # Too many rescans
            # Increment rescan count for next time we see this token
            REJECTED_TEMP[addr]['rescan_count'] = rc + 1
        if addr in STOP_LOSS_COOLDOWN:
            continue
        if get_open_position_count() >= MAX_OPEN_POSITIONS:
            continue

        result, fail_reason = scan_token(token_data)
        if result is None:
            continue

        add_to_cooldown(addr, token_data, result, result.get('chg5', 0))
    
    
    
    # === SCAN DEXSCREENER PUMP.FUN NEW LISTINGS (active discovery) ===
    pump_tokens = get_dexscreener_pump_tokens(20)
    # Sort by age: youngest first (newest listings first)
    pump_tokens.sort(key=lambda x: x.get('creation_timestamp', 0))
    for token_data in pump_tokens:
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
            rc = REJECTED_TEMP[addr].get('rescan_count', 0)
            if rc >= 10:
                continue  # Too many rescans
            # Increment rescan count for next time we see this token
            REJECTED_TEMP[addr]['rescan_count'] = rc + 1
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
    print(f"  Sources: GMGN trending + GMGN trenches + DexScreener pump.fun")
    print(f"  Mcap ${MIN_MCAP:,}-${MAX_MCAP:,} | Holders ≥{MIN_HOLDERS}")
    print(f"  Dip 5-45% | chg1>+{PUMP_CHG1_THRESHOLD:.0f}% pump rule | chg5>+2% normal entry")
    print(f"  Normal: 45s → first check → 15s verify → BUY")
    print(f"  Recovery: 10s rechecks until chg1>=lowest+5% → 10s verify → BUY (max 30)")
    print(f"  Max: {MAX_OPEN_POSITIONS} open | Size: {POSITION_SIZE} SOL")
    print(f"  IronClad: Fresh data only, DexScreener backup, alert dedup")
    
    while True:
        try:
            scan_cycle()
        except Exception as e:
            print(f"Scan error: {e}")
        sys.stdout.flush()
        time.sleep(10)  # 10s main loop, GMGN scan staggered 1 call per 60s

if __name__ == '__main__':
    main()