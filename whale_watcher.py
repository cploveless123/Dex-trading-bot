#!/usr/bin/env python3
"""
Whale Watcher v2 - On-chain wallet activity tracker
Uses Solana RPC to observe whale wallet transactions and learn from their moves
"""
import json
import time
import requests
from datetime import datetime
from pathlib import Path

WALLETS_FILE = Path(__file__).parent / "wallet_analysis" / "whale_wallets.jsonl"
ACTIVITY_FILE = Path(__file__).parent / "wallet_analysis" / "whale_activity.jsonl"
TRADES_FILE = Path(__file__).parent / "trades" / "sim_trades.jsonl"

RPC_URL = "https://api.mainnet-beta.solana.com"
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

def get_wallet_transactions(wallet, limit=10):
    """Get recent transactions for a wallet via Solana RPC"""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSignaturesForAddress",
        "params": [wallet, {"limit": limit}]
    }
    
    try:
        r = requests.post(RPC_URL, json=payload, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return data.get('result', [])
    except Exception as e:
        print(f"RPC error for {wallet[:15]}...: {e}")
    return []

def parse_transaction_type(tx):
    """Parse transaction to determine if buy/sell/transfer"""
    # This is simplified - real implementation would parse transaction details
    sig = tx.get('signature', '')
    # Transaction type detection would require full transaction parsing
    return {
        'signature': sig,
        'time': tx.get('blockTime'),
        'type': 'unknown'  # Would need getTransaction for full details
    }

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

def main():
    print("🐋 Whale Watcher v2 Started (on-chain)")
    
    while True:
        wallets = load_wallets()
        print(f"Monitoring {len(wallets)} wallets...")
        
        for wallet_entry in wallets:
            wallet = wallet_entry.get('wallet', '')
            if not wallet:
                continue
            
            txs = get_wallet_transactions(wallet, limit=5)
            
            if txs:
                # Log activity
                log_activity(wallet, 'tx_check', {
                    'tx_count': len(txs),
                    'latest_sig': txs[0].get('signature', '')[:20] if txs else ''
                })
                
                print(f"  🐋 {wallet[:15]}...: {len(txs)} recent txs")
        
        print("  Sleeping 3 minutes...")
        time.sleep(180)  # Check every 3 minutes

if __name__ == "__main__":
    main()