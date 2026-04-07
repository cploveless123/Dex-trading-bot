#!/usr/bin/env python3
"""
Whale Watcher - Monitor whale wallet activity and learn from their trades
"""
import json
import time
import requests
from datetime import datetime
from pathlib import Path
from collections import defaultdict

WALLETS_FILE = Path(__file__).parent / "wallet_analysis" / "whale_wallets.jsonl"
ACTIVITY_FILE = Path(__file__).parent / "wallet_analysis" / "whale_activity.jsonl"
TRADES_FILE = Path(__file__).parent / "trades" / "sim_trades.jsonl"

BOT_TOKEN = "8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg"
CHAT_ID = "6402511249"

def load_wallets():
    wallets = []
    if WALLETS_FILE.exists():
        with open(WALLETS_FILE) as f:
            for line in f:
                try:
                    wallets.append(json.loads(line))
                except:
                    pass
    return wallets

def get_wallet_token_balances(wallet):
    """Get all token balances for a wallet via DexScreener"""
    try:
        resp = requests.get(
            f"https://api.dexscreener.com/latest/dex/wallets/solana/{wallet}",
            timeout=15
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get('tokens', [])
    except:
        pass
    return []

def analyze_whale_move(wallet, tokens):
    """Analyze what whale is doing - buy/sell/hold"""
    moves = []
    
    for token in tokens:
        sym = token.get('symbol', '?')
        mc = token.get('marketCap', 0)
        liq = token.get('liquidity', 0)
        price_change = token.get('priceChange', {}).get('h24', 0)
        # This is simplified - real implementation would track position size
        
        if mc > 10000 and liq > 5000:
            moves.append({
                'wallet': wallet,
                'symbol': sym,
                'mcap': mc,
                'liquidity': liq,
                'price_change_24h': price_change,
                'type': 'active_position'
            })
    
    return moves

def log_activity(wallet, activity_type, data):
    """Log whale activity to file"""
    entry = {
        'wallet': wallet[:15] + '...',
        'type': activity_type,
        'timestamp': datetime.utcnow().isoformat(),
        'data': data
    }
    with open(ACTIVITY_FILE, 'a') as f:
        f.write(json.dumps(entry) + '\n')

def send_telegram(msg):
    """Send alert to Telegram"""
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg},
            timeout=10
        )
    except:
        pass

def format_whale_alert(wallet, tokens):
    """Format whale activity alert"""
    msg = f"""🐋 **WHALE ACTIVITY**
━━━━━━━━━━━━━━━━━━━
`{wallet[:15]}...`

**Active positions:** {len(tokens)}
"""
    for t in tokens[:3]:
        mc = t.get('marketCap', 0)
        liq = t.get('liquidity', 0)
        chg = t.get('priceChange', {}).get('h24', 0)
        sym = t.get('symbol', '?')
        msg += f"\n• {sym}: ${mc/1000:.1f}K mcap | {chg:+.0f}% 24h"
    
    return msg

def main():
    print("🐋 Whale Watcher Started")
    
    while True:
        wallets = load_wallets()
        print(f"Monitoring {len(wallets)} wallets...")
        
        for wallet_entry in wallets:
            wallet = wallet_entry.get('wallet', '')
            if not wallet:
                continue
            
            tokens = get_wallet_token_balances(wallet)
            
            if tokens:
                # Log activity
                log_activity(wallet, 'token_holdings', {
                    'count': len(tokens),
                    'total_mcap': sum(t.get('marketCap', 0) for t in tokens)
                })
                
                # Send alert for significant activity
                significant = [t for t in tokens if t.get('marketCap', 0) > 50000]
                if significant:
                    msg = format_whale_alert(wallet, significant)
                    send_telegram(msg)
                    print(f"  🐋 {wallet[:15]}...: {len(significant)} significant positions")
        
        print("  Sleeping 5 minutes...")
        time.sleep(300)  # Check every 5 minutes

if __name__ == "__main__":
    main()