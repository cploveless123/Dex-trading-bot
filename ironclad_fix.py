#!/usr/bin/env python3
"""
IRONCLAD RULES FIX - gmgn_scanner.py
Implements:
1. DexScreener backup when GMGN data stale/missing
2. Throttle count tracking (>5 failures/hour → stop calls)
3. Alert throttling (once per cycle)
4. No duplicate alerts
5. Fresh data verification
"""

with open('/root/Dex-trading-bot/gmgn_scanner.py', 'r') as f:
    code = f.read()

# =====================================================================
# PART 1: Add DexScreener functions and throttle tracking
# =====================================================================

# Find where global variables are defined and add new trackers
old_globals = """GMGN_SCANNER_VERSION = "v7.3"
COOLDOWN_WATCH = {}  # addr -> {state, cooldown_end, ...}
REJECTED_TEMP = {}   # addr -> {ts, reason}"""

new_globals = """GMGN_SCANNER_VERSION = "v7.3"
COOLDOWN_WATCH = {}  # addr -> {state, cooldown_end, ...}
REJECTED_TEMP = {}   # addr -> {ts, reason}

# === IRONCLAD TRACKERS ===
THROTTLE_COUNT = {}  # endpoint -> count in last hour
LAST_ALERT_TIME = {}  # alert_type -> timestamp
ALERTS_THIS_CYCLE = set()  # alerts sent this scan cycle (reset each cycle)

# DexScreener backup
DEXSCREENER_BASE = "https://api.dexscreener.io"
DEXSCREENER_FAIL_COUNT = 0
DEXSCREENER_FAIL_WINDOW = 3600  # 1 hour
DEXSCREENER_MAX_FAILS = 5
LAST_DEXSCEENER_RESET = time.time()

def get_dexscreener_token(addr):
    \"\"\"Fetch token data from DexScreener as GMGN backup\"\"\"
    global DEXSCREENER_FAIL_COUNT, LAST_DEXSCEENER_RESET
    
    # Check if we've exceeded failure limit
    if DEXSCEENER_FAIL_COUNT >= DEXSCEENER_MAX_FAILS:
        return None
    
    try:
        url = f"{DEXSCREENER_BASE}/v1/tokens/{addr}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            # Reset fail count on success
            DEXSCEENER_FAIL_COUNT = 0
            return data
    except Exception as e:
        DEXSCEENER_FAIL_COUNT += 1
        if DEXSCEENER_FAIL_COUNT >= DEXSCEENER_MAX_FAILS:
            send_alert(f"⚠️ DexScreener FAILED {DEXSCEENER_FAIL_COUNT}x - stopping API calls for 1 hour")
            LAST_DEXSCEENER_RESET = time.time()
        return None

def check_and_reset_dexscreener():
    \"\"\"Reset DexScreener fail count after 1 hour\"\"\"
    global DEXSCEENER_FAIL_COUNT, LAST_DEXSCEENER_RESET
    if time.time() - LAST_DEXSCEENER_RESET > 3600:
        DEXSCEENER_FAIL_COUNT = 0
        LAST_DEXSCEENER_RESET = time.time()

def record_throttle(endpoint):
    \"\"\"Record throttle with 1-hour window tracking\"\"\"
    now = time.time()
    if endpoint not in THROTTLE_COUNT:
        THROTTLE_COUNT[endpoint] = {'count': 0, 'window_start': now}
    
    # Reset window if expired
    if now - THROTTLE_COUNT[endpoint]['window_start'] > 3600:
        THROTTLE_COUNT[endpoint] = {'count': 0, 'window_start': now}
    
    THROTTLE_COUNT[endpoint]['count'] += 1
    
    # Alert only once per cycle if throttled
    alert_key = f"THROTTLE_{endpoint}"
    if alert_key not in ALERTS_THIS_CYCLE:
        ALERTS_THIS_CYCLE.add(alert_key)
        # Don't send here - let send_alert handle it

def send_alert(msg, force=False):
    \"\"\"Send alert with deduplication - only once per alert type per hour\"\"\"
    alert_key = msg[:50]  # Use first 50 chars as key
    
    # Check if we sent this alert recently (within 5 min)
    now = time.time()
    if alert_key in LAST_ALERT_TIME:
        if now - LAST_ALERT_TIME[alert_key] < 300:
            return  # Duplicate, skip
    
    # Check cycle duplicates
    if alert_key in ALERTS_THIS_CYCLE and not force:
        return  # Already sent this cycle
    
    LAST_ALERT_TIME[alert_key] = now
    
    try:
        import urllib.request, urllib.parse
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
        req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode())
        urllib.request.urlopen(req, timeout=10)
    except:
        pass

def is_data_fresh(data, source="gmgn"):
    \"\"\"Check if data appears fresh (not stale)\"\"\"
    if not data:
        return False
    if source == "gmgn":
        # GMGN returns price_change_percent1h as None when stale
        h1 = data.get('price_change_percent1h')
        if h1 is None:
            return False
        return True
    elif source == "dexscreener":
        # DexScreener returns None or very old data when stale
        if 'priceChange' not in data:
            return False
        return True
    return False

def get_fresh_token_data(addr, prefer_gmgn=True):
    \"\"\"Get fresh token data from GMGN, fallback to DexScreener\"\"\"
    fresh_data = None
    source = None
    
    if prefer_gmgn:
        # Try GMGN first
        gmgn_data = get_gmgn_token_info(addr)
        if is_data_fresh(gmgn_data, "gmgn"):
            fresh_data = gmgn_data
            source = "gmgn"
    
    if not fresh_data:
        # Try DexScreener
        dex_data = get_dexscreener_token(addr)
        if is_data_fresh(dex_data, "dexscreener"):
            fresh_data = dex_data
            source = "dexscreener"
    
    return fresh_data, source"""

code = code.replace(old_globals, new_globals)

# =====================================================================
# PART 2: Fix get_gmgn_token_info to detect stale data
# =====================================================================

old_token_info = """def get_gmgn_token_info(addr):
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
        return None"""

new_token_info = """def get_gmgn_token_info(addr):
    if is_throttled('token_info'):
        send_alert("⚠️ GMGN token_info THROTTLED - using DexScreener backup")
        return None
    r = subprocess.run(['gmgn-cli', 'token', 'info', '--chain', 'sol', '--address', addr],
                      capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        record_throttle('token_info')
        send_alert("⚠️ GMGN token_info FAILED - trying DexScreener backup")
        return None
    try:
        data = json.loads(r.stdout)
        # Verify data is fresh - GMGN returns None for price when stale
        if data and data.get('price_change_percent1h') is None:
            send_alert("⚠️ GMGN data STALE for {} - using DexScreener".format(addr[:20]))
            return None
        return data
    except:
        return None"""

code = code.replace(old_token_info, new_token_info)

# =====================================================================
# PART 3: Add DexScreener fetch for new tokens (backup for GMGN trending)
# =====================================================================

old_trending = """def get_gmgn_trending(limit=50):
    if is_throttled('trending'):
        return []
    r = subprocess.run(['gmgn-cli', 'market', 'trending', '--chain', 'sol', '--interval', '5m', f'--limit={limit}'],
                      capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        record_throttle('trending')
        return []
    try:
        d = json.loads(r.stdout)
        return d.get('data', {}).get('rank', [])
    except:
        return []"""

new_trending = """def get_gmgn_trending(limit=50):
    if is_throttled('trending'):
        send_alert("⚠️ GMGN trending THROTTLED")
        return []
    r = subprocess.run(['gmgn-cli', 'market', 'trending', '--chain', 'sol', '--interval', '5m', f'--limit={limit}'],
                      capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        record_throttle('trending')
        send_alert("⚠️ GMGN trending FAILED")
        return []
    try:
        d = json.loads(r.stdout)
        tokens = d.get('data', {}).get('rank', [])
        if not tokens:
            send_alert("⚠️ GMGN trending returned EMPTY - check API")
        return tokens
    except:
        return []"""

code = code.replace(old_trending, new_trending)

# =====================================================================
# PART 4: Update cooldown cycle to use fresh data verification
# =====================================================================

old_fresh_check = """        # Use fresh data if available, otherwise keep cached
        fresh_h1 = float(fresh.get('price_change_percent1h', 0) or 0)
        fresh_chg5 = float(fresh.get('price_change_percent5m', 0) or 0)
        fresh_chg1 = float(fresh.get('price_change_percent1m', 0) or 0)
        fresh_mcap = float(fresh.get('market_cap', 0) or 0)
        
        # Only update if token_info returned valid data (not 0/None)
        if fresh_h1 > 0:
            chg5 = float(fresh_chg5)
            h1 = float(fresh_h1)
            chg1 = float(fresh_chg1)
            mcap = float(fresh_mcap)
            result['chg5'] = chg5
            result['h1'] = h1
            result['chg1'] = chg1
            result['mcap'] = mcap
            # Update lowest_mcap if in CHG1_RECHECK state
            if state == STATE_CHG1_RECHECK:
                data['lowest_mcap'] = min(data.get('lowest_mcap', mcap), mcap)
        else:
            # token_info doesn't have price data - use cached values from cooldown entry
            chg5 = result.get('chg5', 0)
            h1 = result.get('h1', 0)
            chg1 = result.get('chg1', 0)
            mcap = result.get('mcap', 0)"""

new_fresh_check = """        # Use FRESH data only - never stale
        # First try GMGN, if stale/missing try DexScreener
        fresh_data, data_source = get_fresh_token_data(addr, prefer_gmgn=True)
        
        if fresh_data and is_data_fresh(fresh_data, data_source):
            if data_source == "gmgn":
                fresh_h1 = float(fresh_data.get('price_change_percent1h', 0) or 0)
                fresh_chg5 = float(fresh_data.get('price_change_percent5m', 0) or 0)
                fresh_chg1 = float(fresh_data.get('price_change_percent1m', 0) or 0)
                fresh_mcap = float(fresh_data.get('market_cap', 0) or 0)
            else:  # dexscreener
                fresh_h1 = float(fresh_data.get('priceChange', {}).get('h1', 0) or 0)
                fresh_chg5 = float(fresh_data.get('priceChange', {}).get('m5', 0) or 0)
                fresh_chg1 = float(fresh_data.get('priceChange', {}).get('m1', 0) or 0)
                fresh_mcap = float(fresh_data.get('marketCap', 0) or 0)
            
            if fresh_h1 > 0 or fresh_chg5 != 0:
                chg5 = float(fresh_chg5)
                h1 = float(fresh_h1)
                chg1 = float(fresh_chg1)
                mcap = float(fresh_mcap)
                result['chg5'] = chg5
                result['h1'] = h1
                result['chg1'] = chg1
                result['mcap'] = mcap
                # Update lowest_mcap if in CHG1_RECHECK state
                if state == STATE_CHG1_RECHECK:
                    data['lowest_mcap'] = min(data.get('lowest_mcap', mcap), mcap)
            else:
                # Data still stale - use cached or skip this token
                send_alert(f"⚠️ Data STALE for {result['token']} - skipping update")
                to_remove.append(addr)
                continue
        else:
            # No fresh data available from either source
            send_alert(f"⚠️ NO FRESH DATA for {result['token']} - stopping buys until fixed")
            # Don't remove from cooldown, but flag to stop buys
            result['_no_fresh_data'] = True
            continue"""

code = code.replace(old_fresh_check, new_fresh_check)

# =====================================================================
# PART 5: Add buy blocker when no fresh data
# =====================================================================

# Find the buy_token calls and add fresh data check
old_buy_check = """                print(f"   [BUY_PUMP] {result['token']}: confirmed | BUY!")
                buy_token(addr, result)
                to_remove.append(addr)
                continue"""

new_buy_check = """                # Check fresh data before buy
                if result.get('_no_fresh_data'):
                    send_alert(f"🚫 BUY BLOCKED: {result['token']} - no fresh data")
                    data['cooldown_end'] = now + 30  # Recheck in 30s
                    continue
                print(f"   [BUY_PUMP] {result['token']}: confirmed | BUY!")
                buy_token(addr, result)
                to_remove.append(addr)
                continue"""

code = code.replace(old_buy_check, new_buy_check)

# Find other BUY calls and add same check
old_buy_normal = """                    print(f"   [BUY_BASE] {result['token']}: chg1={chg1:+.1f}% >= {chg1_threshold:+.1f}% from last | BUY!")
                    buy_token(addr, final_result)
                    to_remove.append(addr)
                    continue"""

new_buy_normal = """                    if result.get('_no_fresh_data'):
                        send_alert(f"🚫 BUY BLOCKED: {result['token']} - no fresh data")
                        data['cooldown_end'] = now + 30
                        continue
                    print(f"   [BUY_BASE] {result['token']}: chg1={chg1:+.1f}% >= {chg1_threshold:+.1f}% from last | BUY!")
                    buy_token(addr, final_result)
                    to_remove.append(addr)
                    continue"""

code = code.replace(old_buy_normal, new_buy_normal)

# =====================================================================
# PART 6: Add scan cycle reset for ALERTS_THIS_CYCLE
# =====================================================================

# Find the beginning of scan_cycle and add cycle reset
old_scan_cycle_start = """def scan_cycle():
    global COOLDOWN_WATCH, REJECTED_TEMP
    now = time.time()"""

new_scan_cycle_start = """def scan_cycle():
    global COOLDOWN_WATCH, REJECTED_TEMP, ALERTS_THIS_CYCLE, DEXSCEENER_FAIL_COUNT
    
    # Reset per-cycle alert tracking
    ALERTS_THIS_CYCLE.clear()
    
    # Check DexScreener reset window
    check_and_reset_dexscreener()
    
    # Check if overall API health is bad
    total_throttles = sum(THROTTLE_COUNT.get(k, {}).get('count', 0) for k in THROTTLE_COUNT)
    if total_throttles > 10:
        send_alert(f"🚨 API HEALTH WARNING: {total_throttles} throttles detected - monitoring closely")
    
    now = time.time()"""

code = code.replace(old_scan_cycle_start, new_scan_cycle_start)

# =====================================================================
# PART 7: Add BUY blockers for all buy paths
# =====================================================================

# Find [BUY_YOUNG] and add check
old_buy_young = """                    print(f"   [BUY_YOUNG] {result['token']}: chg1={chg1:+.1f}% >= -5% + chg5={chg5:+.1f}% >= +2% | BUY!")
                    buy_token(addr, final_result)
                    to_remove.append(addr)
                    continue"""

new_buy_young = """                    if result.get('_no_fresh_data'):
                        send_alert(f"🚫 BUY BLOCKED: {result['token']} - no fresh data")
                        data['cooldown_end'] = now + 30
                        continue
                    print(f"   [BUY_YOUNG] {result['token']}: chg1={chg1:+.1f}% >= -5% + chg5={chg5:+.1f}% >= +2% | BUY!")
                    buy_token(addr, final_result)
                    to_remove.append(addr)
                    continue"""

code = code.replace(old_buy_young, new_buy_young)

# Find [BUY_OLDER] and add check
old_buy_older = """                    print(f"   [BUY_OLDER] {result['token']}: chg1={chg1:+.1f}% >= -5% + chg5={chg5:+.1f}% >= +2% | BUY!")
                    buy_token(addr, final_result)
                    to_remove.append(addr)
                    continue"""

new_buy_older = """                    if result.get('_no_fresh_data'):
                        send_alert(f"🚫 BUY BLOCKED: {result['token']} - no fresh data")
                        data['cooldown_end'] = now + 30
                        continue
                    print(f"   [BUY_OLDER] {result['token']}: chg1={chg1:+.1f}% >= -5% + chg5={chg5:+.1f}% >= +2% | BUY!")
                    buy_token(addr, final_result)
                    to_remove.append(addr)
                    continue"""

code = code.replace(old_buy_older, new_buy_older)

# Find [BUY_CHG1] and add check
old_buy_chg1 = """                print(f"   [BUY_CHG1] {result['token']}: chg1 recovered | BUY!")
                buy_token(addr, final_result)
                to_remove.append(addr)
                continue"""

new_buy_chg1 = """                if result.get('_no_fresh_data'):
                    send_alert(f"🚫 BUY BLOCKED: {result['token']} - no fresh data")
                    data['cooldown_end'] = now + 30
                    continue
                print(f"   [BUY_CHG1] {result['token']}: chg1 recovered | BUY!")
                buy_token(addr, final_result)
                to_remove.append(addr)
                continue"""

code = code.replace(old_buy_chg1, new_buy_chg1)

# =====================================================================
# PART 8: Update alert_sender_webhook to use send_alert
# =====================================================================

old_webhook = """def alert_sender_webhook(msg):
    try:
        import urllib.request, urllib.parse
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
        req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode())
        urllib.request.urlopen(req, timeout=10)
    except:
        pass"""

new_webhook = """def alert_sender_webhook(msg):
    send_alert(msg)  # Use unified send_alert with deduplication"""

code = code.replace(old_webhook, new_webhook)

with open('/root/Dex-trading-bot/gmgn_scanner.py', 'w') as f:
    f.write(code)

print("IRONCLAD fixes applied. Compile with: cd /root/Dex-trading-bot && /root/Dex-trading-bot/venv/bin/python -m py_compile gmgn_scanner.py")