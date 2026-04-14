#!/usr/bin/env python3
"""
GMGN Scanner v7.0 - Wilson Bot
Chris's Cooldown Rules: Let coin find ATH, buy the pullback reversal
"""

import json
import time
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from trading_constants import (
    MIN_MCAP, MAX_MCAP, MIN_AGE_SECONDS, MAX_AGE_SECONDS,
    MIN_5MIN_VOLUME, MIN_HOLDERS, TOP10_HOLDER_MAX,
    BS_RATIO_NEW, BS_RATIO_OLD, BS_PUMP_FUN_OK,
    H1_MOMENTUM_MIN, H24_MOMENTUM_MIN,
    MIN_CHG1_FOR_BUY, CHG1_IMPROVEMENT_MIN, CHG1_MIN_VALUE,
    DIP_MIN, DIP_MAX, ATH_DIVERGENCE_MAX,
    BASE_COOLDOWN, CHG1_RECHECK_DELAY, CHG1_VERIFY_DELAY, CHG1_RECOVERY_WAIT,
    VERIFY_CONSECUTIVE_OK,
    MAX_RECHECKS, REJECTED_REVISIT_DELAY,
    PRICE_DROP_REJECT,
    H1_PARABOLIC_REJECT,
    LIQUIDITY_MIN,
    TP1_PERCENT, TP1_TRAILING_PCT, TP1_SELL_PCT,
    TP2_PERCENT, TP2_TRAILING_PCT, TP2_SELL_PCT,
    TP3_PERCENT, TP3_TRAILING_PCT, TP3_SELL_PCT,
    TP4_PERCENT, TP4_TRAILING_PCT, TP4_SELL_PCT,
    TP5_PERCENT, TP5_TRAILING_PCT, TP5_SELL_PCT,
    TRAILING_STOP_PCT, STOP_LOSS_PERCENT,
    ALLOWED_EXCHANGES,
    SIM_RESET_TIMESTAMP,
    MAX_OPEN_POSITIONS, POSITION_SIZE,
)

# === DATA FILES ===
TRADES_FILE = Path("/root/Dex-trading-bot/trades/sim_trades.jsonl")
PERM_BLACKLIST_FILE = Path("/root/Dex-trading-bot/permanent_blacklist.json")

# === STATE ===
COOLDOWN_WATCH = {}
REJECTED_TEMP = {}
PERM_BLACKLIST = set()
_gmgn_throttle_count = 0
_gmgn_last_throttle_alert = 0

# ======= GMGN DATA =======
def gmgn_query(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if r.returncode == 0:
            global _gmgn_throttle_count
            _gmgn_throttle_count = 0
            return json.loads(r.stdout)
        elif 'rate limit' in r.stderr.lower() or '429' in r.stderr:
            _gmgn_throttle_count += 1
            now = time.time()
            if _gmgn_throttle_count >= 3 and (now - _gmgn_last_throttle_alert) > 300:
                print(f"GMGN THROTTLED: {_gmgn_throttle_count}")
                _gmgn_last_throttle_alert = now
    except:
        _gmgn_throttle_count += 1
    return None

def get_gmgn_trending(limit=50):
    d = gmgn_query(['gmgn-cli', 'market', 'trending', '--chain', 'sol', '--interval', '5m', '--limit', str(limit)])
    return d.get('data', {}).get('rank', []) if d else []

def get_gmgn_pumpfun_lowcap(limit=30):
    d = gmgn_query(['gmgn-cli', 'market', 'trending', '--chain', 'sol', '--interval', '5m', '--limit', str(limit),
                    '--platform', 'Pump.fun', '--order-by', 'marketcap', '--direction', 'asc'])
    return d.get('data', {}).get('rank', []) if d else []

def get_gmgn_new_pairs(limit=30):
    d = gmgn_query(['gmgn-cli', 'market', 'trenches', '--chain', 'sol', '--limit', str(limit)])
    if not d:
        return []
    pairs = []
    for k in ('creating', 'created', 'completed'):
        pairs.extend(d.get(k, []) or [])
    return pairs

def get_gmgn_token_info(addr):
    return gmgn_query(['gmgn-cli', 'token', 'info', '--chain', 'sol', '--address', addr])

def get_dexscreener_data(addr):
    try:
        import requests
        r = requests.get(f'https://api.dexscreener.com/v1/tokens/{addr}', timeout=8)
        if r.status_code == 200:
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
    except:
        pass
    return None

# ======= BLACKLIST =======
def load_blacklist():
    global PERM_BLACKLIST
    PERM_BLACKLIST = set()
    if PERM_BLACKLIST_FILE.exists():
        try:
            PERM_BLACKLIST = set(json.load(open(PERM_BLACKLIST_FILE)))
        except:
            PERM_BLACKLIST = set()
    if TRADES_FILE.exists():
        for line in open(TRADES_FILE):
            try:
                t = json.loads(line)
                if t.get('action') == 'BUY':
                    PERM_BLACKLIST.add(t.get('token_address', ''))
            except:
                pass

# ======= FRESH DATA MERGE =======
def merge_token_data(gmgn_data, dex_data):
    """GMGN primary, DexScreener fills gaps. Always fresh."""
    merged = {}
    if gmgn_data:
        merged = gmgn_data.copy()
    if dex_data:
        # DexScreener fills missing/zero fields
        for k, v in dex_data.items():
            if v and (not merged.get(k) or merged.get(k) == 0):
                merged[k] = v
        # Specific DexScreener overrides
        ds_chg1 = dex_data.get('priceChange', {}).get('m1') if dex_data.get('priceChange') else None
        if ds_chg1 is not None:
            merged['price_change_percent1m'] = float(ds_chg1)
        ds_price = dex_data.get('priceUsd') or dex_data.get('price')
        if ds_price and not merged.get('price'):
            merged['price'] = float(ds_price)
    return merged

# ======= TOKEN SCAN =======
def scan_token(gmgn_data, dex_data):
    merged = merge_token_data(gmgn_data, dex_data)
    
    symbol = merged.get('symbol', '?')
    addr = merged.get('address', '')
    mcap = float(merged.get('market_cap', 0) or 0)
    price = float(merged.get('price', 0) or 0)
    
    # Age
    age_str = str(merged.get('age', '0s'))
    age_sec = 0
    if 'h' in age_str:
        try:
            age_sec = int(float(age_str.replace('h','')) * 3600)
        except:
            age_sec = 0
    elif 'm' in age_str:
        try:
            age_sec = int(float(age_str.replace('m','')) * 60)
        except:
            age_sec = 0
    elif age_str.isdigit():
        age_sec = int(age_str)
    else:
        ts = merged.get('creation_timestamp') or merged.get('open_timestamp')
        if ts:
            age_sec = int(time.time() - int(ts))
    age_min = age_sec / 60.0
    
    # Basic fields
    holders = int(merged.get('holder_count', 0) or 0)
    top10 = float(merged.get('top_10_holder_rate', 0) or 0) * 100
    liquidity = float(merged.get('liquidity', 0) or 0)
    h1 = float(merged.get('price_change_percent1h', 0) or 0)
    h24 = float(merged.get('price_change_percent24h', 0) or 0)
    m5 = float(merged.get('price_change_percent5m', 0) or 0)
    chg1_raw = merged.get('price_change_percent1m')
    chg1 = float(chg1_raw) if chg1_raw is not None else None
    ath_mcap = float(merged.get('history_highest_market_cap', 0) or 0) or mcap
    volume = float(merged.get('volume', 0) or 0)
    vol5m = float(merged.get('volume5m', 0) or 0)
    if vol5m == 0 and volume > 0:
        vol5m = volume / 12  # Estimate from 24h
    bs_ratio = float(merged.get('buy_sell_ratio', 0) or 0)
    launchpad = str(merged.get('launchpad', '') or '').lower()
    
    # === FILTERS ===
    if age_sec < MIN_AGE_SECONDS:
        return None, f"age {age_min:.1f}min < {MIN_AGE_SECONDS/60:.0f}min"
    if age_sec > MAX_AGE_SECONDS:
        return None, f"age {age_min:.0f}min > {MAX_AGE_SECONDS/60:.0f}min"
    if mcap < MIN_MCAP:
        return None, f"mcap ${mcap:,.0f} < ${MIN_MCAP:,}"
    if mcap > MAX_MCAP:
        return None, f"mcap ${mcap:,.0f} > ${MAX_MCAP:,}"
    if holders < MIN_HOLDERS:
        return None, f"holders {holders} < {MIN_HOLDERS}"
    if top10 > TOP10_HOLDER_MAX:
        return None, f"top10 {top10:.1f}% > {TOP10_HOLDER_MAX}%"
    
    # Momentum
    if h1 < H1_MOMENTUM_MIN and h24 < H24_MOMENTUM_MIN:
        return None, f"no momentum (h1={h1:+.1f}% 24h={h24:+.1f}%)"
    
    # Parabolic
    if h1 > H1_PARABOLIC_REJECT:
        return None, f"h1 {h1:+.1f}% parabolic"
    
    # Exchange
    if launchpad and launchpad not in ALLOWED_EXCHANGES:
        return None, f"exchange {launchpad} not allowed"
    
    # BS ratio
    if age_min < 15:
        if bs_ratio < BS_RATIO_NEW and not (BS_PUMP_FUN_OK and launchpad == 'pump'):
            return None, f"bs {bs_ratio:.2f} < {BS_RATIO_NEW} (young)"
    else:
        if bs_ratio < BS_RATIO_OLD:
            return None, f"bs {bs_ratio:.2f} < {BS_RATIO_OLD} (old)"
    
    # Volume
    if vol5m < MIN_5MIN_VOLUME:
        return None, f"vol5m ${vol5m:,.0f} < ${MIN_5MIN_VOLUME:,}"
    
    # Liquidity
    if mcap > 60000 and liquidity < LIQUIDITY_MIN:
        return None, f"liq ${liquidity:,.0f} < ${LIQUIDITY_MIN:,}"
    
    # ATH divergence
    if ath_mcap > 0:
        ath_dist = ((ath_mcap - mcap) / ath_mcap) * 100
        if ath_dist > ATH_DIVERGENCE_MAX:
            return None, f"ATH dist {ath_dist:.1f}% > {ATH_DIVERGENCE_MAX}%"
    
    # Dip
    dip = 0
    if ath_mcap > 0:
        dip = ((ath_mcap - mcap) / ath_mcap) * 100
    if dip < DIP_MIN or dip > DIP_MAX:
        return None, f"dip {dip:.1f}% not in [{DIP_MIN}-{DIP_MAX}%]"
    
    # Blacklist / max positions
    if addr in PERM_BLACKLIST:
        return None, "blacklisted"
    try:
        with open(TRADES_FILE) as f:
            open_count = sum(1 for l in f if json.loads(l).get('action')=='BUY' and json.loads(l).get('status')=='open')
        if open_count >= MAX_OPEN_POSITIONS:
            return None, f"max positions ({open_count}/{MAX_OPEN_POSITIONS})"
    except:
        pass
    
    return {
        'token': symbol, 'address': addr, 'mcap': mcap, 'price': price,
        'h1': h1, 'h24': h24, 'm5': m5, 'chg1': chg1,
        'dip': dip, 'ath_mcap': ath_mcap, 'holders': holders,
        'top10': top10, 'liquidity': liquidity, 'vol5m': vol5m,
        'bs_ratio': bs_ratio, 'age_min': age_min, 'age_sec': age_sec,
        'entry_price': price, 'launchpad': launchpad,
    }, "PASS"

# ======= COOLDOWN ENTRY =======
def add_to_cooldown(addr, token_data, result, dex_data=None):
    """Start monitoring a token. Always fresh data per check."""
    now_ts = time.time()
    age_min = result['age_min']
    m5 = result['m5']
    h1 = result['h1']
    chg1 = result.get('chg1')
    
    # Determine base cooldown
    if age_min < 15 and m5 > -5 and h1 > 5:
        base_cooldown = 45
        reason = "young_parabolic"
    else:
        base_cooldown = 30
        reason = "normal"
    
    COOLDOWN_WATCH[addr] = {
        'first_seen': now_ts,
        'cooldown_end': now_ts + base_cooldown,
        'state': 'BASE_WAIT',
        'base_cooldown': base_cooldown,
        'reason': reason,
        'token_data': token_data,
        'result': result,
        'dex_data': dex_data,
        # Tracking
        'lowest_chg1': chg1 if chg1 is not None else 0,
        'lowest_mcap': result['mcap'],
        'last_chg1': chg1,
        'last_m5': m5,
        'last_mcap': result['mcap'],
        'last_price': result['price'],
        'recheck_count': 0,
        'post_cooldown_waiting': False,
        'final_verify_done': False,
        '_started_cooldown_at': now_ts,
    }
    print(f"   [{reason.upper()}] {result['token']}: base cooldown {base_cooldown}s | m5={m5:+.1f}% chg1={chg1}")
    return True

# ======= COOLDOWN MONITOR =======
def check_cooldown_watch():
    """Every check uses FRESH data. GMGN primary, DexScreener backup."""
    to_remove = []
    now = time.time()
    
    for addr, data in COOLDOWN_WATCH.items():
        result = data['result']
        state = data.get('state', 'BASE_WAIT')
        
        # === ALWAYS FRESH DATA ===
        fresh_gmgn = get_gmgn_token_info(addr)
        fresh_dex = get_dexscreener_data(addr)
        
        if not fresh_gmgn and not fresh_dex:
            print(f"   [SKIP] {result['token']}: no data (GMGN+DexScreener failed)")
            to_remove.append(addr)
            continue
        
        merged = merge_token_data(fresh_gmgn, fresh_dex)
        
        # Re-evaluate filters with fresh data
        fresh_result, fresh_reason = scan_token(merged, fresh_dex)
        if fresh_result is None:
            print(f"   [FAIL] {result['token']}: filter fail ({fresh_reason})")
            REJECTED_TEMP[addr] = {'ts': time.time(), 'reason': fresh_reason}
            to_remove.append(addr)
            continue
        
        data['result'] = fresh_result
        data['token_data'] = merged
        data['dex_data'] = fresh_dex
        
        chg1 = fresh_result.get('chg1')
        m5 = fresh_result.get('m5')
        curr_mcap = fresh_result.get('mcap', 0)
        curr_price = fresh_result.get('price', 0)
        
        # Track lowest mcap during cooldown
        if curr_mcap > 0 and curr_mcap < data.get('lowest_mcap', float('inf')):
            data['lowest_mcap'] = curr_mcap
        
        # Track lowest chg1 during rechecks
        if chg1 is not None and chg1 < data.get('lowest_chg1', 0):
            data['lowest_chg1'] = chg1
        
        data['last_chg1'] = chg1
        data['last_m5'] = m5
        data['last_mcap'] = curr_mcap
        data['last_price'] = curr_price
        
        # === STATE MACHINE ===
        if state == 'BASE_WAIT':
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                print(f"   [BASE] {result['token']}: wait {remaining:.0f}s | chg1={chg1} m5={m5:+.1f}%")
                continue
            
            # Base cooldown done — determine next state
            if chg1 is not None and chg1 < CHG1_MIN_VALUE:  # < -5%
                # chg1 < -5%: wait 15s extra, then start rechecks
                data['state'] = 'RECOVERY_WAIT'
                data['cooldown_end'] = now + CHG1_RECOVERY_WAIT
                data['recheck_count'] = 0
                print(f"   [RECOVERY] {result['token']}: chg1={chg1}% < -5% | wait 15s then rechecks")
            else:
                # chg1 >= -5%: wait 30s more, then verify
                data['state'] = 'POST_COOLDOWN_WAIT'
                data['cooldown_end'] = now + 30
                data['post_cooldown_waiting'] = True
                data['recheck_count'] = 0
                print(f"   [POST_CD] {result['token']}: chg1={chg1}% >= -5% | wait 30s for verify")
            continue
        
        elif state == 'RECOVERY_WAIT':
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                print(f"   [RECOVERY] {result['token']}: wait {remaining:.0f}s | chg1={chg1}%")
                continue
            
            # Start rechecks — chg1 needs to be +3% from lowest
            data['state'] = 'RECOVERY_RECHECK'
            data['cooldown_end'] = now + CHG1_RECHECK_DELAY
            data['recheck_count'] += 1
            lowest = data.get('lowest_chg1', 0)
            print(f"   [RECHECK #{data['recheck_count']}] {result['token']}: chg1={chg1}% | need +3% from lowest {lowest}%")
            continue
        
        elif state == 'RECOVERY_RECHECK':
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                continue
            
            data['recheck_count'] += 1
            
            # Max rechecks
            if data['recheck_count'] > MAX_RECHECKS:
                # Maxed out rechecks — use chg5/m5 backup
                lowest_mcap = data.get('lowest_mcap', 0)
                threshold_mcap = lowest_mcap * 1.03  # +3% from lowest mcap
                
                print(f"   [MAX_RECHECKS] {result['token']}: {data['recheck_count']} tries | using m5/mcap backup")
                data['state'] = 'M5_BACKUP_WAIT'
                data['backup_lowest_mcap'] = lowest_mcap
                data['cooldown_end'] = now + CHG1_RECHECK_DELAY
                continue
            
            if chg1 is None:
                # No chg1 — use m5/m5 backup immediately
                print(f"   [CHG1_NONE] {result['token']}: chg1=None, switching to m5/mcap backup")
                data['state'] = 'M5_BACKUP_WAIT'
                data['backup_lowest_mcap'] = data.get('lowest_mcap', curr_mcap)
                data['cooldown_end'] = now + CHG1_RECHECK_DELAY
                continue
            
            # Check improvement from LOWEST chg1 recorded
            lowest = data.get('lowest_chg1', 0)
            improvement = chg1 - lowest if lowest else 0
            
            if improvement >= CHG1_IMPROVEMENT_MIN:
                # Enough improvement — final 15s verify
                data['state'] = 'FINAL_VERIFY'
                data['cooldown_end'] = now + CHG1_VERIFY_DELAY
                data['final_verify_done'] = False
                print(f"   [RECOVERED] {result['token']}: chg1 {chg1}% improved +{improvement:+.1f}% from {lowest}% | verify 15s")
            else:
                # Not enough — keep rechecks
                data['cooldown_end'] = now + CHG1_RECHECK_DELAY
                print(f"   [RECHECK #{data['recheck_count']}] {result['token']}: chg1={chg1}% | +{improvement:+.1f}% from {lowest}% | need +{CHG1_IMPROVEMENT_MIN}%")
            continue
        
        elif state == 'POST_COOLDOWN_WAIT':
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                continue
            
            # Verify: chg1 needs to be +3% from last check
            last_chg1 = data.get('last_chg1') or chg1
            if chg1 is not None and last_chg1 is not None:
                improvement = chg1 - last_chg1
            else:
                improvement = 0
            
            if improvement >= CHG1_IMPROVEMENT_MIN:
                print(f"   [VERIFY_OK] {result['token']}: chg1={chg1}% (+{improvement:+.1f}% from last) | BUY!")
                buy_token(addr, fresh_result, merged, fresh_dex)
                to_remove.append(addr)
            else:
                data['cooldown_end'] = now + CHG1_RECHECK_DELAY
                data['recheck_count'] = (data.get('recheck_count', 0)) + 1
                print(f"   [VERIFY_FAIL] {result['token']}: chg1={chg1}% (+{improvement:+.1f}% < +{CHG1_IMPROVEMENT_MIN}%) | recheck #{data['recheck_count']}")
            continue
        
        elif state == 'FINAL_VERIFY':
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                continue
            
            if not data['final_verify_done']:
                data['final_verify_done'] = True
                data['cooldown_end'] = now + CHG1_VERIFY_DELAY
                print(f"   [VERIFY_FINAL] {result['token']}: final verify 15s | chg1={chg1}%")
                continue
            
            # Final verify done — BUY
            print(f"   [BUY] {result['token']}: verified | chg1={chg1}% | BUY!")
            buy_token(addr, fresh_result, merged, fresh_dex)
            to_remove.append(addr)
            continue
        
        elif state == 'M5_BACKUP_WAIT':
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                print(f"   [M5_BACKUP] {result['token']}: wait {remaining:.0f}s | m5={m5:+.1f}% mcap={curr_mcap:,.0f} (need +3% from {data.get('backup_lowest_mcap',0):,.0f})")
                continue
            
            # Check: m5 should be +3% above lowest mcap recorded
            backup_lowest = data.get('backup_lowest_mcap', curr_mcap)
            if backup_lowest > 0:
                mcap_recovery = ((curr_mcap - backup_lowest) / backup_lowest) * 100
            else:
                mcap_recovery = 0
            
            # Also check chg5 (m5) improvement
            last_m5 = data.get('last_m5', m5)
            m5_improvement = m5 - last_m5 if last_m5 else 0
            
            if mcap_recovery >= 3 or m5_improvement >= CHG1_IMPROVEMENT_MIN:
                print(f"   [M5_BACKUP_OK] {result['token']}: mcap +{mcap_recovery:.1f}% from low | m5={m5:+.1f}% | BUY!")
                buy_token(addr, fresh_result, merged, fresh_dex)
                to_remove.append(addr)
            else:
                data['cooldown_end'] = now + CHG1_RECHECK_DELAY
                data['recheck_count'] = data.get('recheck_count', 0) + 1
                print(f"   [M5_RECHECK #{data['recheck_count']}] {result['token']}: mcap +{mcap_recovery:.1f}% (need 3%) | m5={m5:+.1f}%")
            continue
    
    for addr in to_remove:
        if addr in COOLDOWN_WATCH:
            del COOLDOWN_WATCH[addr]
    return len(to_remove) > 0

# ======= BUY =======
def buy_token(addr, result, token_data=None, dex_data=None):
    global PERM_BLACKLIST
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
        'entry_reason': 'GMGN_V70',
        'h1': result.get('h1', 0),
        'm5': result.get('m5', 0),
        'chg1_at_buy': result.get('chg1', 0),
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
            msg = f"""BUY EXECUTED | {datetime.now(timezone.utc).strftime('%H:%M')}
━━━━━━━━━━━━━━━
{result.get('token')}
Entry MC: ${int(result.get('mcap', 0)):,}
Amount: {POSITION_SIZE} SOL
Entry: ${result.get('entry_price', 0):.10f}

https://dexscreener.com/solana/{addr}
https://pump.fun/{addr}"""
            send_telegram(msg)
        except Exception as e:
            print(f"   Alert error: {e}")
        return True
    except Exception as e:
        print(f"   Buy error: {e}")
        return False

# ======= SCAN CYCLE =======
def scan_cycle():
    tokens = []
    tokens.extend(get_gmgn_trending(50))
    tokens.extend(get_gmgn_new_pairs(20))
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
    
    for token_data in unique:
        addr = token_data.get('address', '')
        if not addr:
            continue
        if addr in PERM_BLACKLIST or addr in COOLDOWN_WATCH:
            continue
        
        dex_data = get_dexscreener_data(addr)
        result, reason = scan_token(token_data, dex_data)
        if result is None:
            continue
        
        # Add to cooldown — let it breathe
        add_to_cooldown(addr, token_data, result, dex_data)
    
    return True

def cleanup_rejected():
    now = time.time()
    for addr in list(REJECTED_TEMP.keys()):
        if now - REJECTED_TEMP[addr]['ts'] > REJECTED_REVISIT_DELAY:
            del REJECTED_TEMP[addr]

# ======= MAIN =======
def main():
    print("GMGN Scanner v7.0 Started")
    print("  Cooldown: young+parabolic=45s else=30s | chg1<-5% → recovery | verify | m5 backup")
    
    load_blacklist()
    
    while True:
        try:
            # Always check cooldown FIRST with fresh data
            check_cooldown_watch()
            
            # Then scan new tokens
            scan_cycle()
            
            cleanup_rejected()
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(15)

if __name__ == '__main__':
    main()