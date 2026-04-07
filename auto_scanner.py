#!/usr/bin/env python3
"""
Auto Scanner - Continuously finds and takes trades autonomously
Runs every 2 minutes, buys when criteria met, monitors TP/stop
"""
import requests, json
from datetime import datetime
import time

BOT_TOKEN = "8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg"
CHAT_ID = "6402511249"
TRADES_FILE = "/root/Dex-trading-bot/trades/sim_trades.jsonl"

# Entry criteria (adjusted for better wins)
LOW_MCAP_MIN = 5000
LOW_MCAP_MAX = 30000
MID_MCAP_MIN = 30000
MID_MCAP_MAX = 80000
MIN_VOLUME = 15000
MIN_BS_RATIO = 1.3
MIN_24H_CHANGE = 50
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

def get_live_mcap(pair_address):
    try:
        resp = requests.get(f"https://api.dexscreener.com/latest/dex/pairs/solana/{pair_address}", timeout=10)
        data = resp.json()
        pairs = data.get('pairs', [])
        if pairs:
            p = max(pairs, key=lambda x: x.get('liquidity', {}).get('usd', 0))
            return p.get('fdv', 0) or 0
    except:
        pass
    return None

def check_and_buy():
    """Scan and buy if criteria met"""
    timestamp = datetime.utcnow().strftime("%H:%M UTC")
    
    resp = requests.get(
        "https://api.dexscreener.com/token-profiles/latest/v1",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=10
    )
    
    if resp.status_code != 200:
        return None
    
    tokens = resp.json()[:40]
    
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
            
            if dex not in ['pumpfun', 'pumpswap']:
                continue
            
            # Check criteria
            low_cap = LOW_MCAP_MIN <= m < LOW_MCAP_MAX and v > MIN_VOLUME and bs >= MIN_BS_RATIO and chg >= MIN_24H_CHANGE
            mid_cap = MID_MCAP_MIN <= m < MID_MCAP_MAX and v > MIN_VOLUME * 1.5 and bs >= MIN_BS_RATIO and chg >= 30
            
            if low_cap or mid_cap:
                # Check if already have this token
                with open(TRADES_FILE) as f:
                    existing = [json.loads(l) for l in f]
                
                already_have = any(
                    t.get('token_address') == addr and t.get('status') in ['open', 'open_partial']
                    for t in existing
                )
                
                if already_have:
                    continue
                
                # Buy it
                trade = {
                    "token": sym,
                    "token_address": addr,
                    "pair_address": pair,
                    "amount_sol": POSITION_SIZE,
                    "entry_mcap": int(m),
                    "entry_liquidity": p.get('liquidity', {}).get('usd', 0),
                    "dex": dex,
                    "action": "BUY",
                    "source": "auto_scanner",
                    "opened_at": datetime.utcnow().isoformat(),
                    "status": "open"
                }
                
                with open(TRADES_FILE, "a") as f:
                    f.write(json.dumps(trade) + "\n")
                
                # Send alert
                msg = f"""✅ BUY EXECUTED | {timestamp}
━━━━━━━━━━━━━━━
💰 {sym}

📍 Entry MC: ${int(m):,}
💵 Amount: {POSITION_SIZE} SOL

🔗 https://dexscreener.com/solana/{pair}
🥧 https://pump.fun/{addr}

🎯 Exit Plan:
+25% → Sell 50%
+100% → Sell 25%
+500% → Sell 15%
Rest → Hold
⚠️ Stop: -25%"""
                
                send_alert(msg)
                print(f"✅ AUTO BOUGHT: {sym} @ ${m:,.0f}")
                return sym
        
        except Exception as e:
            print(f"Error scanning {addr}: {e}")
            continue
    
    return None

def main():
    print("🚀 Auto Scanner Started - Finding opportunities...")
    while True:
        try:
            check_and_buy()
        except Exception as e:
            print(f"Scanner error: {e}")
        time.sleep(120)  # Scan every 2 minutes

if __name__ == "__main__":
    main()
