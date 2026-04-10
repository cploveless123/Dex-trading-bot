#!/usr/bin/env python3
"""
Track wallets for buy/sell patterns
"""
import json
import subprocess
import time
from pathlib import Path

WALLET_FILE = Path("/root/.openclaw/workspace/memory/wallets/watchlist.json")
LOG_FILE = Path("/root/Dex-trading-bot/wallet_activity.log")

RPC_ENDPOINT = "https://api.mainnet-beta.solana.com"

def get_sol_balance(addr):
    cmd = f'''curl -s --max-time 10 -X POST {RPC_ENDPOINT} -H "Content-Type: application/json" -d '{{"jsonrpc": "2.0", "id": 1, "method": "getBalance", "params": ["{addr}"]}}' '''
    result = subprocess.run(cmd, shell=True, capture_output=True, timeout=15)
    try:
        data = json.loads(result.stdout)
        return data.get('result', {}).get('value', 0) / 1e9
    except subprocess.TimeoutExpired:
        print("Timeout getting balance")
        return 0
    except:
        return 0

def get_recent_tokens(addr, limit=3):
    cmd = f'''curl -s --max-time 10 -X POST {RPC_ENDPOINT} -H "Content-Type: application/json" -d '{{"jsonrpc": "2.0", "id": 1, "method": "getSignaturesForAddress", "params": ["{addr}", {{"limit": {limit}}}]}}' '''
    result = subprocess.run(cmd, shell=True, capture_output=True, timeout=15)
    try:
        data = json.loads(result.stdout)
        return [s['signature'] for s in data.get('result', [])]
    except subprocess.TimeoutExpired:
        print("Timeout getting signatures")
        return []
    except:
        return []

def load_wallets():
    if WALLET_FILE.exists():
        with open(WALLET_FILE) as f:
            return json.load(f).get('wallets', [])
    return []

def check_wallets():
    wallets = load_wallets()
    for w in wallets:
        addr = w['address']
        balance = get_sol_balance(addr)
        sigs = get_recent_tokens(addr, 2)
        
        # Check if balance changed significantly
        prev_balance = w.get('balance_sol', 0)
        if abs(balance - prev_balance) > 0.1:
            print(f"🔔 {addr[:8]}... | Balance: {prev_balance:.2f} → {balance:.2f} SOL")
            w['balance_sol'] = balance
            w['last_check'] = time.time()
            
            # Log activity
            with open(LOG_FILE, 'a') as f:
                f.write(f"{time.time()}: {addr} | {prev_balance:.2f} → {balance:.2f} SOL\n")
        
        w['recent_activity'] = sigs
    
    # Save updated
    with open(WALLET_FILE, 'w') as f:
        json.dump({"wallets": wallets}, f, indent=2)

if __name__ == "__main__":
    check_wallets()
