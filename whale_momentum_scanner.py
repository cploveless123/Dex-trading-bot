#!/usr/bin/env python3
"""
Whale Momentum Scanner v1.4
Chris's Strategy v1.4 - Local peak tracking + cooldown + NoMint/Blacklist checks
"""

import requests
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime
from trading_constants import *

# Paths
SCRIPT_DIR = Path("/root/Dex-trading-bot")
WHALE_DB = SCRIPT_DIR / "whales" / "whale_db.json"
TRADES_FILE = SCRIPT_DIR / "trades" / "sim_trades.jsonl"

# Peak tracking (first 60 seconds window)
_peak_prices = {}
_token_first_seen = {}
_token_peak_60s = {}

# Track sold tokens - NEVER re-buy
_sold_tokens = set()

def init_sold_tokens():
    """Load ALL closed positions from trade history - PERMANENT BLACKLIST"""
    try:
        with open(TRADES_FILE) as f:
            for line in f:
                t = json.loads(line)
                if t.get('token_address') and t.get('status') == 'closed' and t.get('action') == 'BUY':
                    _sold_tokens.add(t['token_address'])
    except:
        pass

def is_ascii(sym):
    try:
        sym.encode('ascii').decode('ascii')
        return True
    except:
        return False

def check_blacklist(p_data):
    """Check NoMint and Blacklist flags"""
    if p_data.get('blacklist'):
        return True, "blacklisted"
    if CHECK_NOMINT and p_data.get('mintable'):
        return True, "nomint"
    return False, "OK"

def get_gmgn_token_data(addr):
    """Get GMGN token data - ATH, bonded status"""
    try:
        r = subprocess.run(
            ['gmgn-cli', 'token', 'info', '--chain', 'sol', '--address', addr],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode == 0:
            d = json.loads(r.stdout)
            ath_price = d.get('ath_price', 0)
            supply_str = d.get('total_supply', d.get('circulating_supply', '0'))
            try:
                supply = float(supply_str)
            except:
                supply = 0
            ath_price_val = float(ath_price) if ath_price else 0
            ath_mcap = None
            if ath_price_val > 0 and supply > 0:
                ath_mcap = ath_price_val * supply
            migrated_pool = d.get('migrated_pool', '')
            is_bonded = migrated_pool and len(str(migrated_pool)) > 5
            return ath_mcap, ath_price_val, is_bonded
    except:
        pass
    return None, None, False

def get_pair_age_minutes(p):
    """Get pair age in minutes"""
    created = p.get('pairCreatedAt', 0)
    if created:
        return (time.time() * 1000 - created) / 60000
    return 999

def scan_token(addr):
    """Scan a single token against v1.4 criteria"""
    try:
        r = requests.get(f'https://api.dexscreener.com/latest/dex/tokens/{addr}', timeout=10)
        if r.status_code != 200:
            return None, None
        data = r.json()
        pairs = data.get('pairs', [])
        if not pairs:
            return None, None
        p = max(pairs, key=lambda x: x.get('liquidity', {}).get('usd', 0))
        m = float(p.get('fdv', 0) or p.get('marketCap', 0) or 0)
        v5 = float(p.get('volume', {}).get('m5', 0) or 0)
        sym = p.get('baseToken', {}).get('symbol', '?')
        
        # Basic checks
        if not is_ascii(sym):
            return None, None
        if sym in TICKER_BLACKLIST:
            return None, None
        
        # Get price changes
        chg1 = float(p.get('priceChange', {}).get('m1', 0) or 0)
        chg5 = float(p.get('priceChange', {}).get('m5', 0) or 0)
        chg60 = float(p.get('priceChange', {}).get('h1', 0) or 0)
        chg24 = float(p.get('priceChange', {}).get('h24', 0) or 0)
        
        # BS ratio
        liq = float(p.get('liquidity', {}).get('usd', 0) or 0)
        bs_mcap = float(p.get('bondingCurve', {}).get('mcap', 0) or 0)
        bs = bs_mcap / max(liq, 1) if bs_mcap > 0 else (m / max(liq, 1) if liq > 0 else 1)
        
        holders = int(p.get('holders', 0) or 0)
        p_data = p
        
        # Anti-patterns
        top10 = float(p.get('topHolderPercent', 0) or 0)
        if top10 > 50:
            return None, None  # Dumper
        
        # NoMint / Blacklist
        is_bl, bl_reason = check_blacklist(p_data)
        if is_bl:
            return None, None
        
        # Mcap range
        if m < MIN_MCAP or m > MAX_MCAP:
            return None, None
        
        # Holders
        if holders > 0 and holders < MIN_HOLDERS:
            return None, None
        
        # 5min vol
        if v5 < MIN_5MIN_VOLUME:
            return None, None
        
        # Liquidity: ignore if mcap < $50K OR new/bonding curve (enforced below)
        pair_age = get_pair_age_minutes(p)
        if liq < 1000 and m >= 50000:
            return None, None
        
        # Track local peak (first 60 seconds)
        now = time.time()
        if addr not in _token_first_seen:
            _token_first_seen[addr] = now
            _token_peak_60s[addr] = m
        
        # Update peak if within 60s window
        if now - _token_first_seen[addr] < PEAK_WINDOW_SECONDS:
            if m > _token_peak_60s[addr]:
                _token_peak_60s[addr] = m
        else:
            # After 60s, freeze the peak
            if addr not in _token_peak_60s:
                _token_peak_60s[addr] = m
        
        peak = _token_peak_60s.get(addr, m)
        dip_pct = (peak - m) / peak * 100 if peak > 0 else 0
        
        # Dip range check
        if dip_pct < DIP_MIN:
            return None, f"B: dip <{DIP_MIN}%"
        if dip_pct > DIP_MAX:
            return None, f"B: dip >{DIP_MAX}%"
        
        # GMGN ATH check - reject if local peak >40% from ATH (parabolic warning)
        ath_mcap, _, _ = get_gmgn_token_data(addr)
        if ath_mcap and ath_mcap > 0:
            divergence = (ath_mcap - m) / ath_mcap * 100
            if divergence > ATH_DIVERGENCE_REJECT:
                return None, f"B: peak >{ATH_DIVERGENCE_REJECT}% from ATH"
        
        # Age-based entry criteria
        if pair_age < 5:
            # NEW PAIRS (<5 min): h1 >+50%, 5min >+50%
            if chg60 < 50:
                return None, f"B: new h1 <+50%"
            if chg5 < 50:
                return None, f"B: new 5min <+50%"
            
            # Cooldown: h1 >+100% → wait 45s
            if chg60 > NEW_PUMP_HS1_THRESHOLD:
                time_watching = now - _token_first_seen.get(addr, now)
                if time_watching < NEW_PUMP_COOLDOWN:
                    return None, f"B: new pump cooldown ({int(time_watching)}s < {NEW_PUMP_COOLDOWN}s)"
        else:
            # OLDER PAIRS (>5 min): 24hr >+25%, h1 >-39%, 5min >-39%
            if chg24 < 25:
                return None, f"B: 24hr <+25%"
            if chg60 < -39:
                return None, f"B: h1 <-39%"
            if chg5 < -39:
                return None, f"B: 5min <-39%"
            
            # Cooldown: 5min >+1% → wait 90s
            if chg5 > OLD_PUMP_5M_THRESHOLD:
                time_watching = now - _token_first_seen.get(addr, now)
                if time_watching < OLD_PUMP_COOLDOWN:
                    return None, f"B: old pump cooldown ({int(time_watching)}s < {OLD_PUMP_COOLDOWN}s)"
            
            # BS ratio for older
            if bs < MIN_BS_OLD:
                return None, f"B: BS <{MIN_BS_OLD}"
        
        # Get bonded status for informational tag
        _, _, is_bonded = get_gmgn_token_data(addr)
        
        return {
            "token": sym,
            "address": addr,
            "mcap": m,
            "bs": bs,
            "holders": holders,
            "chg1": chg1,
            "chg5": chg5,
            "chg60": chg60,
            "chg24": chg24,
            "v5": v5,
            "liq": liq,
            "dip_pct": dip_pct,
            "age": pair_age,
            "dex": p.get('dexId', ''),
            "is_bonded": is_bonded
        }, "OK"
    except Exception as e:
        return None, str(e)

def check_and_buy():
    """Main scan + buy loop with 60s startup delay"""
    print("⏳ 60s startup delay before first buy...")
    time.sleep(60)
    print("✅ Startup delay complete, starting scans...")
    
    whales = load_whales()
    print(f"   Loaded {len(whales)} whales, {len(_sold_tokens)} sold (blacklisted)")
    print("Starting scans...")
    
    while True:
        try:
            resp = requests.get(
                "https://api.dexscreener.com/token-profiles/latest/v1",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10
            )
            if resp.status_code != 200:
                time.sleep(5)
                continue
            tokens = resp.json()[:50]
        except:
            time.sleep(5)
            continue
        
        # Check max positions
        try:
            with open(TRADES_FILE) as f:
                existing = [json.loads(l) for l in f]
            reset = SIM_RESET_TIMESTAMP
            open_pos = [t for t in existing if t.get('opened_at', '') > reset and not t.get('closed_at')]
            if len(open_pos) >= MAX_OPEN_POSITIONS:
                time.sleep(5)
                continue
        except:
            existing = []
        
        bought = None
        for tok_data in tokens:
            addr = tok_data.get('tokenAddress', '')
            if not addr:
                continue
            
            # PERMANENT BLACKLIST - check open OR closed
            already_open_or_sold = False
            try:
                with open(TRADES_FILE) as f:
                    for line in f:
                        t = json.loads(line)
                        if t.get('token_address') == addr:
                            if t.get('action') == 'BUY' and not t.get('closed_at'):
                                already_open_or_sold = True
                                break
                            if t.get('status') == 'closed' and t.get('action') == 'BUY':
                                _sold_tokens.add(addr)
            except:
                pass
            if addr in _sold_tokens or already_open_or_sold:
                continue
            
            result, msg = scan_token(addr)
            if result is None:
                continue
            
            # Execute buy
            bonded_tag = " [BONDED]" if result.get('is_bonded') else ""
            print(f"✅ BUY: {result['token']}{bonded_tag} @ ${result['mcap']:,.0f}")
            
            trade = {
                "token": result['token'],
                "token_address": addr,
                "amount_sol": POSITION_SIZE,
                "entry_mcap": int(result['mcap']),
                "entry_liquidity": result['liq'],
                "dex": result['dex'],
                "action": "BUY",
                "source": "whale_momentum_SCANNER",
                "opened_at": datetime.utcnow().isoformat(),
                "status": "open",
                "entry_reason": "SCAN_DIP",
                "bs_ratio": result['bs'],
                "chg60": result['chg60'],
                "chg5": result['chg5'],
                "dip_pct": result['dip_pct']
            }
            
            with open(TRADES_FILE, "a") as f:
                f.write(json.dumps(trade) + "\n")
            
            bought = result
            break
        
        if not bought:
            time.sleep(5)

def load_whales():
    try:
        with open(WHALE_DB) as f:
            d = json.load(f)
        return [w['wallet'] for w in d.get('whales', []) if w.get('winrate', 0) >= 0.5 and w.get('buy_count', 0) >= 3]
    except:
        return []

if __name__ == "__main__":
    print("🚀 Whale Momentum Scanner v1.4 - Chris's Strategy v1.4")
    print(f"   Mcap: ${MIN_MCAP:,}-${MAX_MCAP:,} | Dip: {DIP_MIN}-{DIP_MAX}% | Peak: {PEAK_WINDOW_SECONDS}s window")
    init_sold_tokens()
    check_and_buy()
