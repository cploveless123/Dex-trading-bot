#!/usr/bin/env python3
"""
Position Monitor - Auto-execute TP/stop for open positions
Run continuously in background alongside scanner
"""
import requests, json
from datetime import datetime
import time
from trading_constants import TP1_PERCENT, TP1_SELL_PCT, TP2_PERCENT, TP2_SELL_PCT, STOP_LOSS_PERCENT, TRAILING_STOP_PCT, EXIT_PLAN_TEXT, SIM_RESET_TIMESTAMP

BOT_TOKEN = "8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg"
CHAT_ID = "6402511249"
TRADES_FILE = "/root/Dex-trading-bot/trades/sim_trades.jsonl"
POSITION_SIZE = 0.05

def get_live_mcap(tok_address):
    """Get current mcap for a token using its CA"""
    try:
        resp = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{tok_address}", timeout=10)
        data = resp.json()
        pairs = data.get('pairs', [])
        if pairs:
            p = max(pairs, key=lambda x: x.get('liquidity', {}).get('usd', 0))
            return p.get('fdv', 0) or 0
    except:
        pass
    return None

def send_alert(msg, label="ALERT"):
    """Send alert via Telegram"""
    import urllib.request, urllib.parse
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
    try:
        req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode())
        resp = urllib.request.urlopen(req, timeout=10)
        print(f"[{label}] ✅ Alert sent")
    except Exception as e:
        print(f"[{label}] ❌ Alert failed: {e}")

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
        tok = t.get('token_address', '')
        
        if not entry or not tok:
            continue
        
        mcap = get_live_mcap(tok)
        if not mcap:
            continue
        
        change = ((mcap - entry) / entry) * 100
        
        # Get current balance - only count PnL from trades opened after wallet reset
        with open(TRADES_FILE) as f_trades:
            all_trades = [json.loads(l) for l in f_trades]
        reset_ts = SIM_RESET_TIMESTAMP
        # Only trades opened after reset count toward PnL
        reset_trades = [tr for tr in all_trades if tr.get('opened_at', '') > reset_ts]
        closed_pnl = sum(tr.get('pnl_sol', 0) for tr in reset_trades if tr.get('status') == 'closed')
        open_full = len([tr for tr in reset_trades if tr.get('status') == 'open'])
        open_partial = len([tr for tr in reset_trades if tr.get('status') == 'open_partial'])
        locked = open_full * POSITION_SIZE + open_partial * POSITION_SIZE * ((100 - TP1_SELL_PCT) / 100)
        balance = 1.0 + closed_pnl - locked
        
        # TP1: +25% → sell 75%
        if change >= TP1_PERCENT and not t.get('tp1_sold'):
            t['tp1_sold'] = True
            t['partial_exit'] = True
            t['status'] = 'open_partial'  # still have 25% in
            t['exit_reason'] = 'TP1_AUTO'
            t['closed_at'] = datetime.utcnow().isoformat()
            # PnL: 75% of position sold at 25% gain
            tp1_pnl = POSITION_SIZE * (TP1_SELL_PCT / 100) * (TP1_PERCENT / 100)
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
🟢 Sold {TP1_SELL_PCT}% (initial investment): +{tp1_pnl:.4f} SOL (+{TP1_PERCENT}%)
💰 Wallet: {balance:.4f} SOL (~{100-TP1_SELL_PCT}% still in trade)

🔗 https://dexscreener.com/solana/{tok}
🥧 https://pump.fun/{tok}

📋 After TP1: Trailing stop — sell remaining if {TRAILING_STOP_PCT}% drop from peak
⚠️ Stop: {STOP_LOSS_PERCENT}% from entry
"""
            updated = True
        
        # TP2: TRAILING STOP — for remaining 30% after TP1
        # Track peak mcap since TP1, sell if price drops TRAILING_STOP_PCT from peak
        elif t.get('tp1_sold') and not t.get('tp2_sold') and not t.get('trailing_stopped'):
            # Update peak mcap
            current_peak = max(t.get('trail_peak_mcap', entry), mcap)
            t['trail_peak_mcap'] = current_peak
            
            # Calculate drawdown from peak
            peak = current_peak
            if peak > entry:
                drawdown_pct = ((peak - mcap) / peak) * 100
            else:
                drawdown_pct = 0
            
            # Trailing stop: sell remaining if drop from peak >= TRAILING_STOP_PCT
            if drawdown_pct >= TRAILING_STOP_PCT:
                t['trailing_stopped'] = True
                t['tp2_sold'] = True
                t['exit_reason'] = 'TRAILING_STOP'
                t['closed_at'] = datetime.utcnow().isoformat()
                
                # PnL: remaining % sold at current gain
                remaining_pct = (mcap - entry) / entry * 100
                tp2_pnl = POSITION_SIZE * ((100 - TP1_SELL_PCT) / 100) * (remaining_pct / 100)
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
                msg = f"""📊 TRAILING STOP (FULL EXIT) | {timestamp}
━━━━━━━━━━━━━━━
💰 {sym}
📍 Entry MC: ${entry:,}
📍 Peak MC: ${int(peak):,}
📍 Exit MC: ${int(mcap):,}
🟢 Total P&L: +{total_pnl:.4f} SOL (+{total_pct}%)
💰 Wallet: {balance:.4f} SOL
📋 Reason: Trailing stop ({drawdown_pct:.0f}% drop from peak)

🔗 https://dexscreener.com/solana/{tok}
🥧 https://pump.fun/{tok}"""
                send_alert(msg, "TP1")
                print(f"✅ {sym} TRAILING STOP: {drawdown_pct:.0f}% drop from peak ${int(peak):,}")
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

🔗 https://dexscreener.com/solana/{tok}
🥧 https://pump.fun/{tok}"""
            send_alert(msg, "STOP")
            print(f"🛑 {sym} STOP LOSS at {change:.0f}%")
            updated = True
    
    return updated

def main():
    print(f"📊 Position Monitor starting...")
    print(f"📋 Exit Plan: TP1 +{TP1_PERCENT}% (sell {TP1_SELL_PCT}%) | Trailing {TRAILING_STOP_PCT}% drop from peak | Stop {STOP_LOSS_PERCENT}%")
    
    # Test Telegram connectivity
    try:
        import urllib.request
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
        resp = urllib.request.urlopen(url, timeout=5)
        print(f"✅ Telegram connected")
    except Exception as e:
        print(f"❌ Telegram error: {e}")
    
    while True:
        try:
            check_positions()
        except Exception as e:
            print(f"Error: {e}")
        
        time.sleep(60)  # Check every 60 seconds

if __name__ == "__main__":
    main()
