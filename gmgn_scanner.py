#!/usr/bin/env python3
"""
GMGN Scanner v6.9 - Wilson Bot
Cooldown State Machine with chg5 deterioration + pump rule
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
    MIN_CHG1_FOR_BUY, CHG1_NONE_M5_REJECT, CHG1_IMPROVEMENT_MIN, CHG1_MIN_VALUE,
    DIP_MIN, DIP_MAX, ATH_DIVERGENCE_MAX,
    PUMP_5M_THRESHOLD, BASE_COOLDOWN,
    CHG1_RECHECK_DELAY, CHG1_VERIFY_DELAY, CHG1_RECOVERY_WAIT,
    VERIFY_CONSECUTIVE_OK,
    CHG5_DROP_REJECT,
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
    STATE_COOLDOWN, STATE_RECOVERY, STATE_VERIFICATION,
)

# === DATA FILES ===
TRADES_FILE = Path("/root/Dex-trading-bot/trades/sim_trades.jsonl")
WHALE_DB = Path("/root/Dex-trading-bot/wallet_analysis/whale_wallets.jsonl")
SIGNALS_DIR = Path("/root/Dex-trading-bot/signals")
PEAK_CACHE = Path("/root/Dex-trading-bot/position_peak_cache.json")
PERM_BLACKLIST_FILE = Path("/root/Dex-trading-bot/permanent_blacklist.json")

# === STATE ===
COOLDOWN_WATCH = {}  # {addr: {...}}
REJECTED_TEMP = {}   # {addr: {"ts": timestamp, "reason": str}}
PERM_BLACKLIST = set()
_gmgn_throttle_count = 0
_gmgn_last_throttle_alert = 0
_gmgn_empty_cycle_count = 0
_gmgn_last_alert_empty = 0

# === THROTTLE ===
def gmgn_throttle_alert():
    global _gmgn_throttle_count, _gmgn_last_throttle_alert
    _gmgn_throttle_count += 1
    now = time.time()
    if _gmgn_throttle_count >= 3 and (now - _gmgn_last_throttle_alert) > 300:
        print(f"🚨 GMGN API THROTTLED: {_gmgn_throttle_count} failures")
        try:
            from alert_sender import send_telegram_alert
            send_telegram_alert(f"🚨 GMGN THROTTLED: {_gmgn_throttle_count} failures. Check scanner.", "SYSTEM_ALERT")
        except:
            pass
        _gmgn_last_throttle_alert = now

def gmgn_success():
    global _gmgn_throttle_count
    _gmgn_throttle_count = 0

# === LOAD BLACKLIST ===
def load_blacklist():
    global PERM_BLACKLIST
    PERM_BLACKLIST = set()
    if PERM_BLACKLIST_FILE.exists():
        try:
            with open(PERM_BLACKLIST_FILE) as f:
                PERM_BLACKLIST = set(json.load(f))
        except:
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

# === GET DATA ===
def get_gmgn_trending(limit=50):
    try:
        r = subprocess.run(
            ['gmgn-cli', 'market', 'trending', '--chain', 'sol', '--interval', '5m', '--limit', str(limit)],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode == 0:
            gmgn_success()
            return json.loads(r.stdout).get('data', {}).get('rank', [])
        elif r.returncode != 0:
            gmgn_throttle_alert()
    except Exception as e:
        gmgn_throttle_alert()
    return []

def get_gmgn_pumpfun_lowcap(limit=30):
    try:
        r = subprocess.run(
            ['gmgn-cli', 'market', 'trending', '--chain', 'sol', '--interval', '5m', '--limit', str(limit),
             '--platform', 'Pump.fun', '--order-by', 'marketcap', '--direction', 'asc'],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode == 0:
            gmgn_success()
            return json.loads(r.stdout).get('data', {}).get('rank', [])
        elif r.returncode != 0:
            gmgn_throttle_alert()
    except Exception as e:
        gmgn_throttle_alert()
    return []

def get_gmgn_new_pairs(limit=30):
    try:
        r = subprocess.run(
            ['gmgn-cli', 'market', 'trenches', '--chain', 'sol', '--limit', str(limit)],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode == 0:
            gmgn_success()
            data = json.loads(r.stdout)
            pairs = []
            pairs.extend(data.get('creating', []))
            pairs.extend(data.get('created', []))
            pairs.extend(data.get('completed', []))
            return pairs
        elif r.returncode != 0:
            gmgn_throttle_alert()
    except Exception as e:
        gmgn_throttle_alert()
    return []

def get_gmgn_token_info(addr):
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
    """DexScreener as backup when GMGN is unavailable"""
    try:
        import requests
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(f'https://api.dexscreener.com/v1/tokens/{addr}', headers=headers, timeout=8)
        if r.status_code == 200:
            data = r.json()
            pairs = data.get('pairs', [])
            if pairs:
                p = pairs[0]
                return {
                    'priceChange': {
                        'm1': p.get('priceChange', {}).get('m1'),
                        'm5': p.get('priceChange', {}).get('m5'),
                        'h1': p.get('priceChange', {}).get('h1'),
                    },
                    'priceUsd': p.get('priceUsd'),
                    'marketCap': p.get('marketCap'),
                    'volume': p.get('volume', {}),
                    'holderCount': p.get('holderCount'),
                    'liquidity': p.get('liquidity'),
                }
    except:
        pass
    return None

# === SCAN TOKEN ===
def scan_token(gmgn_data, dex_data, whale_wallets):
    """Evaluate if a token passes all filters"""
    
    # Extract GMGN data
    symbol = gmgn_data.get('symbol', '?')
    addr = gmgn_data.get('address', '')
    mcap = float(gmgn_data.get('market_cap', 0) or 0)
    price = float(gmgn_data.get('price', 0) or 0)
    age_sec = int(gmgn_data.get('age', '0s').replace('s','').split('h')[0] if 'h' in str(gmgn_data.get('age','0s')) else int(gmgn_data.get('age', 0) or 0))
    if age_sec == 0:
        age_sec = int(time.time() - int(gmgn_data.get('creation_timestamp', time.time())))
    age_min = age_sec / 60
    holders = int(gmgn_data.get('holder_count', 0) or 0)
    top10 = float(gmgn_data.get('top_10_holder_rate', 0) or 0) * 100
    liquidity = float(gmgn_data.get('liquidity', 0) or 0)
    h1 = float(gmgn_data.get('price_change_percent1h', 0) or 0)
    h24 = float(gmgn_data.get('price_change_percent24h', 0) or 0)
    m5 = float(gmgn_data.get('price_change_percent5m', 0) or 0)
    chg1 = gmgn_data.get('price_change_percent1m')
    if chg1 is not None:
        chg1 = float(chg1)
    ath_mcap = float(gmgn_data.get('ath_market_cap', 0) or 0) or mcap
    vol5m = float(gmgn_data.get('volume5m', 0) or 0)
    bs_ratio = float(gmgn_data.get('buy_sell_ratio', 0) or 0)
    launchpad = str(gmgn_data.get('launchpad', '')).lower()
    pair_address = gmgn_data.get('pair_address', '')
    
    # DexScreener overrides
    ds_holders = 0
    if dex_data:
        ds_holders = int(dex_data.get('holderCount', 0) or 0)
        if holders == 0 and ds_holders > 0:
            holders = ds_holders
        ds_m5 = dex_data.get('priceChange', {}).get('m5')
        if ds_m5 is not None and m5 == 0:
            m5 = float(ds_m5)
        ds_h1 = dex_data.get('priceChange', {}).get('h1')
        if ds_h1 is not None and h1 == 0:
            h1 = float(ds_h1)
        ds_price = dex_data.get('priceUsd')
        if ds_price and price == 0:
            price = float(ds_price)
    
    # === AGE CHECK ===
    if age_sec < MIN_AGE_SECONDS:
        return None, f"age {age_min:.1f}min < {MIN_AGE_SECONDS/60:.0f}min"
    if age_sec > MAX_AGE_SECONDS:
        return None, f"age {age_min:.0f}min > {MAX_AGE_SECONDS/60:.0f}min"
    
    # === MCAP CHECK ===
    if mcap < MIN_MCAP:
        return None, f"mcap ${mcap:,.0f} < ${MIN_MCAP:,}"
    if mcap > MAX_MCAP:
        return None, f"mcap ${mcap:,.0f} > ${MAX_MCAP:,}"
    
    # === HOLDERS CHECK ===
    if holders < MIN_HOLDERS:
        return None, f"holders {holders} < {MIN_HOLDERS}"
    
    # === BOT FARM CHECK ===
    if holders == 0 and ds_holders == 0:
        return None, f"bot farm (holders=0)"
    if top10 == 0:
        return None, f"bot farm (top10=0%)"
    
    # === TOP10% FILTER ===
    if top10 > TOP10_HOLDER_MAX:
        return None, f"top10 {top10:.1f}% > {TOP10_HOLDER_MAX}%"
    
    # === MOMENTUM FILTER ===
    if h1 < H1_MOMENTUM_MIN and h24 < H24_MOMENTUM_MIN:
        return None, f"no momentum (h1={h1:+.1f}% 24h={h24:+.1f}%)"
    
    # === PARABOLIC ===
    if h1 > H1_PARABOLIC_REJECT:
        return None, f"h1 {h1:+.1f}% parabolic"
    
    # === CHG1 NONE + M5 > +5% = REJECT ===
    if chg1 is None and m5 > CHG1_NONE_M5_REJECT:
        return None, f"chg1=None but m5 {m5:+.1f}% > +{CHG1_NONE_M5_REJECT}%"
    
    # === EXCHANGE VALIDATION ===
    if launchpad == 'pump':
        if not (pair_address.endswith('pump') or 'pump' in pair_address.lower()):
            pass  # Accept pump.fun regardless
    elif launchpad not in ALLOWED_EXCHANGES:
        return None, f"exchange {launchpad} not allowed"
    
    # === BS RATIO ===
    if age_min < 15:
        if bs_ratio < BS_RATIO_NEW and not (BS_PUMP_FUN_OK and launchpad == 'pump'):
            return None, f"bs {bs_ratio:.2f} < {BS_RATIO_NEW} (young)"
    else:
        if bs_ratio < BS_RATIO_OLD:
            return None, f"bs {bs_ratio:.2f} < {BS_RATIO_OLD} (old)"
    
    # === VOLUME ===
    if vol5m < MIN_5MIN_VOLUME:
        return None, f"vol5m ${vol5m:,.0f} < ${MIN_5MIN_VOLUME:,}"
    
    # === LIQUIDITY (mcap > $60K) ===
    if mcap > LIQUIDITY_MCAP_THRESHOLD and liquidity < LIQUIDITY_MIN:
        return None, f"liq ${liquidity:,.0f} < ${LIQUIDITY_MIN:,} (mcap ${mcap:,.0f})"
    
    # === ATH DIVERGENCE ===
    if ath_mcap > 0:
        ath_distance = ((ath_mcap - mcap) / ath_mcap) * 100
        if ath_distance > ATH_DIVERGENCE_MAX:
            return None, f"ATH dist {ath_distance:.1f}% > {ATH_DIVERGENCE_MAX}%"
    
    # === DIP ===
    dip = 0
    if ath_mcap > 0:
        dip = ((ath_mcap - mcap) / ath_mcap) * 100
    if dip < DIP_MIN:
        return None, f"dip {dip:.1f}% < {DIP_MIN}%"
    if dip > DIP_MAX:
        return None, f"dip {dip:.1f}% > {DIP_MAX}%"
    
    # === OPEN POSITIONS CHECK ===
    try:
        with open(TRADES_FILE) as f:
            open_count = sum(1 for l in f if json.loads(l).get('action') == 'BUY' and json.loads(l).get('status') == 'open')
        if open_count >= MAX_OPEN_POSITIONS:
            return None, f"max positions ({open_count}/{MAX_OPEN_POSITIONS})"
    except:
        pass
    
    # === BLACKLIST ===
    if addr in PERM_BLACKLIST:
        return None, f"blacklisted"
    
    return {
        'token': symbol,
        'address': addr,
        'mcap': mcap,
        'price': price,
        'h1': h1,
        'h24': h24,
        'm5': m5,
        'chg1': chg1,
        'dip': dip,
        'ath_mcap': ath_mcap,
        'holders': holders,
        'top10': top10,
        'liquidity': liquidity,
        'vol5m': vol5m,
        'bs_ratio': bs_ratio,
        'age_min': age_min,
        'age_sec': age_sec,
        'entry_price': price,
        'launchpad': launchpad,
    }, "PASS"

# === COOLDOWN ===
def determine_cooldown(result):
    """m5 > -5% = cooldown, otherwise buy immediately"""
    if result['m5'] > PUMP_5M_THRESHOLD:
        return BASE_COOLDOWN
    return 0

def add_to_cooldown(addr, token_data, result, dex_data=None):
    """Add to cooldown watch - v6.9 state machine"""
    cooldown_secs = determine_cooldown(result)
    if cooldown_secs == 0:
        return False  # Buy immediately
    
    now_ts = time.time()
    chg1 = result.get('chg1')
    
    # If chg1 > +5%, enter PUMP path (go straight to recovery wait)
    pump_triggered = chg1 is not None and chg1 > 5.0
    
    COOLDOWN_WATCH[addr] = {
        'first_seen': now_ts,
        'cooldown_end': now_ts + cooldown_secs,
        'state': STATE_COOLDOWN,
        'token_data': token_data,
        'result': result,
        'dex_data': dex_data,
        'prev_chg1': chg1,
        'prev_chg5': result.get('m5'),
        'chg1_at_cooldown_start': chg1,
        'consecutive_ok': 0,
        'recheck_count': 0,
        'local_peak_mcap': result['mcap'],
        'lowest_mcap': result['mcap'],
        'price_at_last_check': result['entry_price'],
        'prev_h1': result['h1'],
        'price_drop_consecutive': 0,
        '_pump_triggered': pump_triggered,
    }
    
    pump_msg = " 🚀 PUMP" if pump_triggered else ""
    print(f"   ⏳ {result['token']}: cooldown {cooldown_secs}s (m5={result['m5']:+.1f}%){pump_msg}")
    return True

def check_deterioration_chg5(chg5, prev_chg5):
    """chg5 dropped >5% from previous = momentum dying"""
    if prev_chg5 is None or chg5 is None:
        return False
    if prev_chg5 <= 0:
        return False
    drop = prev_chg5 - chg5
    return drop > CHG5_DROP_REJECT

def check_cooldown_watch():
    """v6.9 Cooldown State Machine"""
    to_remove = []
    now = time.time()
    
    for addr, data in COOLDOWN_WATCH.items():
        result = data['result']
        state = data.get('state', STATE_COOLDOWN)
        
        # === GET FRESH DATA ===
        fresh_data = get_gmgn_token_info(addr)
        fresh_dex = get_dexscreener_data(addr)
        
        # Build merged data: GMGN primary → DexScreener fills gaps
        merged_data = {}
        if fresh_data:
            merged_data = fresh_data.copy()
        if fresh_dex:
            ds_chg1 = fresh_dex.get('priceChange', {}).get('m1')
            if ds_chg1 is not None:
                merged_data['price_change_percent1m'] = float(ds_chg1)
            ds_price = fresh_dex.get('priceUsd')
            if ds_price and merged_data.get('price') in (None, 0, ''):
                merged_data['price'] = float(ds_price)
            ds_mcap = fresh_dex.get('marketCap')
            if ds_mcap and merged_data.get('market_cap', 0) == 0:
                merged_data['market_cap'] = float(ds_mcap)
            ds_holders = fresh_dex.get('holderCount')
            if ds_holders and merged_data.get('holder_count', 0) == 0:
                merged_data['holder_count'] = int(ds_holders)
        
        if not fresh_data and not merged_data:
            print(f"   ❌ {result['token']}: no data (GMGN+DexScreener failed)")
            to_remove.append(addr)
            continue
        
        # === RE-EVALUATE FILTERS ===
        scan_data = merged_data if merged_data else fresh_data
        fresh_result, fresh_reason = scan_token(scan_data, fresh_dex, [])
        
        if fresh_result is None:
            print(f"   ❌ {result['token']}: filter fail ({fresh_reason})")
            to_remove.append(addr)
            continue
        
        data['result'] = fresh_result
        data['token_data'] = merged_data
        data['dex_data'] = fresh_dex
        
        # === UPDATE PEAK/TRACKING ===
        curr_mcap = fresh_result.get('mcap', 0)
        curr_price = fresh_result.get('price', 0)
        if curr_mcap > 0:
            if curr_mcap > data.get('local_peak_mcap', 0):
                data['local_peak_mcap'] = curr_mcap
            if curr_mcap < data.get('lowest_mcap', float('inf')):
                data['lowest_mcap'] = curr_mcap
        
        # === H1 INSTABILITY ===
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
        chg5 = fresh_result.get('m5')
        prev_chg1 = data.get('prev_chg1')
        prev_chg5 = data.get('prev_chg5')
        cooldown_done = now >= data['cooldown_end']
        baseline_chg1 = data.get('chg1_at_cooldown_start', 0)
        
        # === DETERIORATION CHECK (chg5 drops >5%) ===
        if check_deterioration_chg5(chg5, prev_chg5):
            print(f"   ❌ {result['token']}: chg5 deteriorated {prev_chg5:+.1f}% → {chg5:+.1f}% (>5% drop)")
            REJECTED_TEMP[addr] = {'ts': time.time(), 'reason': 'chg5 deterioration'}
            to_remove.append(addr)
            continue
        
        # === STATE MACHINE ===
        if state == STATE_COOLDOWN:
            # Monitor for 45s
            if not cooldown_done:
                remaining = data['cooldown_end'] - now
                print(f"   ⏳ {result['token']}: cooldown {remaining:.0f}s left (chg1={chg1:+.1f}% chg5={chg5:+.1f}%)")
                data['prev_chg1'] = chg1
                data['prev_chg5'] = chg5
                continue
            
            # Cooldown done — check next state
            if chg1 is not None and chg1 > 5.0:
                # 🚀 PUMP PATH: chg1 > +5% — skip recovery, go straight to verify
                data['state'] = STATE_VERIFICATION
                data['cooldown_end'] = now + CHG1_VERIFY_DELAY
                data['prev_chg1'] = chg1
                data['consecutive_ok'] = 0
                data['recheck_count'] = 0
                print(f"   🚀 {result['token']}: PUMP confirmed (chg1={chg1:+.1f}%) — verify 15s")
                continue
            
            elif chg1 is not None and chg1 < CHG1_MIN_VALUE:
                # chg1 < -5% — enter RECOVERY
                data['state'] = STATE_RECOVERY
                data['cooldown_end'] = now + CHG1_RECOVERY_WAIT
                data['prev_chg1'] = chg1
                data['recheck_count'] = 0
                data['consecutive_ok'] = 0
                print(f"   ⏳ {result['token']}: cooldown done | chg1={chg1:+.1f}% < -5% — RECOVERY")
                continue
            
            else:
                # chg1 >= -5% — normal verify
                data['state'] = STATE_VERIFICATION
                data['cooldown_end'] = now + CHG1_RECHECK_DELAY
                data['prev_chg1'] = chg1
                data['prev_chg5'] = chg5
                data['consecutive_ok'] = 0
                data['recheck_count'] = 0
                print(f"   ⏳ {result['token']}: cooldown done | chg1={chg1:+.1f}% — verify (need +3% from last)")
                continue
        
        elif state == STATE_RECOVERY:
            # chg1 < -5%, waiting for it to recover
            if not cooldown_done:
                remaining = data['cooldown_end'] - now
                print(f"   ⏳ {result['token']}: recovery {remaining:.0f}s left (chg1={chg1:+.1f}%)")
                data['prev_chg1'] = chg1
                data['prev_chg5'] = chg5
                continue
            
            # Recheck
            data['recheck_count'] += 1
            if data['recheck_count'] > MAX_RECHECKS:
                print(f"   ❌ {result['token']}: max rechecks — temp reject")
                REJECTED_TEMP[addr] = {'ts': time.time(), 'reason': 'max rechecks'}
                to_remove.append(addr)
                continue
            
            if chg1 is None:
                data['cooldown_end'] = now + CHG1_RECHECK_DELAY
                data['prev_chg1'] = chg1
                print(f"   ⏳ {result['token']}: recheck #{data['recheck_count']} chg1=None")
                continue
            
            if chg1 >= CHG1_MIN_VALUE:
                # chg1 recovered above -5% — check improvement
                improvement = chg1 - (prev_chg1 if prev_chg1 else baseline_chg1)
                if improvement > CHG1_IMPROVEMENT_MIN:
                    data['state'] = STATE_VERIFICATION
                    data['cooldown_end'] = now + CHG1_VERIFY_DELAY
                    data['prev_chg1'] = chg1
                    data['consecutive_ok'] = 0
                    data['recheck_count'] = 0
                    print(f"   ✅ {result['token']}: chg1 recovered {chg1:+.1f}% (improved +{improvement:+.1f}%) — verify 15s")
                    continue
                else:
                    # Improvement not met — keep recovering
                    data['cooldown_end'] = now + CHG1_RECHECK_DELAY
                    data['prev_chg1'] = chg1
                    print(f"   ⏳ {result['token']}: chg1 {chg1:+.1f}% improved +{improvement:+.1f}% < +{CHG1_IMPROVEMENT_MIN}% — keep recovery")
                    continue
            else:
                # Still below -5%
                data['cooldown_end'] = now + CHG1_RECHECK_DELAY
                data['prev_chg1'] = chg1
                print(f"   ⏳ {result['token']}: recheck #{data['recheck_count']} chg1={chg1:+.1f}% still < -5%")
                continue
        
        elif state == STATE_VERIFICATION:
            # 15s verify — need 2 consecutive rechecks with +3% improvement from last
            if not cooldown_done:
                remaining = data['cooldown_end'] - now
                print(f"   ⏳ {result['token']}: verify {remaining:.0f}s left (ok={data['consecutive_ok']}/{VERIFY_CONSECUTIVE_OK})")
                data['prev_chg1'] = chg1
                data['prev_chg5'] = chg5
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
                    print(f"   ⏳ {result['token']}: price down {price_drop:.1f}% ({price_drop_count}/3) — wait {wait_time}s")
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
                improvement = 0
            
            if improvement > CHG1_IMPROVEMENT_MIN:
                data['consecutive_ok'] += 1
                data['prev_chg1'] = chg1
                data['prev_chg5'] = chg5
                print(f"   ⏳ {result['token']}: verify #{data['consecutive_ok']} chg1={chg1:+.1f}% (improved +{improvement:+.1f}%) | {data['consecutive_ok']}/{VERIFY_CONSECUTIVE_OK}")
                
                if data['consecutive_ok'] >= VERIFY_CONSECUTIVE_OK:
                    # BUY!
                    lowest_mcap = data.get('lowest_mcap', 0)
                    if lowest_mcap > 0 and curr_mcap > 0:
                        mcap_recovery = ((curr_mcap - lowest_mcap) / lowest_mcap) * 100
                        if mcap_recovery < MCAP_INCREASE_CONFIRM:
                            print(f"   ⏳ {result['token']}: mcap up {mcap_recovery:.1f}% < 2% — recheck")
                            data['cooldown_end'] = now + CHG1_RECHECK_DELAY
                            data['consecutive_ok'] = 0
                            continue
                    
                    print(f"   🟢 BUY: {result['token']} @ mcap ${curr_mcap:,.0f} | chg1={chg1:+.1f}%")
                    buy_token(addr, fresh_result)
                    to_remove.append(addr)
                    continue
                else:
                    data['cooldown_end'] = now + CHG1_RECHECK_DELAY
                    continue
            else:
                # Improvement not met
                print(f"   ❌ {result['token']}: improvement +{improvement:+.1f}% < +{CHG1_IMPROVEMENT_MIN}% — REJECT")
                REJECTED_TEMP[addr] = {'ts': time.time(), 'reason': f'insufficient improvement ({improvement:+.1f}%)'}
                to_remove.append(addr)
                continue
    
    for addr in to_remove:
        if addr in COOLDOWN_WATCH:
            del COOLDOWN_WATCH[addr]
    return len(to_remove) > 0

# === BUY ===
def buy_token(addr, result):
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
        'entry_reason': 'GMGN_V69',
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
            from alert_sender import send_telegram_alert
            msg = f"""🟢 BUY | {datetime.now(timezone.utc).strftime('%H:%M UTC')}
━━━━━━━━━━━━━━━
[BUY] {result.get('token')}
[MKT] MC: ${int(result.get('mcap', 0)):,} | Entry: ${int(result.get('entry_price', 0))}
📊 h1: {result.get('h1', 0):+.1f}% | m5: {result.get('m5', 0):+.1f}% | chg1: {result.get('chg1', 0):+.1f}%
👥 Holders: {result.get('holders', 0)} | Top10: {result.get('top10', 0):.0f}%
[DIP] Dip: {result.get('dip', 0):.1f}%

🔗 https://dexscreener.com/solana/{addr}
🥧 https://pump.fun/{addr}"""
            send_telegram_alert(msg, "BUY")
        except:
            pass
        return True
    except Exception as e:
        print(f"   ❌ Buy error: {e}")
        return False

# === SCAN CYCLE ===
def scan_cycle():
    global _gmgn_empty_cycle_count, _gmgn_last_alert_empty
    load_blacklist()
    
    tokens = get_gmgn_trending(50)
    tokens.extend(get_gmgn_new_pairs(30))
    tokens.extend(get_gmgn_pumpfun_lowcap(30))
    
    if len(tokens) == 0:
        _gmgn_empty_cycle_count += 1
        now = time.time()
        if _gmgn_empty_cycle_count >= 5 and (now - _gmgn_last_alert_empty) > 300:
            print(f"🚨 GMGN returning empty for {_gmgn_empty_cycle_count} cycles")
            try:
                from alert_sender import send_telegram_alert
                send_telegram_alert(f"🚨 GMGN empty data for {_gmgn_empty_cycle_count} cycles", "SYSTEM_ALERT")
            except:
                pass
            _gmgn_last_alert_empty = now
    else:
        _gmgn_empty_cycle_count = 0
    
    print(f"[SCAN] Found {len(tokens)} tokens")
    
    # Deduplicate
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
        
        if addr in PERM_BLACKLIST or addr in COOLDOWN_WATCH:
            continue
        
        dex_data = get_dexscreener_data(addr)
        result, reason = scan_token(token_data, dex_data, [])
        
        if result is None:
            continue
        
        cooldown_secs = determine_cooldown(result)
        if cooldown_secs > 0:
            if add_to_cooldown(addr, token_data, result, dex_data):
                continue
            continue
        else:
            if buy_token(addr, result):
                print(f"   🟢 BUY (immediate): {result['token']} @ ${result['mcap']:,.0f}")
                bought += 1
                if bought >= 1:
                    break
    
    return bought > 0

# === TEMP REJECT CLEANUP ===
def cleanup_rejected():
    now = time.time()
    for addr in list(REJECTED_TEMP.keys()):
        entry = REJECTED_TEMP[addr]
        if now - entry['ts'] > REJECTED_REVISIT_DELAY:
            del REJECTED_TEMP[addr]

# === MAIN ===
def main():
    print(f"🚀 GMGN Scanner v6.9 Started")
    print(f"   Sources: GMGN trending + trenches + pump.fun lowcap")
    print(f"   Mcap: ${MIN_MCAP:,}-${MAX_MCAP:,} | Holders: {MIN_HOLDERS}+ | Dip: {DIP_MIN}-{DIP_MAX}% | ATH: <{ATH_DIVERGENCE_MAX}%")
    print(f"   Momentum: h1/24h > +{H1_MOMENTUM_MIN}% | chg1 > +{MIN_CHG1_FOR_BUY}%")
    print(f"   Cooldown: m5>-5% → {BASE_COOLDOWN}s | chg1<-5% → recovery | verify 2x(+3%) | deterioration: chg5>5% drop")
    print(f"   Stop: {STOP_LOSS_PERCENT}%")
    
    load_blacklist()
    cleanup_rejected()
    
    cycle = 0
    while True:
        try:
            cycle += 1
            print(f"\n[CYCLE {cycle}] {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}")
            
            check_cooldown_watch()
            scan_cycle()
            cleanup_rejected()
            
        except Exception as e:
            print(f"[SCAN] Cycle error: {e}")
        time.sleep(SCAN_INTERVAL)

if __name__ == '__main__':
    main()
