from trading_constants import TP1_PERCENT, TP1_SELL_PCT, TP2_PERCENT, TP2_SELL_PCT, STOP_LOSS_PERCENT

#!/usr/bin/env python3
"""
Position Monitor - Auto-execute TP/stop for open positions
Run continuously in background alongside scanner
"""
import requests, json
from datetime import datetime
import time

BOT_TOKEN = "8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg"
CHAT_ID = "6402511249"
TRADES_FILE = "/root/Dex-trading-bot/trades/sim_trades.jsonl"

def get_live_mcap(pair_address):
    """Get current mcap for a pair"""
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

# Telegram alerts handled by alert_sender.py ONLY - no duplicate sending
def send_alert(msg):
    """DEPRECATED - use alert_sender.py only"""
    pass

def check_positions():
    """Check all open positions for TP/stop hits"""
    with open(TRADES_FILE) as f:
        trades = [json.loads(l) for l in f]
    
    updated = False
    
    for t in trades:
        # Include 'open_partial' as still open for further TP/stop monitoring
        if t.get('status') not in ['open', 'open_partial']:
            continue
        
        sym = t.get('token')
        entry = t.get('entry_mcap', 0)
        pair = t.get('pair_address', '')
        tok = t.get('token_address', '')
        
        if not entry or not pair:
            continue
        
        mcap = get_live_mcap(pair)
        if not mcap:
            continue
        
        change = ((mcap - entry) / entry) * 100
        
        # Get current balance
        with open(TRADES_FILE) as f_trades:
            all_trades = [json.loads(l) for l in f_trades]
        closed_pnl = sum(t.get('pnl_sol', 0) for t in all_trades if t.get('status') == 'closed')
        open_count = len([t for t in all_trades if t.get('status') in ['open', 'open_partial']])
        locked = open_count * 0.05
        balance = 1.0 + closed_pnl - locked
        
        # Check TP1 (+25%) - sell 50%
        if change >= 25 and not t.get('tp1_sold'):
            t['tp1_sold'] = True
            t['partial_exit'] = True
            t['status'] = 'open_partial'  # NOT closed - still have 50% position
            t['exit_reason'] = 'TP1_AUTO'
            t['closed_at'] = datetime.utcnow().isoformat()
            t['pnl_sol'] = 0.025
            t['pnl_pct'] = 25
            updated = True
            
            timestamp = datetime.utcnow().strftime("%H:%M UTC")
            msg = f"""🔴 SELL EXECUTED (50%) | {timestamp}
━━━━━━━━━━━━━━━
💰 {sym}

📍 Entry MC: ${entry:,}
📍 Exit MC: ${int(mcap):,}
🟢 P&L: +0.0250 SOL (+25.0%)
💰 Wallet: {balance:.4f} SOL
📋 Reason: TP1_AUTO

🔗 https://dexscreener.com/solana/{pair}
🥧 https://pump.fun/{tok}"""
            send_alert(msg)
            print(f"✅ {sym} TP1 AUTO: sold 50% at +{change:.0f}%")
        
        # Check TP2 (+75%) - sell remaining 25%
        elif change >= 100 and not t.get('tp2_sold'):
            t['tp2_sold'] = True
            t['exit_reason'] = 'TP2_AUTO'
            t['closed_at'] = datetime.utcnow().isoformat()
            t['pnl_sol'] = 0.05
            t['pnl_pct'] = 100
            t['status'] = 'closed'
            updated = True
            
            timestamp = datetime.utcnow().strftime("%H:%M UTC")
            msg = f"""🔴 SELL EXECUTED (remaining) | {timestamp}
━━━━━━━━━━━━━━━
💰 {sym}

📍 Entry MC: ${entry:,}
📍 Exit MC: ${int(mcap):,}
🟢 P&L: +0.0125 SOL (+75.0%)
💰 Wallet: {balance:.4f} SOL
📋 Reason: TP2_AUTO (full exit)

🔗 https://dexscreener.com/solana/{pair}
🥧 https://pump.fun/{tok}"""
            send_alert(msg)
            print(f"✅ {sym} TP2 AUTO: full exit at +{change:.0f}%")
            t['closed_at'] = datetime.utcnow().isoformat()
            t['pnl_sol'] = 0.10
            t['pnl_pct'] = 500
            t['status'] = 'closed'
            updated = True
            
            timestamp = datetime.utcnow().strftime("%H:%M UTC")
            msg = f"""🔴 SELL EXECUTED (15%) | {timestamp}
━━━━━━━━━━━━━━━
💰 {sym}

📍 Entry MC: ${entry:,}
📍 Exit MC: ${int(mcap):,}
🟢 P&L: +0.1000 SOL (+500.0%)
💰 Wallet: {balance:.4f} SOL
📋 Reason: TP3_AUTO

🔗 https://dexscreener.com/solana/{pair}
🥧 https://pump.fun/{tok}"""
            send_alert(msg)
            print(f"✅ {sym} TP3 AUTO: full exit at +{change:.0f}%")
        
        # Check Stop Loss (-25%)
        elif change <= -25 and not t.get('stopped'):
            t['stopped'] = True
            t['status'] = 'closed'
            t['exit_reason'] = 'STOP_AUTO'
            t['closed_at'] = datetime.utcnow().isoformat()
            t['pnl_sol'] = -0.025
            t['pnl_pct'] = -25
            updated = True
            
            timestamp = datetime.utcnow().strftime("%H:%M UTC")
            msg = f"""🔴 SELL EXECUTED | {timestamp}
━━━━━━━━━━━━━━━
💰 {sym}

📍 Entry MC: ${entry:,}
📍 Exit MC: ${int(mcap):,}
🔴 P&L: -0.0250 SOL (-25.0%)
💰 Wallet: {balance:.4f} SOL
📋 Reason: STOP_AUTO

🔗 https://dexscreener.com/solana/{pair}
🥧 https://pump.fun/{tok}"""
            send_alert(msg)
            print(f"🛑 {sym} STOP AUTO: closed at {change:.0f}%")
    
    if updated:
        with open(TRADES_FILE, 'w') as f:
            for t in trades:
                f.write(json.dumps(t) + '\n')
    
    return updated

def main():
    print("📊 Position Monitor Started - Auto TP/Stop")
    while True:
        try:
            check_positions()
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(15)  # Check every minute

if __name__ == "__main__":
    main()
