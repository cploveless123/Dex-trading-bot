from trading_constants import TP1_PERCENT, TP1_SELL_PCT, TP2_PERCENT, TP2_SELL_PCT, STOP_LOSS_PERCENT, EXIT_PLAN_TEXT

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
POSITION_SIZE = 0.05

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

def send_alert(msg):
    """Send alert via Telegram"""
    import urllib.request, urllib.parse
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
    try:
        req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode())
        urllib.request.urlopen(req, timeout=10)
    except:
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
        closed_pnl = sum(tr.get('pnl_sol', 0) for tr in all_trades if tr.get('status') == 'closed')
        open_count = len([tr for tr in all_trades if tr.get('status') in ['open', 'open_partial']])
        locked = open_count * POSITION_SIZE
        balance = 1.0 + closed_pnl - locked
        
        # TP1: +25% → sell 75%
        if change >= TP1_PERCENT and not t.get('tp1_sold'):
            t['tp1_sold'] = True
            t['partial_exit'] = True
            t['status'] = 'open_partial'  # still have 25% in
            t['exit_reason'] = 'TP1_AUTO'
            t['closed_at'] = datetime.utcnow().isoformat()
            # PnL: 75% of position sold at 25% gain
            tp1_pnl = POSITION_SIZE * 0.75 * (TP1_PERCENT / 100)
            t['pnl_sol'] = round(tp1_pnl, 6)
            t['pnl_pct'] = TP1_PERCENT
            
            with open(TRADES_FILE, 'w') as f:
                for tr in trades:
                    f.write(json.dumps(tr) + '\n')
            
            timestamp = datetime.utcnow().strftime("%H:%M UTC")
            msg = f"""🎯 TP1 HIT (Partial Exit) | {timestamp}
━━━━━━━━━━━━━━━
💰 {sym}
📍 Entry MC: ${entry:,}
📍 Exit MC: ${int(mcap):,}
🟢 Sold 75%: +{tp1_pnl:.4f} SOL (+{TP1_PERCENT}%)
💰 Wallet: {balance:.4f} SOL (25% still in trade)

🔗 https://dexscreener.com/solana/{pair}
🥧 https://pump.fun/{tok}

{EXIT_PLAN_TEXT}"""
            send_alert(msg)
            print(f"✅ {sym} TP1 AUTO: sold 75% at +{change:.0f}%")
            updated = True
        
        # TP2: +75% → sell remaining 25%
        elif change >= TP2_PERCENT and not t.get('tp2_sold'):
            t['tp2_sold'] = True
            t['exit_reason'] = 'TP2_AUTO'
            t['closed_at'] = datetime.utcnow().isoformat()
            # PnL: remaining 25% sold at 75% gain
            tp2_pnl = POSITION_SIZE * 0.25 * (TP2_PERCENT / 100)
            prev_pnl = t.get('pnl_sol', 0)
            total_pnl = round(tp2_pnl + prev_pnl, 6)
            total_pct = round((total_pnl / POSITION_SIZE) * 100, 1)
            t['pnl_sol'] = total_pnl
            t['pnl_pct'] = total_pct
            t['status'] = 'closed'
            
            with open(TRADES_FILE, 'w') as f:
                for tr in trades:
                    f.write(json.dumps(tr) + '\n')
            
            timestamp = datetime.utcnow().strftime("%H:%M UTC")
            msg = f"""🔴 SELL EXECUTED (FULL EXIT) | {timestamp}
━━━━━━━━━━━━━━━
💰 {sym}
📍 Entry MC: ${entry:,}
📍 Exit MC: ${int(mcap):,}
🟢 Total P&L: +{total_pnl:.4f} SOL (+{total_pct}%)
💰 Wallet: {balance:.4f} SOL
📋 Reason: TP2_AUTO

🔗 https://dexscreener.com/solana/{pair}
🥧 https://pump.fun/{tok}"""
            send_alert(msg)
            print(f"✅ {sym} TP2 AUTO: full exit at +{change:.0f}%")
            updated = True
        
        # Stop Loss: -25%
        elif change <= STOP_LOSS_PERCENT and not t.get('stopped'):
            t['stopped'] = True
            t['status'] = 'closed'
            t['exit_reason'] = 'STOP_AUTO'
            t['closed_at'] = datetime.utcnow().isoformat()
            stop_pnl = POSITION_SIZE * (abs(STOP_LOSS_PERCENT) / 100)
            t['pnl_sol'] = round(-stop_pnl, 6)
            t['pnl_pct'] = STOP_LOSS_PERCENT
            
            with open(TRADES_FILE, 'w') as f:
                for tr in trades:
                    f.write(json.dumps(tr) + '\n')
            
            timestamp = datetime.utcnow().strftime("%H:%M UTC")
            msg = f"""🛑 STOP LOSS | {timestamp}
━━━━━━━━━━━━━━━
💰 {sym}
📍 Entry MC: ${entry:,}
📍 Exit MC: ${int(mcap):,}
🔴 Loss: -{stop_pnl:.4f} SOL ({STOP_LOSS_PERCENT}%)
💰 Wallet: {balance:.4f} SOL
📋 Reason: STOP_AUTO

🔗 https://dexscreener.com/solana/{pair}
🥧 https://pump.fun/{tok}"""
            send_alert(msg)
            print(f"🛑 {sym} STOP LOSS at {change:.0f}%")
            updated = True
    
    return updated

def main():
    print(f"📊 Position Monitor starting...")
    print(f"📋 Exit Plan: TP1 +{TP1_PERCENT}% (sell {TP1_SELL_PCT}%) | TP2 +{TP2_PERCENT}% (sell {TP2_SELL_PCT}%) | Stop {STOP_LOSS_PERCENT}%")
    
    while True:
        try:
            check_positions()
        except Exception as e:
            print(f"Error: {e}")
        
        time.sleep(60)  # Check every 60 seconds

if __name__ == "__main__":
    main()
