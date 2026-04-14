#!/usr/bin/env python3
"""
Pump Early Scanner v1.2 - Wilson Bot
Catches pump.fun coins within first 10 minutes of launch.
Uses GMGN trending with creation_timestamp filtering for early detection.
"""

import json
import time
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# === EARLY COIN FILTERS ===
MIN_MCAP_EARLY = 1000       # $1K floor
MAX_MCAP_EARLY = 15000      # $15K max
MAX_AGE_SECONDS_EARLY = 600  # 10 minutes max
MIN_HOLDERS_EARLY = 3       # Holders ≥ 3 (very early)
TOP10_MAX_EARLY = 50       # Top10 < 50%
MIN_VOLUME_5M_EARLY = 100  # $100+ 5min volume
POSITION_SIZE_EARLY = 0.05  # 0.05 SOL per early trade
STOP_LOSS_EARLY = -15        # -15% stop

# === DATA FILES ===
TRADES_FILE = Path("/root/Dex-trading-bot/trades/sim_trades.jsonl")
PERM_BLACKLIST_FILE = Path("/root/Dex-trading-bot/permanent_blacklist.json")

# === STATE ===
PERM_BLACKLIST = set()
COOLDOWN_WATCH = set()  # addresses recently processed

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

# === GET EARLY TOKENS FROM GMGN ===
def get_early_tokens(limit=50):
    """Get very new tokens from GMGN trending using creation_timestamp"""
    try:
        r = subprocess.run(
            ['gmgn-cli', 'market', 'trending', '--chain', 'sol', '--interval', '5m', '--limit', str(limit)],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode != 0:
            print(f"[EARLY] GMGN trending failed: {r.stderr[:100]}")
            return []
        
        data = json.loads(r.stdout)
        rank = data.get('data', {}).get('rank', [])
        
        now_ts = time.time()
        tokens = []
        
        for p in rank:
            try:
                creation_ts = int(p.get('creation_timestamp', 0))
                if not creation_ts:
                    continue
                
                age_sec = now_ts - creation_ts
                
                # Only tokens < 10 min old
                if age_sec < 0 or age_sec > MAX_AGE_SECONDS_EARLY:
                    continue
                
                mcap = float(p.get('market_cap', 0) or 0)
                if mcap < MIN_MCAP_EARLY or mcap > MAX_MCAP_EARLY:
                    continue
                
                # Check if pump.fun
                launchpad = str(p.get('launchpad', '')).lower()
                if launchpad not in ('pump', 'pumpswap'):
                    continue
                
                holders = int(p.get('holder_count', 0) or 0)
                top10 = float(p.get('top_10_holder_rate', 0) or 0) * 100
                volume5m = float(p.get('volume5m', 0) or 0)
                h1 = float(p.get('price_change_percent1h', 0) or 0)
                m5 = float(p.get('price_change_percent5m', 0) or 0)
                price = float(p.get('price', 0) or 0)
                buys = int(p.get('buys', 0) or 0)
                sells = int(p.get('sells', 0) or 0)
                
                tokens.append({
                    'address': p.get('address', ''),
                    'symbol': p.get('symbol', '?'),
                    'name': p.get('name', 'Unknown'),
                    'mcap': mcap,
                    'price': price,
                    'volume5m': volume5m,
                    'holders': holders,
                    'top10': top10,
                    'h1': h1,
                    'm5': m5,
                    'buys': buys,
                    'sells': sells,
                    'age_sec': age_sec,
                    'age_min': age_sec / 60,
                    'creation_ts': creation_ts,
                    'source': 'gmgn',
                })
            except Exception as e:
                continue
        
        return tokens
    except Exception as e:
        print(f"[EARLY] GMGN error: {e}")
        return []

# === FILTER EARLY TOKEN ===
def filter_early_token(token):
    """Check if token passes early entry filters"""
    addr = token['address']
    
    if addr in PERM_BLACKLIST:
        return None, "blacklisted"
    
    if token['age_sec'] > MAX_AGE_SECONDS_EARLY:
        return None, f"age {token['age_min']:.1f}min > 10min"
    
    if token['mcap'] < MIN_MCAP_EARLY:
        return None, f"mcap ${token['mcap']:,.0f} < $1K"
    if token['mcap'] > MAX_MCAP_EARLY:
        return None, f"mcap ${token['mcap']:,.0f} > $15K"
    
    holders = token.get('holders', 0)
    if holders < MIN_HOLDERS_EARLY:
        return None, f"holders {holders} < {MIN_HOLDERS_EARLY}"
    
    top10 = token.get('top10', 0)
    if top10 > TOP10_MAX_EARLY:
        return None, f"top10 {top10:.0f}% > {TOP10_MAX_EARLY}%"
    
    # Must have some trading activity
    buys = token.get('buys', 0)
    if buys < 3:
        return None, f"buys {buys} < 3"
    
    return token, "PASS"

# === BUY TOKEN (SIMULATED) ===
def buy_early_token(addr, token):
    global PERM_BLACKLIST
    
    now = datetime.now(timezone.utc).isoformat()
    
    trade = {
        'action': 'BUY',
        'token_address': addr,
        'token_name': token.get('name', token.get('symbol', '?')),
        'entry_price': token.get('price', 0),
        'entry_mcap': int(token.get('mcap', 0)),
        'opened_at': now,
        'closed_at': None,
        'entry_sol': POSITION_SIZE_EARLY,
        'status': 'open',
        'tp_status': {
            'tp1_hit': False, 'tp2_hit': False, 'tp3_hit': False,
            'tp4_hit': False, 'tp5_hit': False,
        },
        'tp1_sold': False, 'tp2_sold': False, 'tp3_sold': False,
        'tp4_sold': False, 'tp5_sold': False,
        'partial_exit': False, 'fully_exited': False,
        'peak_price': token.get('price', 0),
        'entry_reason': 'EARLY_PUMP_V12',
        'h1': token.get('h1', 0),
        'm5': token.get('m5', 0),
        'chg1_at_buy': 0,
        'dip_at_buy': 0,
        'ath_mcap': token.get('mcap', 0),
        'holders': token.get('holders', 0),
        'top10': token.get('top10', 0),
        'dex': 'pumpfun',
        'age_at_entry': token.get('age_min', 0),
    }
    
    try:
        with open(TRADES_FILE, 'a') as f:
            f.write(json.dumps(trade) + '\n')
        
        PERM_BLACKLIST.add(addr)
        with open(PERM_BLACKLIST_FILE, 'w') as f:
            json.dump(list(PERM_BLACKLIST), f)
        
        sym = token.get('symbol', addr[:16])
        print(f"   🐣 EARLY BUY: {sym} @ mcap ${token.get('mcap', 0):,.0f} | age {token.get('age_min', 0):.1f}min | holders {token.get('holders', 0)}")
        
        try:
            from alert_sender import send_telegram_alert
            msg = f"""🐣 EARLY BUY | {datetime.now(timezone.utc).strftime('%H:%M UTC')}
━━━━━━━━━━━━━━━
💰 {sym}
📍 Entry MC: ${int(token.get('mcap', 0)):,}
⏱ Age: {token.get('age_min', 0):.1f} min
👥 Holders: {token.get('holders', 0)}
📊 Vol5m: ${token.get('volume5m', 0):,.0f}
🛒 Buys: {token.get('buys', 0)} | Sells: {token.get('sells', 0)}
💵 Size: {POSITION_SIZE_EARLY} SOL

🔗 https://dexscreener.com/solana/{addr}
🥧 https://pump.fun/{addr}

⚠️ Early stage — stop {STOP_LOSS_EARLY}%"""
            send_telegram_alert(msg, "EARLY_BUY")
        except:
            pass
        
        return True
    except Exception as e:
        print(f"   ❌ Early buy error: {e}")
        return False

# === SCAN CYCLE ===
def scan_cycle():
    """Find and buy early pump.fun tokens"""
    global COOLDOWN_WATCH
    
    load_blacklist()
    tokens = get_early_tokens(50)
    print(f"[EARLY] Found {len(tokens)} pump.fun tokens < 10min old")
    
    bought = 0
    for token in tokens:
        addr = token['address']
        if not addr or addr in COOLDOWN_WATCH:
            continue
        
        result, reason = filter_early_token(token)
        if result is None:
            if reason != "blacklisted":
                print(f"   ❌ {token.get('symbol', addr[:12])}: {reason}")
            continue
        
        sym = token.get('symbol', addr[:12])
        age = token.get('age_min', 0)
        mcap = token.get('mcap', 0)
        holders = token.get('holders', 0)
        
        print(f"   ✅ {sym}: age {age:.1f}min | mcap ${mcap:,.0f} | holders {holders} | BUY!")
        
        COOLDOWN_WATCH.add(addr)
        if buy_early_token(addr, result):
            bought += 1
            if bought >= 1:
                break
    
    # Clean old cooldown entries
    if len(COOLDOWN_WATCH) > 100:
        COOLDOWN_WATCH = set()
    
    return bought > 0

# === MAIN ===
def main():
    print(f"🚀 PUMP EARLY SCANNER v1.2 Started")
    print(f"   Mcap: ${MIN_MCAP_EARLY:,}-${MAX_MCAP_EARLY:,} | Age: <10min | Holders: {MIN_HOLDERS_EARLY}+")
    print(f"   Buys: 3+ | Stop: {STOP_LOSS_EARLY}%")
    print(f"   Size: {POSITION_SIZE_EARLY} SOL")
    
    load_blacklist()
    
    cycle = 0
    while True:
        try:
            cycle += 1
            print(f"\n[EARLY CYCLE {cycle}] {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}")
            scan_cycle()
        except Exception as e:
            print(f"[EARLY] Cycle error: {e}")
        time.sleep(30)  # 30 second intervals

if __name__ == '__main__':
    main()
