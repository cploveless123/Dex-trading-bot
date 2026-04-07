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

# STRICTER criteria based on pattern analysis
# WINNING: $5K-$15K mcap, pumpfun, MOMENTUM
# LOSING: $70K+ mcap, pumpswap
MIN_MCAP = 5000
MAX_MCAP = 20000  # Tighter cap based on data
MIN_VOLUME = 10000  # Higher volume requirement
MIN_BS_RATIO = 1.5
MIN_24H_CHANGE = 30
POSITION_SIZE = 0.05

def send_alert(msg):
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg}
        )
        return resp.status_code == 200
    except:
        return False

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
            
            # ONLY pumpfun, ONLY low mcap based on winning trades
            if dex != 'pumpfun':
                continue
            
            # Stricter mcap: $5K-$20K (winners were $5K-$15K mostly)
            if m < MIN_MCAP or m > MAX_MCAP:
                continue
            
            # Volume requirement: $30K+ for raydium, $20K+ for pump.fun (can have 0 liquidity during bonding)
            if dex == 'pumpfun' and v < 20000:
                continue
            if v < MIN_VOLUME:
                continue
            
            # Buy/sell ratio 1.5+ (winners had good ratio)
            if bs < MIN_BS_RATIO:
                continue
            
            # 24h change 30%+ (momentum needed)
            if chg < MIN_24H_CHANGE:
                continue
            
            # Check if already have this token
            with open(TRADES_FILE) as f:
                existing = [json.loads(l) for l in f]
            
            already_have = any(
                t.get('token_address') == addr and t.get('status') in ['open', 'open_partial']
                for t in existing
            )
            
            if already_have:
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
            
            msg = f"""✅ BUY EXECUTED | {timestamp}
━━━━━━━━━━━━━━━
💰 {sym}

🚀 MOMENTUM | Based on pattern analysis
📍 Entry MC: ${int(m):,}
💵 Amount: {POSITION_SIZE} SOL
💰 Wallet: {balance:.4f} SOL

🔗 https://dexscreener.com/solana/{pair}
🥧 https://pump.fun/{addr}

🎯 Exit Plan:
+25% → Sell 50%
+100% → Sell 50%


⚠️ Stop: -25%"""
            
            send_alert(msg)
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
