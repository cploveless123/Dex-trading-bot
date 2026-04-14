#!/usr/bin/env python3
"""
Pump Early Scanner v1.3 - Wilson Bot
Catches pump.fun coins in first 1-15 minutes of launch.
Key signal: rapid holder accumulation = organic momentum = potential pump.
"""

import json
import time
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# === EARLY COIN FILTERS ===
MIN_MCAP_EARLY = 2000       # $2K floor
MAX_MCAP_EARLY = 15000      # $15K max
MIN_AGE_SECONDS = 60        # 1 minute minimum (skip dust)
MAX_AGE_SECONDS = 900       # 15 minutes max
MIN_HOLDERS_EARLY = 5      # ≥5 holders (organic momentum)
MIN_LIQUIDITY_EARLY = 1000 # ≥$1K liquidity
POSITION_SIZE_EARLY = 0.05 # 0.05 SOL per early trade
STOP_LOSS_EARLY = -15       # -15% stop

# === DATA FILES ===
TRADES_FILE = Path("/root/Dex-trading-bot/trades/sim_trades.jsonl")
PERM_BLACKLIST_FILE = Path("/root/Dex-trading-bot/permanent_blacklist.json")

# === STATE ===
PERM_BLACKLIST = set()
COOLDOWN_WATCH = set()  # recently processed addresses

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

# === GET NEW PUMP.FUN CREATIONS ===
def get_new_pumpfun_tokens(limit=50):
    """Get pump.fun tokens 1-15 min old with rapid holder growth"""
    try:
        r = subprocess.run(
            ['gmgn-cli', 'market', 'trenches', '--chain', 'sol',
             '--type', 'new_creation',
             '--launchpad-platform', 'Pump.fun',
             '--min-created', '1m', '--max-created', '15m',
             '--limit', str(limit)],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode != 0:
            print(f"[EARLY] GMGN trenches failed: {r.stderr[:100]}")
            return []
        
        data = json.loads(r.stdout)
        new = data.get('new_creation', [])
        
        now_ts = time.time()
        tokens = []
        
        for p in new:
            try:
                ct = int(p.get('created_timestamp', 0))
                age_sec = now_ts - ct if ct else 0
                
                if age_sec < MIN_AGE_SECONDS or age_sec > MAX_AGE_SECONDS:
                    continue
                
                mcap = float(p.get('market_cap', 0) or 0)
                if mcap < MIN_MCAP_EARLY or mcap > MAX_MCAP_EARLY:
                    continue
                
                holders = int(p.get('holder_count', 0) or 0)
                if holders < MIN_HOLDERS_EARLY:
                    continue
                
                liquidity = float(p.get('liquidity', 0) or 0)
                if liquidity < MIN_LIQUIDITY_EARLY:
                    continue
                
                smart = int(p.get('smart_degen_count', 0) or 0)
                
                # Rapid holder growth signal: holders / age_min
                age_min = age_sec / 60
                holder_rate = holders / age_min if age_min > 0 else 0
                
                tokens.append({
                    'address': p.get('address', ''),
                    'symbol': p.get('symbol', '?'),
                    'name': p.get('name', p.get('symbol', 'Unknown')),
                    'mcap': mcap,
                    'price': float(p.get('price', 0) or 0),
                    'holders': holders,
                    'liquidity': liquidity,
                    'smart_degen': smart,
                    'age_sec': age_sec,
                    'age_min': age_min,
                    'holder_rate': holder_rate,  # holders per minute = momentum signal
                    'source': 'gmgn',
                })
            except:
                continue
        
        return tokens
    except Exception as e:
        print(f"[EARLY] Error: {e}")
        return []

# === FILTER ===
def filter_token(token):
    addr = token['address']
    if addr in PERM_BLACKLIST:
        return None, "blacklisted"
    if addr in COOLDOWN_WATCH:
        return None, "cooldown"
    if token['holders'] < MIN_HOLDERS_EARLY:
        return None, f"holders {token['holders']} < {MIN_HOLDERS_EARLY}"
    if token['liquidity'] < MIN_LIQUIDITY_EARLY:
        return None, f"liq ${token['liquidity']:,.0f} < $1K"
    return token, "PASS"

# === BUY ===
def buy_early_token(addr, token):
    global PERM_BLACKLIST
    now = datetime.now(timezone.utc).isoformat()
    
    trade = {
        'action': 'BUY',
        'token_address': addr,
        'token_name': token['name'],
        'entry_price': token['price'],
        'entry_mcap': int(token['mcap']),
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
        'peak_price': token['price'],
        'entry_reason': 'EARLY_PUMP_V13',
        'h1': 0, 'm5': 0, 'chg1_at_buy': 0, 'dip_at_buy': 0,
        'ath_mcap': token['mcap'],
        'holders': token['holders'],
        'top10': 0,
        'dex': 'pumpfun',
        'age_at_entry': token['age_min'],
    }
    
    try:
        with open(TRADES_FILE, 'a') as f:
            f.write(json.dumps(trade) + '\n')
        PERM_BLACKLIST.add(addr)
        with open(PERM_BLACKLIST_FILE, 'w') as f:
            json.dump(list(PERM_BLACKLIST), f)
        
        sym = token['symbol']
        rate = token['holder_rate']
        print(f"   🐣 EARLY BUY: {sym} | mcap ${token['mcap']:,.0f} | {token['age_min']:.1f}min | holders {token['holders']} ({rate:.1f}/min)")
        
        try:
            from alert_sender import send_telegram_alert
            msg = f"""🐣 EARLY BUY | {datetime.now(timezone.utc).strftime('%H:%M UTC')}
━━━━━━━━━━━━━━━
💰 {sym}
📍 MC: ${int(token['mcap']):,} | Liq: ${int(token['liquidity']):,}
⏱ {token['age_min']:.1f} min old | 👥 {token['holders']} holders ({rate:.1f}/min)
💵 Size: {POSITION_SIZE_EARLY} SOL

🔗 https://dexscreener.com/solana/{addr}
🥧 https://pump.fun/{addr}

⚠️ Early stage — stop {STOP_LOSS_EARLY}%"""
            send_telegram_alert(msg, "EARLY_BUY")
        except:
            pass
        return True
    except Exception as e:
        print(f"   ❌ Buy error: {e}")
        return False

# === SCAN CYCLE ===
def scan_cycle():
    global COOLDOWN_WATCH
    load_blacklist()
    
    tokens = get_new_pumpfun_tokens(50)
    print(f"[EARLY] Found {len(tokens)} qualifying pump.fun tokens (1-15min)")
    
    # Sort by holder_rate (most momentum first)
    tokens.sort(key=lambda x: x['holder_rate'], reverse=True)
    
    bought = 0
    for token in tokens:
        addr = token['address']
        if not addr:
            continue
        
        result, reason = filter_token(token)
        if result is None:
            continue
        
        sym = token['symbol']
        rate = token['holder_rate']
        
        # High momentum: >2 holders/min = strong organic interest
        if rate >= 2.0:
            print(f"   🚀 {sym}: {token['holders']} holders in {token['age_min']:.1f}min ({rate:.1f}/min) — HIGH MOMENTUM!")
        elif rate >= 1.0:
            print(f"   🐋 {sym}: {token['holders']} holders in {token['age_min']:.1f}min ({rate:.1f}/min) — buying!")
        else:
            print(f"   ⏳ {sym}: {token['holders']} holders ({rate:.1f}/min)")
        
        # Buy if holder_rate >= 1.0/min (strong organic momentum)
        if rate >= 1.0:
            COOLDOWN_WATCH.add(addr)
            if buy_early_token(addr, result):
                bought += 1
                if bought >= 1:
                    break
    
    # Clean cooldown
    if len(COOLDOWN_WATCH) > 200:
        COOLDOWN_WATCH = set()
    
    return bought > 0

# === MAIN ===
def main():
    print(f"🚀 PUMP EARLY SCANNER v1.3 Started")
    print(f"   Mcap: ${MIN_MCAP_EARLY:,}-${MAX_MCAP_EARLY:,} | Age: 1-15min")
    print(f"   Holders: {MIN_HOLDERS_EARLY}+ | Liq: ${MIN_LIQUIDITY_EARLY:,}+")
    print(f"   Signal: ≥1 holder/min = buy | Size: {POSITION_SIZE_EARLY} SOL | Stop: {STOP_LOSS_EARLY}%")
    
    load_blacklist()
    
    cycle = 0
    while True:
        try:
            cycle += 1
            print(f"\n[EARLY CYCLE {cycle}] {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}")
            scan_cycle()
        except Exception as e:
            print(f"[EARLY] Cycle error: {e}")
        time.sleep(30)

if __name__ == '__main__':
    main()
