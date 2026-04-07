#!/usr/bin/env python3
"""
Simple Trading Bot - Clean Rewrite
"""
import json
import time
import os
from pathlib import Path
from datetime import datetime

# Config
SIGNALS_DIR = Path("/root/Dex-trading-bot/signals")
TRADES_FILE = Path("/root/Dex-trading-bot/trades/sim_trades.jsonl")
SIM_WALLET = Path("/root/Dex-trading-bot/sim_wallet.json")
STARTING_BALANCE = 1.0
TELEGRAM_BOT = "8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg"
TELEGRAM_CHAT = "6402511249"

# State
balance = STARTING_BALANCE
positions = []
stats = {"total_trades": 0, "wins": 0, "losses": 0, "best": 0, "worst": 0}
processed_signals = set()

def is_valid_solana(addr):
    """Check if valid Solana address"""
    if not addr:
        return False
    if addr == "0x0":
        return False
    if len(addr) < 32:
        return False
    if addr.startswith("0x"):
        return False  # Ethereum format
    return True

def load_state():
    global balance, positions, stats
    if SIM_WALLET.exists():
        with open(SIM_WALLET) as f:
            data = json.load(f)
            balance = data.get("balance", STARTING_BALANCE)
            positions = data.get("positions", [])
            stats = data.get("stats", stats)
    else:
        save_state()

def save_state():
    global balance, positions, stats
    with open(SIM_WALLET, "w") as f:
        json.dump({"balance": balance, "positions": positions, "stats": stats}, f, indent=2)

def save_trade(trade):
    global stats
    TRADES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TRADES_FILE, "a") as f:
        f.write(json.dumps(trade) + "\n")
    
    pnl = trade.get("pnl_sol", 0)
    stats["total_trades"] += 1
    if pnl > 0:
        stats["wins"] += 1
        stats["best"] = max(stats["best"], pnl)
    else:
        stats["losses"] += 1
        stats["worst"] = min(stats["worst"], pnl)
    save_state()

def score_signal(sig):
    """Simple scoring"""
    score = 0
    sig_list = sig.get("signals", [])
    
    # Strong buy signals
    if any(s in sig_list for s in ["BUY_MOMENTUM", "STRONG_BUY", "KOL_WALLET", "STRONG_BUY_PRESSURE", "INSIDER_BUY"]):
        score += 5
    # Pump signals  
    if any(s in sig_list for s in ["HIGH_VOLUME_PUMP", "PUMP"]):
        score += 4
    # Rapid movement
    if "RAPID_MOVE" in sig_list:
        score += 3
    
    # Liquidity scoring
    liq = sig.get("liquidity", 0)
    if liq >= 20000:
        score += 2
    if liq >= 50000:
        score += 1
    
    return score

def open_position(sig):
    global balance, positions
    if len(positions) >= 3:
        return None
    if balance < 0.1:
        return None
    
    token = sig.get("symbol", "UNKNOWN")
    addr = sig.get("token_address", "")
    
    # Validate address
    if not is_valid_solana(addr):
        print(f"  → Skipping {token}: invalid address {addr}")
        return None
    
    entry_price = sig.get("price", 0.00000001)
    liq = sig.get("liquidity", 0)
    mcap = sig.get("mcap", 0)
    
    position = {
        "token": token,
        "address": addr,
        "entry_price": entry_price,
        "entry_time": datetime.now().isoformat(),
        "liquidity": liq,
        "mcap": mcap,
        "size": 0.1,
        "pnl_sol": 0,
        "status": "open"
    }
    
    positions.append(position)
    balance -= 0.1
    save_state()
    
    msg = f"🟢 BUY 0.1 SOL of {token}\nEntry: ${entry_price:.8f}\nLiq: ${liq/1000:.1f}K | MCap: ${mcap/1000:.1f}K\n🔗 https://dexscreener.com/solana/{addr}\n📊 Balance: {balance:.4f} SOL"
    print(msg)
    send_telegram(msg)
    return position

def check_positions():
    global positions, balance
    if not positions:
        return
    
    for pos in positions[:]:
        # Simulate price movement (90 second candles)
        price_change = (hash(pos["token"]) % 200 - 50) / 100.0  # -50% to +150%
        current_price = pos["entry_price"] * (1 + price_change/100)
        
        tp1 = pos["entry_price"] * 1.5  # +50%
        tp2 = pos["entry_price"] * 1.75  # +100%
        stop = pos["entry_price"] * 0.7  # -30%
        
        pnl = (current_price - pos["entry_price"]) * pos["size"] / pos["entry_price"]
        
        if current_price >= tp2:
            # TP2 hit - full exit
            pnl = 0.075  # +100%
            balance += 0.1 + pnl
            pos["pnl_sol"] = pnl
            pos["status"] = "closed_tp2"
            save_trade(pos)
            positions.remove(pos)
            msg = f"🎯🎯 TP2 HIT! {pos['token']} at +100%\n💰 Profit: +{pnl:.4f} SOL\n📊 Balance: {balance:.4f} SOL"
            print(msg)
            send_telegram(msg)
            
        elif current_price >= tp1:
            # TP1 hit - sell 50%
            pnl = 0.05  # +50%
            balance += pnl
            pos["pnl_sol"] = pnl
            pos["status"] = "closed_tp1"
            save_trade(pos)
            positions.remove(pos)
            msg = f"🎯 TP1 HIT! {pos['token']} at +50%\n💰 Profit: +{pnl:.4f} SOL\n📊 Balance: {balance:.4f} SOL"
            print(msg)
            send_telegram(msg)
            
        elif current_price <= stop:
            # Stop loss hit
            pnl = -0.03  # -30%
            balance += 0.1 + pnl
            pos["pnl_sol"] = pnl
            pos["status"] = "closed_sl"
            save_trade(pos)
            positions.remove(pos)
            msg = f"🛑 STOP LOSS! {pos['token']} at -30%\n💰 Loss: {pnl:.4f} SOL\n📊 Balance: {balance:.4f} SOL"
            print(msg)
            send_telegram(msg)
        
        save_state()

def get_signals():
    """Get recent signals"""
    signals = []
    if not SIGNALS_DIR.exists():
        return signals
    
    for f in sorted(SIGNALS_DIR.glob("dexs_*.json"), key=lambda x: -x.stat().st_mtime)[:10]:
        if f.name in processed_signals:
            continue
        try:
            with open(f) as fp:
                sig = json.load(fp)
                sig["_file"] = f.name
                signals.append(sig)
                processed_signals.add(f.name)
        except:
            pass
    return signals

def _disabled_send_telegram(msg):
    """Send Telegram alert"""
    import urllib.request
    import urllib.parse
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT, "text": msg, "parse_mode": "Markdown"}
        req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode())
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def main():
    global balance, positions, stats
    
    print("🚀 SIMPLE TRADING BOT STARTED")
    load_state()
    print(f"💰 Balance: {balance:.4f} SOL")
    print(f"📊 Stats: {stats}")
    
    iteration = 0
    while True:
        iteration += 1
        
        # Check existing positions
        check_positions()
        
        # Check for new signals every 3 iterations
        if iteration % 3 == 0 and len(positions) < 3:
            signals = get_signals()
            print(f"\nIteration {iteration}: Checking {len(signals)} signals...")
            
            for sig in signals:
                score = score_signal(sig)
                token = sig.get("symbol", "?")
                liq = sig.get("liquidity", 0)
                addr = sig.get("token_address", "?")
                print(f"  {token}: score={score}, liq=${liq/1000:.1f}K, addr={addr[:20]}...")
                
                if score >= 5 and is_valid_solana(addr):
                    print(f"  → Opening position on {token}!")
                    open_position(sig)
        
        # Status update every minute
        if iteration % 10 == 0:
            print(f"💰 Balance: {balance:.4f} SOL | Positions: {len(positions)} | Stats: {stats}")
        
        time.sleep(30)

if __name__ == "__main__":
    main()
