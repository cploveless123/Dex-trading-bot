#!/usr/bin/env python3
"""
Whale Wallet Follower v2 - Copy trades from known profitable whales
Uses Solana RPC to monitor whale wallet token balances
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
LAST_SEEN_FILE = Path("/root/Dex-trading-bot/.whale_balances.json")

RPC_URL = "https://api.mainnet-beta.solana.com"

def load_whales():
    """Load whale wallets from db - top performers only"""
    try:
        with open(WHALE_DB) as f:
            d = json.load(f)
        # Filter to whales with >50% winrate and meaningful activity
        whales = [
            w for w in d.get('whales', []) 
            if w.get('winrate', 0) >= 0.5 and w.get('buy_count', 0) >= 3
        ]
        return whales
    except:
        return []

def get_token_balances(wallet):
    """Get all token balances for a wallet via Solana RPC"""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTokenAccountsByOwner",
        "params": [
            wallet,
            {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
            {"encoding": "jsonParsed"}
        ]
    }
    try:
        r = requests.post(RPC_URL, json=payload, timeout=15)
        if r.status_code == 200:
            data = r.json()
            accounts = data.get('result', {}).get('value', [])
            balances = []
            for acc in accounts:
                info = acc.get('account', {}).get('data', {}).get('parsed', {}).get('info', {})
                mint = info.get('mint', '')
                amount = info.get('tokenAmount', {}).get('uiAmount', 0)
                if amount and amount > 0:
                    balances.append({'mint': mint, 'amount': amount})
            return balances
    except Exception as e:
        pass
    return []

def load_last_balances():
    try:
        with open(LAST_SEEN_FILE) as f:
            return json.load(f)
    except:
        return {}

def save_last_balances(data):
    with open(LAST_SEEN_FILE, 'w') as f:
        json.dump(data, f)

def check_whale_new_positions():
    """Check if any whales have NEW token positions (they just bought)"""
    whales = load_whales()
    if not whales:
        return None
    
    last_balances = load_last_balances()
    new_buys = []
    
    for whale in whales:
        wallet = whale['wallet']
        old_balance = set(last_balances.get(wallet, {}).keys())
        
        current_balances = get_token_balances(wallet)
        current_mints = set(b['mint'] for b in current_balances)
        
        # New mints = new buys
        new_mints = current_mints - old_balance
        
        for mint in new_mints:
            bal = next((b for b in current_balances if b['mint'] == mint), None)
            if bal and bal['amount'] > 0.1:  # Only care about meaningful positions
                new_buys.append({
                    'wallet': wallet,
                    'mint': mint,
                    'amount': bal['amount'],
                    'winrate': whale.get('winrate', 0),
                    'avg_hold': whale.get('avg_hold_hours', 0)
                })
        
        # Update last seen
        last_balances[wallet] = {b['mint']: b['amount'] for b in current_balances}
    
    save_last_balances(last_balances)
    
    # Process new buys
    for buy in new_buys:
        addr = buy['mint']
        if not addr or len(addr) < 20:
            continue
        
        # Skip SOL (wrapped SOL mint)
        if addr == 'So11111111111111111111111111111111111111112':
            continue
        
        # Check if already tracked
        try:
            with open(TRADES_FILE) as f:
                existing = [json.loads(l) for l in f]
        except:
            existing = []
        
        already = any(
            t.get('token_address') == addr and t.get('status') in ['open', 'open_partial']
            for t in existing
        )
        if already:
            continue
        
        already_exited = any(
            t.get('token_address') == addr and (t.get('fully_exited') or t.get('tp1_sold'))
            for t in existing
        )
        if already_exited:
            continue
        
        # Get token info
        try:
            r = requests.get(f'https://api.dexscreener.com/latest/dex/tokens/{addr}', timeout=10)
            if r.status_code != 200:
                continue
            pairs = r.json().get('pairs', [])
            if not pairs:
                continue
            p = max(pairs, key=lambda x: x.get('liquidity', {}).get('usd', 0))
            m = p.get('fdv', 0) or p.get('marketCap', 0) or 0
            sym = p.get('baseToken', {}).get('symbol', '?')
            
            if not sym or not sym.isalpha() or len(sym) < 3:
                continue
            if sym in TICKER_BLACKLIST:
                continue
            
            bs_buys = p.get('txns', {}).get('h24', {}).get('buys', 0) or 0
            bs_sells = p.get('txns', {}).get('h24', {}).get('sells', 0) or 1
            bs = bs_buys / bs_sells if bs_sells > 0 else 0
            v5 = p.get('volume', {}).get('m5', 0) or 0
            holders = p.get('holders', 0) or 0
            liq = p.get('liquidity', {}).get('usd', 0) or 0
        except:
            continue
        
        # Apply filters - STRICTER for whale follow
        # Whales prefer sub-$10K mcap entries
        if m > 75000:
            continue  # Too mature
        
        # Strict BS requirement
        if bs < 1.5:
            continue
        
        # Volume filter
        if v5 > 0 and v5 < 1000:
            continue
        
        # Holders filter
        if holders > 0 and holders < 20:
            continue
        
        # PRIORITIZE sub-$10K entries (whale preference)
        is_sub_10k = m < 10000
        
        # === WHALE FOLLOW BUY ===
        trade = {
            "token": sym,
            "token_address": addr,
            "pair_address": p.get('pairAddress', ''),
            "amount_sol": POSITION_SIZE,
            "entry_mcap": int(m),
            "entry_liquidity": liq,
            "dex": p.get('dexId', 'unknown'),
            "action": "BUY",
            "source": "whale_follower_v2",
            "opened_at": datetime.utcnow().isoformat(),
            "status": "open",
            "entry_reason": f"WHALE_FOLLOW_wr{buy['winrate']*100:.0f}%",
            "whale_wallet": buy['wallet'][:20],
            "whale_winrate": round(buy['winrate'] * 100, 1),
            "whale_avg_hold_hours": round(buy['avg_hold'], 1),
            "bs_ratio": round(bs, 2), "whale_sub_10k": is_sub_10k
        }
        
        with open(TRADES_FILE, "a") as f:
            f.write(json.dumps(trade) + "\n")
        
        print(f"🐋 WHALE FOLLOW: {sym} @ ${m:,.0f} {'[SUB-10K]' if is_sub_10k else ''} (whale WR {buy['winrate']*100:.0f}%)")
        return sym
    
    return None

def main():
    whales = load_whales()
    print(f"🐋 Whale Follower v2 started - tracking {len(whales)} whales (WR >50%)")
    print("Waiting 2 min for whale balances to stabilize before detecting new positions...")
    
    # PRE-LOAD current whale balances so we only detect NEW buys after this point
    print("Pre-loading whale balances...")
    whales_with_balances = 0
    last_balances = {}
    for whale in whales:
        wallet = whale['wallet']
        current = get_token_balances(wallet)
        if current:
            last_balances[wallet] = {b['mint']: b['amount'] for b in current}
            whales_with_balances += 1
    save_last_balances(last_balances)
    print(f"Pre-loaded {whales_with_balances} whale balances - will detect only NEW buys after this point")
    
    while True:
        try:
            check_whale_new_positions()
        except Exception as e:
            print(f"Whale follower error: {e}")
        time.sleep(90)  # Check every 90 seconds (slower to avoid rate limits)

if __name__ == "__main__":
    main()
