#!/usr/bin/env python3
"""
Auto Scanner v2 - Based on pattern analysis data
Tighter criteria: low mcap pumpfun only, avoid pumpswap
"""
import requests, json
from datetime import datetime
import time

BOT_TOKEN = "8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg"
CHAT_ID = "6402511249"
TRADES_FILE = "/root/Dex-trading-bot/trades/sim_trades.jsonl"

# STRICTER criteria based on 110-trade pattern analysis
# Mcap $5K-$100K, 24h vol $15K+, 5min vol $2K+, bs 1.5, holders 15+
MIN_MCAP = 5000        # floor
MAX_MCAP = 100000      # ceiling
MIN_VOLUME = 15000     # 24h volume minimum
MIN_5MIN_VOLUME = 2000 # 5min volume minimum (recent activity)
MIN_BS_RATIO = 1.5    # buy/sell ratio - winners have momentum
MIN_HOLDERS = 15       # holders minimum
POSITION_SIZE = 0.05

# Hard blacklist - NEVER re-enter these tickers
TICKER_BLACKLIST = {'NODES', 'nodes', 'Nodes'}

# Re-entry lockout: 30 min after any close, must have STRONG momentum to override
REENTRY_LOCKOUT_MINUTES = 30
REENTRY_BS_THRESHOLD = 3.0   # buy/sell ratio 3.0+ to override lockout
REENTRY_CHG_THRESHOLD = 60   # 24h change 60%+ to override lockout

# Telegram alerts handled by alert_sender.py - NOT here
def _do_not_use_send_alert(msg):
    # DEPRECATED - use alert_sender.py only
    pass

def check_and_buy():
    """Scan and buy if STRICTER criteria met based on pattern analysis"""
    timestamp = datetime.utcnow().strftime("%H:%M UTC")
    
    resp = requests.get(
        "https://api.dexscreener.com/token-profiles/latest/v1",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=10
    )
    
    if resp.status_code != 200:
        return None
    
    tokens = resp.json()[:80]
    
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
            m = p.get('fdv', 0) or 0
            v = p.get('volume', {}).get('h24', 0) or 0
            dex = p.get('dexId', '')
            sym = p.get('baseToken', {}).get('symbol', '?')
            pair = p.get('pairAddress', '')
            chg = p.get('priceChange', {}).get('h24', 0) or 0
            buys = p.get('txns', {}).get('h24', {}).get('buys', 0) or 0
            sells = p.get('txns', {}).get('h24', {}).get('sells', 0) or 1
            bs = buys / sells if sells > 0 else 0
            
            # 5min volume check
            v5 = p.get('volume', {}).get('h5', 0) or 0
            
            # ONLY pumpfun for now
            if dex != 'pumpfun':
                continue
            
            # Mcap: $5K-$100K
            if m < MIN_MCAP:
                continue
            if m > MAX_MCAP:
                continue
            
            # 24h volume: $15K+ for pumpfun
            if v < MIN_VOLUME:
                continue
            
            # 5min volume: $2K+ (recent activity)
            if v5 < MIN_5MIN_VOLUME:
                continue
            
            # Buy/sell ratio 1.5+ (winners had momentum)
            if bs < MIN_BS_RATIO:
                continue
            
            # Holders: 15+ if available
            holders = p.get('holders', 0) or 0
            if holders > 0 and holders < MIN_HOLDERS:
                continue
            
            # Check if already have this token (open or partial)
            with open(TRADES_FILE) as f:
                existing = [json.loads(l) for l in f]
            
            already_have = any(
                t.get('token_address') == addr and t.get('status') in ['open', 'open_partial']
                for t in existing
            )
            
            if already_have:
                continue
            
            # Hard blacklist - NEVER re-enter these tickers
            if sym in TICKER_BLACKLIST:
                continue
            
            # Block re-entry on any recently closed token
            # UNLESS token shows STRONG renewed momentum (bs 3.0+ AND chg 60%+)
            recently_closed = None
            for t in existing:
                if t.get('token_address') == addr and t.get('exit_reason') in ['STOP_AUTO', 'MANUAL_CLOSE', 'TP2', 'TP1_AUTO']:
                    from datetime import datetime as dt
                    closed = t.get('closed_at', '')
                    if closed:
                        try:
                            closed_ts = dt.fromisoformat(closed.replace('Z', '+00:00'))
                            age_minutes = (dt.utcnow() - closed_ts.replace(tzinfo=None)).total_seconds() / 60
                            if age_minutes < REENTRY_LOCKOUT_MINUTES:
                                recently_closed = t
                                break
                        except:
                            pass
            
            if recently_closed:
                if not (bs >= REENTRY_BS_THRESHOLD and chg >= REENTRY_CHG_THRESHOLD):
                    continue
            
            balance = 1.0 + sum(t.get('pnl_sol', 0) for t in existing)
            
            trade = {
                "token": sym,
                "token_address": addr,
                "pair_address": pair,
                "amount_sol": POSITION_SIZE,
                "entry_mcap": int(m),
                "entry_liquidity": p.get('liquidity', {}).get('usd', 0),
                "dex": dex,
                "action": "BUY",
                "source": "auto_scanner_v2",
                "opened_at": datetime.utcnow().isoformat(),
                "status": "open",
                "entry_reason": "MOMENTUM"
            }
            
            with open(TRADES_FILE, "a") as f:
                f.write(json.dumps(trade) + "\n")
            
            # DON'T send Telegram here - let alert_sender.py handle ALL alerts
            # This prevents double-sending
            print(f"✅ AUTO BOUGHT: {sym} @ ${m:,.0f}")
            return sym
        
        except Exception as e:
            continue
    
    return None

def main():
    print("🚀 Auto Scanner v2 Started - Based on pattern analysis")
    while True:
        try:
            check_and_buy()
        except:
            pass
        time.sleep(120)

if __name__ == "__main__":
    main()
