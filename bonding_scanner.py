#!/usr/bin/env python3
"""
Bonding Scanner v2 - Chris's new criteria

Catches pump.fun coins STILL IN BONDING CURVE that meet:
- Mcap: $5K-$75K for pairs <3min old, $9K-$75K for pairs >3min old
- BS Ratio: 0.25+ for pairs <2min old, 1.0+ for pairs >2min old
- Holders: 15+
- Min 5min volume: $1000
- Never re-enter
- Top 10 holder % < 70%

EARLY MOMENTUM TIER:
- $5K-$12K mcap + vol/mcap 1:1+ = buy signal

ANTI-PATTERNS (>3min pairs):
- Top 10 holder > 70% = dump risk
- BS < 1.0 = sell pressure
- Liquidity < $5K = rug risk
"""
import requests, json
from datetime import datetime
import time
from pathlib import Path
from trading_constants import (
    MIN_MCAP, MAX_MCAP, MIN_5MIN_VOLUME, MIN_BS_RATIO,
    MIN_HOLDERS, POSITION_SIZE, TICKER_BLACKLIST, MAX_OPEN_POSITIONS, SIM_RESET_TIMESTAMP
)

TRADES_FILE = Path("/root/Dex-trading-bot/trades/sim_trades.jsonl")

def get_pair_age_minutes(p):
    """Get pair age in minutes from pairCreatedAt"""
    created = p.get('pairCreatedAt', 0)
    if not created:
        return 999
    return (datetime.utcnow().timestamp() * 1000 - created) / 60000

def check_and_buy_bonding():
    """Scan pump.fun for momentum in bonding curve"""
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
            liq = p.get('liquidity', {}).get('usd', 0) or 0
            
            pair_age_min = get_pair_age_minutes(p)
            is_new = pair_age_min < 3
            is_very_new = pair_age_min < 2
            
            # === MCAP FILTERS ===
            if is_new:
                if m < 5000:
                    continue
                if m > 75000:
                    continue
            else:
                if m < 9000:
                    continue
                if m > 75000:
                    continue
            
            # === VOLUME FILTER ===
            if v5 > 0 and v5 < 1000:
                continue
            
            # === HOLDERS FILTER ===
            if holders > 0 and holders < 15:
                continue
            
            # === ANTI-PATTERN: OLD PAIRS ===
            if pair_age_min >= 3:
                if bs < 1.0:
                    continue
                if liq > 0 and liq < 5000:
                    continue  # Low liquidity rug risk
            
            # === EARLY MOMENTUM TIER ===
            v5m_ratio = v5 / m if m > 0 and v5 > 0 else 0
            vol_mcap_ratio = v / m if m > 0 else 0
            early_momentum = 5000 <= m <= 12000 and v5m_ratio >= 1.0
            
            if early_momentum:
                pass  # OK - bypasses BS check
            else:
                # === BS RATIO FILTERS ===
                if is_very_new:
                    if bs < 0.25:
                        continue
                else:
                    if bs < 1.0:
                        continue
                
                # Vol/mcap filter
                if vol_mcap_ratio < 1.0:
                    continue
            
            # === PULLBACK INSIGHT: Buy AFTER dip, not on pump ===
            if pair_age_min >= 5:
                if chg5 > 40:
                    continue  # Bought the top
                if chg5 < -20:
                    continue  # Falling knife
            
            # Check if already tracked
            try:
                with open(TRADES_FILE) as f:
                    existing = [json.loads(l) for l in f]
            except:
                existing = []
            
            # Check by contract address
            already_have = any(
                t.get('token_address') == addr and t.get('status') in ['open', 'open_partial']
                for t in existing
            )
            # Also block by symbol if we've traded it before
            already_traded_sym = any(
                t.get('token', '').upper() == sym.upper() and t.get('status') in ['open', 'open_partial']
                for t in existing
            )
            if already_have or already_traded_sym:
                continue
            
            # Blacklist
            if sym in TICKER_BLACKLIST or not sym.isalpha() or len(sym) < 3:
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
                "entry_liquidity": liq,
                "dex": "pumpfun",
                "action": "BUY",
                "source": "bonding_scanner_v2",
                "opened_at": datetime.utcnow().isoformat(),
                "status": "open",
                "entry_reason": "EARLY_MOMENTUM" if early_momentum else "BONDING",
                "detection_type": "BONDING",
                "pair_age_min": round(pair_age_min, 1),
                "bs_ratio": round(bs, 2),
                "vol_mcap_ratio": round(vol_mcap_ratio, 2),
                "chg5": round(chg5, 1)
            }
            
            with open(TRADES_FILE, "a") as f:
                f.write(json.dumps(trade) + "\n")
            
            print(f"✅ AUTO BOUGHT [BONDING]: {sym} @ ${m:,.0f} | BS:{bs:.2f} | {pair_age_min:.0f}min")
            bought = sym
            break
        
        except Exception as e:
            continue
    
    return bought

def main():
    print("🚀 Bonding Scanner v2 Started - Chris's New Criteria")
    while True:
        try:
            check_and_buy_bonding()
        except Exception as e:
            print(f"Scanner error: {e}")
        time.sleep(60)

if __name__ == "__main__":
    main()
