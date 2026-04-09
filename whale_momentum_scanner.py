#!/usr/bin/env python3
"""
Whale Momentum Scanner v2
Combines whale patterns + token recognition for multi-strategy entry

Strategy A: Whale Coattail - whale buys in sub-$10K mcap
Strategy B: Pullback Momentum - pullback entries with whale confirmation
Strategy C: Pump Graduate - pump.fun graduation candidates
"""
import requests, json
from datetime import datetime
import time
from pathlib import Path
from trading_constants import (
    MIN_MCAP, MAX_MCAP, MIN_BS_RATIO,
    MIN_HOLDERS, MIN_5MIN_VOLUME, POSITION_SIZE,
    TICKER_BLACKLIST, MAX_OPEN_POSITIONS, SIM_RESET_TIMESTAMP
)

TRADES_FILE = Path("/root/Dex-trading-bot/trades/sim_trades.jsonl")
WHALE_DB = Path("/root/Dex-trading-bot/whales/whale_db.json")

def get_pair_age_minutes(p):
    created = p.get('pairCreatedAt', 0)
    if not created:
        return 999
    return (datetime.utcnow().timestamp() * 1000 - created) / 60000

def load_whales():
    try:
        with open(WHALE_DB) as f:
            d = json.load(f)
        return [w['wallet'] for w in d.get('whales', []) if w.get('winrate', 0) >= 0.5 and w.get('buy_count', 0) >= 3]
    except:
        return []

def check_anti_patterns(p, m, bs, holders, v5m_ratio, chg5):
    """Reject tokens with anti-patterns"""
    # Top10 holder check requires gmgn - skip for now
    # BS check
    if bs < 1.0:
        return True, "BS < 1.0"
    # Liquidity check
    liq = p.get('liquidity', {}).get('usd', 0) or 0
    if liq > 0 and liq < 5000:
        return True, "Low liquidity"
    # Pullback check
    if chg5 > 50:
        return True, "Chasing top"
    if chg5 < -30:
        return True, "Falling knife"
    return False, "OK"

def scan_strategy_a(p, m, v5, bs, holders, chg5, sym, addr, pair_addr, dex, p_data):
    """Strategy A: Whale Coattail - stricter filters"""
    # Sub-$10K mcap (whale preference)
    is_sub_10k = m < 10000
    
    # Stricter BS
    if bs < 1.5:
        return False, None
    
    # Holders
    if holders > 0 and holders < 20:
        return False, None
    
    # Volume
    if v5 > 0 and v5 < 1000:
        return False, None
    
    # Mcap
    if m > 75000:
        return False, None
    
    # Pullback required
    if chg5 > 15:
        return False, "A: chasing top (need pullback <+15%)"
    
    return True, {
        "strategy": "WHALE_COATTAIL",
        "sub_10k": is_sub_10k,
        "bs_strict": True
    }

def scan_strategy_b(p, m, v5, bs, holders, chg5, sym, addr, pair_addr, dex, p_data):
    """Strategy B: Pullback Momentum"""
    # BS requirement
    if bs < 1.5:
        return False, None
    
    # Holders
    if holders > 0 and holders < 20:
        return False, None
    
    # Mcap
    if m < 5000 or m > 75000:
        return False, None
    
    # Volume/mcap
    v = p.get('volume', {}).get('h24', 0) or 0
    vol_mcap = v / m if m > 0 else 0
    if vol_mcap < 2.0:
        return False, "B: low vol/mcap"
    
    # Pullback zone: 0-20% or negative with good BS
    if chg5 > 15:
        return False, "B: >15% pump"
    if chg5 < -15:
        return False, "B: too deep"
    if chg5 < 0 and bs < 2.0:
        return False, "B: dip no support"
    
    return True, {
        "strategy": "PULLBACK_MOMENTUM",
        "pullback": True,
        "bs_strict": True
    }

def scan_strategy_c(p, m, v5, bs, holders, chg5, sym, addr, pair_addr, dex, p_data):
    """Strategy C: Pump Graduate - pump.fun with graduation signals"""
    # Must be pump.fun
    if dex != 'pumpfun':
        return False, None
    
    # Mcap in graduation zone
    if m < 30000 or m > 75000:
        return False, None
    
    # Extreme BS
    if bs < 2.5:
        return False, "C: weak BS"
    
    # High holders
    if holders < 300:
        return False, "C: few holders"
    
    # High vol/mcap
    v = p.get('volume', {}).get('h24', 0) or 0
    vol_mcap = v / m if m > 0 else 0
    if vol_mcap < 5.0:
        return False, None
    
    return True, {
        "strategy": "PUMP_GRADUATE",
        "graduation_zone": True,
        "bs_boost": True
    }

def scan_token(addr):
    """Scan a single token across all strategies"""
    try:
        r = requests.get(f'https://api.dexscreener.com/latest/dex/tokens/{addr}', timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        pairs = data.get('pairs', [])
        if not pairs:
            return None
        
        p = max(pairs, key=lambda x: x.get('liquidity', {}).get('usd', 0))
        m = p.get('fdv', 0) or p.get('marketCap', 0) or 0
        v = p.get('volume', {}).get('h24', 0) or 0
        v5 = p.get('volume', {}).get('m5', 0) or 0
        sym = p.get('baseToken', {}).get('symbol', '?')
        pair_addr = p.get('pairAddress', '')
        dex = p.get('dexId', '')
        buys = p.get('txns', {}).get('h24', {}).get('buys', 0) or 0
        sells = p.get('txns', {}).get('h24', {}).get('sells', 0) or 1
        bs = buys / sells if sells > 0 else 0
        holders = p.get('holders', 0) or 0
        chg5 = p.get('priceChange', {}).get('m5', 0) or 0
        
        # Anti-pattern check
        is_anti, reason = check_anti_patterns(p, m, bs, holders, v5/m if m > 0 else 0, chg5)
        if is_anti:
            return None
        
        # Ticker check
        if not sym.isascii() or not sym.isalpha() or len(sym) < 3:
            return None
        
        # Try strategies
        for scan_fn, strat_name in [
            (scan_strategy_b, "B"),
            (scan_strategy_c, "C")
        ]:
            should_buy, meta = scan_fn(p, m, v5, bs, holders, chg5, sym, addr, pair_addr, dex, p)
            if should_buy and meta:
                meta['token'] = sym
                meta['mcap'] = m
                meta['bs'] = bs
                meta['holders'] = holders
                return meta
        
        return None
    
    except:
        return None

def check_and_buy():
    """Main scan + buy loop"""
    whales = load_whales()
    if not whales:
        return None
    
    # Get tokens from DexScreener
    try:
        resp = requests.get(
            "https://api.dexscreener.com/token-profiles/latest/v1",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        if resp.status_code != 200:
            return None
        tokens = resp.json()[:50]
    except:
        return None
    
    # Check max positions
    try:
        with open(TRADES_FILE) as f:
            existing = [json.loads(l) for l in f]
        reset = SIM_RESET_TIMESTAMP
        open_pos = [t for t in existing if t.get('opened_at','') > reset and not t.get('closed_at')]
        if len(open_pos) >= MAX_OPEN_POSITIONS:
            return None
    except:
        existing = []
    
    bought = None
    
    for tok_data in tokens:
        addr = tok_data.get('tokenAddress', '')
        if not addr:
            continue
        
        # Check if already tracked
        already = any(t.get('token_address') == addr and t.get('status') in ['open', 'open_partial'] for t in existing)
        if already:
            continue
        
        # Never re-enter
        already_exited = any(t.get('token_address') == addr and t.get('fully_exited') for t in existing)
        if already_exited:
            continue
        
        result = scan_token(addr)
        if not result:
            continue
        
        # Get full token data for trade
        try:
            r = requests.get(f'https://api.dexscreener.com/latest/dex/tokens/{addr}', timeout=10)
            p = max(r.json().get('pairs', []), key=lambda x: x.get('liquidity', {}).get('usd', 0))
            m = p.get('fdv', 0) or p.get('marketCap', 0) or 0
        except:
            continue
        
        trade = {
            "token": result['token'],
            "token_address": addr,
            "pair_address": p.get('pairAddress', ''),
            "amount_sol": POSITION_SIZE,
            "entry_mcap": int(m),
            "entry_liquidity": p.get('liquidity', {}).get('usd', 0),
            "dex": p.get('dexId', 'unknown'),
            "action": "BUY",
            "source": f"whale_momentum_{result['strategy']}",
            "opened_at": datetime.utcnow().isoformat(),
            "status": "open",
            "entry_reason": result['strategy'],
            "strategy_details": result,
            "bs_ratio": round(result.get('bs', 0), 2),
            "whale_sub_10k": result.get('sub_10k', False)
        }
        
        with open(TRADES_FILE, "a") as f:
            f.write(json.dumps(trade) + "\n")
        
        print(f"✅ {result['strategy']}: {result['token']} @ ${m:,.0f}")
        bought = result['token']
        break
    
    return bought

def main():
    whales = load_whales()
    print(f"🚀 Whale Momentum Scanner v2 - {len(whales)} whales loaded")
    
    time.sleep(60)
    print("Starting scans now")
    while True:
        try:
            check_and_buy()
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(60)

if __name__ == "__main__":
    main()
