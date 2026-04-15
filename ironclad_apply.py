#!/usr/bin/env python3
"""Apply IRONCLAD fixes cleanly"""

with open('/root/Dex-trading-bot/gmgn_scanner.py', 'r') as f:
    code = f.read()

# 1. Add IRONCLAD trackers after _buys_stopped
old_trackers = """_buys_stopped = False
_last_buys_stopped_alert = 0

PERM_BLACKLIST = set()"""

new_trackers = """_buys_stopped = False
_last_buys_stopped_alert = 0

# === IRONCLAD TRACKERS ===
ALERTS_THIS_CYCLE = set()  # Deduplication per scan cycle
_LAST_ALERT_TIMES = {}     # alert_key -> timestamp (5 min dedup)
DEXSCREENER_FAIL_COUNT = 0
DEXSCREENER_FAIL_RESET = time.time()

PERM_BLACKLIST = set()"""

code = code.replace(old_trackers, new_trackers)

# 2. Add DexScreener function and send_alert after check_stop_buys
old_check_stop = """def check_stop_buys():
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
    return _buys_stopped"""

new_check_stop = """def check_stop_buys():
    global _buys_stopped, _last_buys_stopped_alert, DEXSCEENER_FAIL_COUNT
    now = time.time()
    gmgn_throttled = any(time.time() < s['backoff_until'] for s in _gmgn_throttle_state.values())
    
    # Reset DexScreener fail count after 1 hour
    if now - DEXSCREENER_FAIL_RESET > 3600:
        DEXSCEENER_FAIL_COUNT = 0
        DEXSCREENER_FAIL_RESET = now
    
    if gmgn_throttled and DEXSCEENER_FAIL_COUNT >= 5:
        if not _buys_stopped:
            _buys_stopped = True
            msg = f"🚨🚨 STOPPING ALL BUYS: GMGN throttled + DexScreener failing"
            print(f"! {msg}")
            alert_sender_webhook(msg)
            _last_buys_stopped_alert = now
    else:
        if _buys_stopped and not (gmgn_throttled and DEXSCEENER_FAIL_COUNT >= 5):
            _buys_stopped = False
            msg = f"✅ RESUMING BUYS: APIs recovered"
            print(f"! {msg}")
            alert_sender_webhook(msg)
    return _buys_stopped

def get_dexscreener_token(addr):
    \"\"\"Fetch token data from DexScreener as GMGN backup\"\"\"
    global DEXSCEENER_FAIL_COUNT
    if DEXSCEENER_FAIL_COUNT >= 5:
        return None
    try:
        import urllib.request
        url = f"https://api.dexscreener.io/v1/tokens/{addr}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            DEXSCEENER_FAIL_COUNT = 0
            return data
    except:
        DEXSCEENER_FAIL_COUNT += 1
        if DEXSCEENER_FAIL_COUNT >= 5:
            alert_sender_webhook(f"⚠️ DexScreener FAILED {DEXSCEENER_FAIL_COUNT}x - stopping calls for 1 hour")
        return None

def send_alert(msg):
    \"\"\"Send alert with deduplication - once per type per 5 min\"\"\"
    alert_key = msg[:60]
    now = time.time()
    if alert_key in _LAST_ALERT_TIMES:
        if now - _LAST_ALERT_TIMES[alert_key] < 300:
            return  # Skip duplicate
    _LAST_ALERT_TIMES[alert_key] = now
    alert_sender_webhook(msg)

def get_fresh_token_data(addr):
    \"\"\"Get fresh token data: try GMGN first, then DexScreener\"\"\"
    # Try GMGN first
    info = get_gmgn_token_info(addr)
    if info and info.get('price_change_percent1h') is not None:
        return info, 'gmgn'
    
    # Try DexScreener
    dex_data = get_dexscreener_token(addr)
    if dex_data and dex_data.get('priceChange', {}).get('h1') is not None:
        return dex_data, 'dexscreener'
    
    return None, None"""

code = code.replace(old_check_stop, new_check_stop)

# 3. Update scan_cycle to reset ALERTS_THIS_CYCLE
old_scan_cycle_start = """def scan_cycle():
    global COOLDOWN_WATCH, REJECTED_TEMP
    now = time.time()"""

new_scan_cycle_start = """def scan_cycle():
    global COOLDOWN_WATCH, REJECTED_TEMP, ALERTS_THIS_CYCLE
    ALERTS_THIS_CYCLE.clear()  # Reset per-cycle alert dedup
    now = time.time()"""

code = code.replace(old_scan_cycle_start, new_scan_cycle_start)

# 4. Update get_gmgn_trending to alert on failure
old_trending = """def get_gmgn_trending(limit=50):
    if is_throttled('trending'):
        return []
    r = subprocess.run(['gmgn-cli', 'market', 'trending', '--chain', 'sol', '--interval', '5m', '--limit', str(limit)],
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
        return []
    r = subprocess.run(['gmgn-cli', 'market', 'trending', '--chain', 'sol', '--interval', '5m', '--limit', str(limit)],
                      capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        record_throttle('trending')
        send_alert(f"⚠️ GMGN trending FAILED - throttled")
        return []
    try:
        d = json.loads(r.stdout)
        tokens = d.get('data', {}).get('rank', [])
        if not tokens and r.returncode == 0:
            send_alert(f"⚠️ GMGN trending returned EMPTY")
        return tokens
    except:
        return []"""

code = code.replace(old_trending, new_trending)

# 5. Update get_gmgn_token_info to alert and return None on stale
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
        # Check for stale data - GMGN returns None for price when stale
        if data.get('price_change_percent1h') is None:
            send_alert(f"⚠️ GMGN data STALE for {addr[:20]}...")
            return None
        return data
    except:
        return None"""

code = code.replace(old_token_info, new_token_info)

# 6. Update cooldown cycle to use get_fresh_token_data
old_fresh_update = """        # Fresh GMGN data for recheck
        fresh = get_gmgn_token_info(addr)
        if not fresh:
            to_remove.append(addr)
            continue
        
        # Use fresh data if available, otherwise keep cached
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

new_fresh_update = """        # Fresh data: GMGN first, DexScreener backup
        fresh_data, source = get_fresh_token_data(addr)
        
        if fresh_data:
            if source == 'gmgn':
                fresh_h1 = float(fresh_data.get('price_change_percent1h', 0) or 0)
                fresh_chg5 = float(fresh_data.get('price_change_percent5m', 0) or 0)
                fresh_chg1 = float(fresh_data.get('price_change_percent1m', 0) or 0)
                fresh_mcap = float(fresh_data.get('market_cap', 0) or 0)
            else:  # dexscanner
                pc = fresh_data.get('priceChange', {})
                fresh_h1 = float(pc.get('h1', 0) or 0)
                fresh_chg5 = float(pc.get('m5', 0) or 0)
                fresh_chg1 = float(pc.get('m1', 0) or 0)
                fresh_mcap = float(fresh_data.get('marketCap', 0) or 0)
            
            if fresh_h1 > 0 or fresh_chg5 != 0:
                chg5 = fresh_chg5
                h1 = fresh_h1
                chg1 = fresh_chg1
                mcap = fresh_mcap
                result['chg5'] = chg5
                result['h1'] = h1
                result['chg1'] = chg1
                result['mcap'] = mcap
                if state == STATE_CHG1_RECHECK:
                    data['lowest_mcap'] = min(data.get('lowest_mcap', mcap), mcap)
            else:
                # Data still stale from both sources
                send_alert(f"⚠️ Data STALE for {result['token']} - removing from cooldown")
                to_remove.append(addr)
                continue
        else:
            # No fresh data - remove from cooldown, stop buys
            send_alert(f"🚫 NO FRESH DATA for {result['token']} - skipping")
            to_remove.append(addr)
            continue"""

code = code.replace(old_fresh_update, new_fresh_update)

# 7. Add buy blocker for pump path
old_buy_pump = """            print(f"   [BUY_PUMP] {result['token']}: confirmed | BUY!")
                buy_token(addr, result)
                to_remove.append(addr)
                continue
            else:
                data['state'] = STATE_RECOVERY_WAIT"""

new_buy_pump = """            # Block buy if no fresh data
            if not fresh_data:
                send_alert(f"🚫 BUY BLOCKED: {result['token']} - no fresh data")
                data['cooldown_end'] = now + 30
                continue
            print(f"   [BUY_PUMP] {result['token']}: confirmed | BUY!")
                buy_token(addr, result)
                to_remove.append(addr)
                continue
            else:
                data['state'] = STATE_RECOVERY_WAIT"""

code = code.replace(old_buy_pump, new_buy_pump)

with open('/root/Dex-trading-bot/gmgn_scanner.py', 'w') as f:
    f.write(code)

print("Done. Compile with: cd /root/Dex-trading-bot && /root/Dex-trading-bot/venv/bin/python -m py_compile gmgn_scanner.py")