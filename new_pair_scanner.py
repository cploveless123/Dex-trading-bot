#!/usr/bin/env python3
"""
New Pair Scanner v2 - Catches:
1. New Raydium v4 pairs (fresh listings)
2. Migrated pump.fun coins (graduated to Raydium v4)
3. High-momentum pump.fun coins (still in bonding)

Detects migrations by checking pump.fun CAs against new Raydium pairs.
"""
import requests, json
from datetime import datetime, timedelta
import time
from pathlib import Path
from trading_constants import (
    MIN_MCAP, MAX_MCAP, MIN_BS_RATIO,
    MIN_HOLDERS, MIN_5MIN_VOLUME, POSITION_SIZE,
    TICKER_BLACKLIST, MAX_OPEN_POSITIONS, SIM_RESET_TIMESTAMP
)

BOT_TOKEN = "8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg"
CHAT_ID = "6402511249"
TRADES_FILE = Path("/root/Dex-trading-bot/trades/sim_trades.jsonl")
PUMP_CA_CACHE = Path("/root/Dex-trading-bot/.pump_ca_cache.json")

def load_pump_cache():
    """Load cached pump.fun contract addresses"""
    try:
        with open(PUMP_CA_CACHE) as f:
            return set(json.load(f))
    except:
        return set()

def save_pump_cache(cache):
    """Save pump.fun CAs to avoid re-checking"""
    with open(PUMP_CA_CACHE, 'w') as f:
        json.dump(list(cache), f)

def get_mcap_data(addr):
    """Get full token data from DexScreener"""
    try:
        r = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{addr}", timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        pairs = data.get('pairs', [])
        if not pairs:
            return None
        return data, pairs
    except:
        return None

def is_pumpfun_token(addr, pairs):
    """Check if token is/was on pump.fun"""
    for p in pairs:
        if p.get('dexId') == 'pumpfun':
            return True
    return False

def get_raydium_pair(pairs):
    """Get the Raydium v4 pair if exists"""
    for p in pairs:
        if p.get('dexId') == 'raydium':
            return p
    return None

def get_pumpfun_pair(pairs):
    """Get the pump.fun pair if exists"""
    for p in pairs:
        if p.get('dexId') == 'pumpfun':
            return p
    return None

def is_migration(pump_pair, raydium_pair):
    """Detect if this is a pump.fun -> Raydium migration"""
    if not pump_pair or not raydium_pair:
        return False
    
    pump_created = pump_pair.get('pairCreatedAt', 0)
    raydium_created = raydium_pair.get('pairCreatedAt', 0)
    
    if not pump_created or not raydium_created:
        return False
    
    # Migration: pump created BEFORE raydium (pump was first, then migrated)
    pump_age_hours = (datetime.utcnow().timestamp() * 1000 - pump_created) / 3600000
    raydium_age_hours = (datetime.utcnow().timestamp() * 1000 - raydium_created) / 3600000
    
    # Pump is older than Raydium pair = migration
    return pump_age_hours > raydium_age_hours

def get_token_age_hours(pair):
    """Get age of a pair in hours"""
    created = pair.get('pairCreatedAt', 0)
    if not created:
        return 999
    return (datetime.utcnow().timestamp() * 1000 - created) / 3600000

def check_and_buy_new_pairs():
    """Scan for new Raydium pairs and migrations"""
    timestamp = datetime.utcnow().strftime("%H:%M UTC")
    
    # Check max open positions
    try:
        with open(TRADES_FILE) as f:
            all_trades = [json.loads(l) for l in f]
        reset = SIM_RESET_TIMESTAMP
        open_pos = [t for t in all_trades if t.get('opened_at','') > reset and not t.get('closed_at')]
        if len(open_pos) >= MAX_OPEN_POSITIONS:
            print(f"⏳ Max open positions ({MAX_OPEN_POSITIONS}) reached, skipping")
            return None
    except:
        pass
    
    # Load pump.fun CA cache
    pump_cache = load_pump_cache()
    
    # Fetch recent Raydium pairs
    try:
        # Try searching for recent SOL pairs
        resp = requests.get(
            "https://api.dexscreener.com/solana/dex/tokens/pump",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        if resp.status_code != 200:
            # Fallback: scan known pump.fun graduates
            resp = requests.get(
                "https://api.dexscreener.com/token-profiles/latest/v1",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10
            )
        
        tokens = resp.json()[:100] if resp.status_code == 200 else []
    except:
        tokens = []
    
    # Also try gmgn-cli for new listings
    try:
        import subprocess
        result = subprocess.run(
            ['gmgn-cli', 'new-listings', '--chain', 'sol', '--limit', '20'],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            try:
                new_data = json.loads(result.stdout)
                # Add to tokens if useful
                for item in new_data.get('data', new_data.get('list', []))[:20]:
                    if isinstance(item, dict) and item not in tokens:
                        tokens.append(item)
            except:
                pass
    except:
        pass
    
    bought = None
    
    # Scan tokens
    for tok_data in tokens[:50]:
        addr = tok_data.get('tokenAddress', '') or tok_data.get('address', '')
        if not addr:
            continue
        
        data_result = get_mcap_data(addr)
        if not data_result:
            continue
        
        data, pairs = data_result
        
        # Get primary pair (highest liquidity)
        primary = max(pairs, key=lambda x: x.get('liquidity', {}).get('usd', 0))
        raydium = get_raydium_pair(pairs)
        pump = get_pumpfun_pair(pairs)
        
        if not raydium:
            continue  # Need Raydium v4 pair
        
        m = raydium.get('fdv', 0) or raydium.get('marketCap', 0) or 0
        v = raydium.get('volume', {}).get('h24', 0) or 0
        v5 = raydium.get('volume', {}).get('m5', 0) or 0
        sym = raydium.get('baseToken', {}).get('symbol', '?')
        pair_addr = raydium.get('pairAddress', '')
        buys = raydium.get('txns', {}).get('h24', {}).get('buys', 0) or 0
        sells = raydium.get('txns', {}).get('h24', {}).get('sells', 0) or 1
        bs = buys / sells if sells > 0 else 0
        holders = raydium.get('holders', 0) or 0
        
        raydium_age_hours = get_token_age_hours(raydium)
        
        # === TYPE DETECTION ===
        is_migrated = pump and is_migration(pump, raydium)
        is_new_pair = raydium_age_hours < 6  # Fresh Raydium pair (<6h old)
        is_bonding = pump and not raydium  # Still in bonding curve
        
        if is_bonding:
            continue  # Skip pure bonding curve coins here
        
        # === FILTERS ===
        # Only scan sub-$15K for new/migrated pairs
        if m > 15000:
            continue
        
        if m < 5000:
            continue
        
        # Need volume evidence
        if v < 5000:
            continue
        
        # BS filter
        if bs < 1.2:
            continue
        
        # Freshness check
        if raydium_age_hours > 24:
            continue
        
        # Check if already tracked
        try:
            with open(TRADES_FILE) as f:
                existing = [json.loads(l) for l in f]
        except:
            existing = []
        
        already_have = any(
            t.get('token_address') == addr and t.get('status') in ['open', 'open_partial']
            for t in existing
        )
        if already_have:
            continue
        
        # Blacklist
        if sym in TICKER_BLACKLIST:
            continue
        
        # Never re-enter
        already_exited = any(
            t.get('token_address') == addr and (t.get('fully_exited') or t.get('tp1_sold'))
            for t in existing
        )
        if already_exited:
            continue
        
        # === DETECTION TYPE LOG ===
        if is_migrated:
            detection = "MIGRATED"
        elif is_new_pair:
            detection = "NEW_PAIR"
        else:
            detection = "RAYDIUM"
        
        # === BUY ===
        trade = {
            "token": sym,
            "token_address": addr,
            "pair_address": pair_addr,
            "amount_sol": POSITION_SIZE,
            "entry_mcap": int(m),
            "entry_liquidity": raydium.get('liquidity', {}).get('usd', 0),
            "dex": "raydium",
            "action": "BUY",
            "source": f"new_pair_scanner_v2_{detection}",
            "opened_at": datetime.utcnow().isoformat(),
            "status": "open",
            "entry_reason": detection,
            "detection_type": detection,
            "raydium_age_hours": round(raydium_age_hours, 1)
        }
        
        with open(TRADES_FILE, "a") as f:
            f.write(json.dumps(trade) + "\n")
        
        print(f"✅ AUTO BOUGHT [{detection}]: {sym} @ ${m:,.0f} | {raydium_age_hours:.1f}h Raydium | BS:{bs:.2f}")
        bought = sym
        break
    
    return bought

def main():
    print("🚀 New Pair Scanner v2 Started - New Pairs + Migrations + Bonding")
    while True:
        try:
            check_and_buy_new_pairs()
        except Exception as e:
            print(f"Scanner error: {e}")
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    main()
