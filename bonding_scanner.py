#!/usr/bin/env python3
"""
Bonding Scanner v2 - Catches pump.fun coins STILL IN BONDING CURVE
These are sub-$75K mcap coins that haven't graduated yet but showing strong momentum.

KEY INSIGHT: Buy AFTER the first pump + dump cycle, not during the pump.
Sweet spot: price up 5-40% in 5min (momentum) but NOT at peak.
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

BOT_TOKEN = "8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg"
TRADES_FILE = Path("/root/Dex-trading-bot/trades/sim_trades.jsonl")

def check_and_buy_bonding():
    """Scan pump.fun for momentum in bonding curve"""
    timestamp = datetime.utcnow().strftime("%H:%M UTC")
    
    # Check max open positions
    try:
        with open(TRADES_FILE) as f:
            all_trades = [json.loads(l) for l in f]
        reset = SIM_RESET_TIMESTAMP
        open_pos = [t for t in all_trades if t.get('opened_at','') > reset and not t.get('closed_at')]
        if len(open_pos) >= MAX_OPEN_POSITIONS:
            print(f"⏳ Max open positions reached, skipping")
            return None
    except:
        pass
    
    # Get trending pump.fun coins
    try:
        resp = requests.get(
            "https://api.dexscreener.com/token-profiles/latest/v1",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        if resp.status_code != 200:
            return None
        tokens = resp.json()[:100]
    except:
        return None
    
    bought = None
    
    for tok_data in tokens:
        addr = tok_data.get('tokenAddress', '')
        if not addr:
            continue
        
        try:
            r = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{addr}", timeout=10)
            if r.status_code != 200:
                continue
            
            data = r.json()
            pairs = data.get('pairs', [])
            if not pairs:
                continue
            
            p = max(pairs, key=lambda x: x.get('liquidity', {}).get('usd', 0))
            
            # Must be pump.fun ONLY (not on Raydium yet - still in bonding)
            if p.get('dexId') != 'pumpfun':
                continue
            
            m = p.get('fdv', 0) or p.get('marketCap', 0) or 0
            v = p.get('volume', {}).get('h24', 0) or 0
            v5 = p.get('volume', {}).get('m5', 0) or 0
            sym = p.get('baseToken', {}).get('symbol', '?')
            pair_addr = p.get('pairAddress', '')
            buys = p.get('txns', {}).get('h24', {}).get('buys', 0) or 0
            sells = p.get('txns', {}).get('h24', {}).get('sells', 0) or 1
            bs = buys / sells if sells > 0 else 0
            holders = p.get('holders', 0) or 0
            chg5 = p.get('priceChange', {}).get('m5', 0) or 0
            chg24 = p.get('priceChange', {}).get('h24', 0) or 0
            
            # === BONDING CURVE FILTERS ===
            # Must be in bonding (mcap < $75K on pump.fun)
            if m < 5000:
                continue
            if m > 75000:
                continue  # Graduated
            
            # 5min volume filter
            if v5 < MIN_5MIN_VOLUME:
                continue
            
            # === CHRIS'S PULLBACK INSIGHT ===
            # Buy AFTER first pump + dump cycle, not during the pump
            # Sweet spot: price up 5-40% in 5min showing momentum but NOT at peak
            # If 5min change > 50%, we caught the top - SKIP
            # If 5min change negative but > -20%, pullback entry is GOOD
            if chg5 > 50:
                continue  # Too hot - chasing top
            if chg5 < -30:
                continue  # Falling knife
            
            # BS ratio filter
            if bs < MIN_BS_RATIO:
                continue
            
            # Holders filter
            if holders > 0 and holders < MIN_HOLDERS:
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
            
            # === BUY ===
            trade = {
                "token": sym,
                "token_address": addr,
                "pair_address": pair_addr,
                "amount_sol": POSITION_SIZE,
                "entry_mcap": int(m),
                "entry_liquidity": p.get('liquidity', {}).get('usd', 0),
                "dex": "pumpfun",
                "action": "BUY",
                "source": "bonding_scanner_v2",
                "opened_at": datetime.utcnow().isoformat(),
                "status": "open",
                "entry_reason": "BONDING",
                "detection_type": "BONDING",
                "chg5": chg5,
                "bs_ratio": round(bs, 2)
            }
            
            with open(TRADES_FILE, "a") as f:
                f.write(json.dumps(trade) + "\n")
            
            print(f"✅ AUTO BOUGHT [BONDING]: {sym} @ ${m:,.0f} | BS:{bs:.2f} | 5m:{chg5:+.0f}%")
            bought = sym
            break
        
        except Exception as e:
            continue
    
    return bought

def main():
    print("🚀 Bonding Scanner v2 Started - Pump.fun Bonding Curve Momentum")
    while True:
        try:
            check_and_buy_bonding()
        except Exception as e:
            print(f"Scanner error: {e}")
        time.sleep(90)  # Check every 90 seconds

if __name__ == "__main__":
    main()
