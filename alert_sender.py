from trading_constants import EXIT_PLAN_TEXT

#!/usr/bin/env python3
"""
Real-time Alert Sender - Runs continuously, checks for new signals/trades and sends to Telegram
"""
import json
import urllib.request
import urllib.parse
import time
from pathlib import Path
from datetime import datetime

# Config
BOT_TOKEN = "8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg"
CHAT_ID = "6402511249"

SIGNALS_DIR = Path("/root/Dex-trading-bot/signals")
TRADES_FILE = Path("/root/Dex-trading-bot/trades/sim_trades.jsonl")
LAST_SIGNAL_FILE = Path("/root/Dex-trading-bot/.last_alert_signal")
# Track alerted trades to prevent duplicate alerts on file updates
ALERTED_TRADES_FILE = Path("/root/Dex-trading-bot/.alerted_trades")



def format_trade_alert(trade):
    """Format trade alert with full details"""
    timestamp = datetime.utcnow().strftime("%H:%M UTC")
    token = trade.get('token', '?')
    action = trade.get('action', 'UNKNOWN')
    token_addr = trade.get('token_address', '')
    entry_mcap = int(trade.get('entry_mcap', trade.get('mcap', 0)))
    exit_mcap = int(trade.get('exit_mcap', 0)) if trade.get('exit_mcap') else 0
    pnl = trade.get('pnl_sol', 0)
    pnl_pct = (trade.get('net_pct', 0) or trade.get('pnl_pct', 0)) * 100
    exit_r = trade.get('exit_reason', 'OPEN')
    
    # Calculate wallet balance correctly
    with open(TRADES_FILE) as f:
        all_trades = [json.loads(l) for l in f]
    # Treat old trades (status=None) as closed
    closed_pnl = sum(t.get('pnl_sol', 0) for t in all_trades if t.get('status') in ['closed', 'open_partial', None])
    # Full open positions: 0.05 locked each
    open_full = len([t for t in all_trades if t.get('status') == 'open'])
    # Partial exits: 0.0125 locked (25% still at risk)
    open_partial = len([t for t in all_trades if t.get('status') == 'open_partial'])
    locked = open_full * 0.05 + open_partial * 0.0125
    balance = 1.0 + closed_pnl - locked
    
    if action == "BUY":
        msg = f"""✅ BUY EXECUTED | {timestamp}
━━━━━━━━━━━━━━━
💰 {token}

📍 Entry MC: ${entry_mcap:,}
💵 Amount: 0.05 SOL
💰 Wallet: {balance:.4f} SOL

🔗 https://dexscreener.com/solana/{token_addr}
🥧 https://pump.fun/{token_addr}

{EXIT_PLAN_TEXT}"""
    else:
        pnl_emoji = "🟢" if pnl >= 0 else "🔴"
        msg = f"""🔴 SELL EXECUTED | {timestamp}
━━━━━━━━━━━━━━━
💰 {token}

📍 Entry MC: ${entry_mcap:,}
📍 Exit MC: ${exit_mcap:,}
{pnl_emoji} P&L: {pnl:+.4f} SOL ({pnl_pct:+.1f}%)
📋 Reason: {exit_r}

🔗 DexScreener: https://dexscreener.com/solana/{token_addr}
🥧 PumpFun: https://pump.fun/{token_addr}"""
    
    return msg

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode())
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

def format_signal(sig):
    symbol = sig.get('symbol', 'UNKNOWN')
    token_addr = sig.get('token_address', '')
    sig_list = sig.get('signals', [])
    liquidity = sig.get('liquidity', 0)
    mcap = sig.get('mcap', 0)
    
    liq_str = f"${liquidity/1000:.1f}K" if liquidity >= 1000 else f"${liquidity:.0f}"
    mcap_str = f"${mcap/1000:.1f}K" if mcap >= 1000 else f"${mcap:.0f}"
    sig_str = ', '.join(sig_list[:3])
    
    msg = f"📡 *{symbol.upper()}*\n"
    msg += f"📊 Signals: {sig_str}\n"
    msg += f"💎 Liq: {liq_str} | MCap: {mcap_str}\n"
    if token_addr:
        msg += f"🔗 https://dexscreener.com/solana/{token_addr}\n"
        msg += f"⚙️ /buy {token_addr} 0.1"
    return msg

def check_new_signals():
    if not LAST_SIGNAL_FILE.exists():
        LAST_SIGNAL_FILE.write_text("")
    
    last = LAST_SIGNAL_FILE.read_text().strip()
    signals = sorted(SIGNALS_DIR.glob("dexs_*.json"), key=lambda x: -x.stat().st_mtime)
    
    if not signals:
        return None
    
    latest = signals[0].name
    if latest != last:
        LAST_SIGNAL_FILE.write_text(latest)
        with open(signals[0]) as f:
            return format_signal(json.load(f))
    return None

def check_new_trades():
    """Check for NEW trades only (not updated existing trades)"""
    if not TRADES_FILE.exists():
        return None
    
    # Load already alerted trades
    alerted = set()
    if ALERTED_TRADES_FILE.exists():
        alerted = set(ALERTED_TRADES_FILE.read_text().strip().split('\n'))
    
    with open(TRADES_FILE) as f:
        lines = [l for l in f.readlines() if l.strip()]
    
    if not lines:
        return None
    
    # Check for NEW trades (not yet alerted) or newly closed trades
    for line in reversed(lines):
        trade = json.loads(line)
        token_addr = trade.get('token_address', '')
        action = trade.get('action', '')
        status = trade.get('status', '')
        trade_key = f"{token_addr}:{action}:{status}"
        
        # Skip if already alerted for this exact state
        if trade_key in alerted:
            continue
        
        # Only alert on NEW buys (action=BUY, status=open) or CLOSED trades (status=closed with exit)
        if action == 'BUY' and status == 'open':
            # Mark as alerted
            alerted.add(trade_key)
            ALERTED_TRADES_FILE.write_text('\n'.join(alerted))
            return format_trade_alert(trade)
        
        if status == 'closed' and trade.get('exit_reason'):
            # Mark as alerted
            alerted.add(trade_key)
            ALERTED_TRADES_FILE.write_text('\n'.join(alerted))
            return format_trade_alert(trade)
    
    return None

def get_status():
    if not TRADES_FILE.exists():
        return "💰 Balance: 1.0 SOL | No trades yet"
    
    with open(TRADES_FILE) as f:
        lines = [json.loads(l) for l in f.readlines() if l.strip()]
    
    # Treat old trades (status=None) as closed
    closed_pnl = sum(t.get('pnl_sol', 0) for t in lines if t.get('status') in ['closed', 'open_partial', None])
    # Full open positions: 0.05 locked each
    open_full = len([t for t in lines if t.get('status') == 'open'])
    # Partial exits: 0.0125 locked (25% still at risk)
    open_partial = len([t for t in lines if t.get('status') == 'open_partial'])
    locked = open_full * 0.05 + open_partial * 0.0125
    balance = 1.0 + closed_pnl - locked
    wins = len([t for t in lines if t.get('pnl_sol', 0) > 0])
    return f"💰 Balance: {balance:.4f} SOL\n📈 {len(lines)} trades | {wins}W"

def main():
    print("📱 Alert sender started")
    send_telegram("🔔 *Alert System Online!*\nMonitoring for signals and trades.")
    
    while True:
        try:
            trade_alert = check_new_trades()
            if trade_alert:
                send_telegram(trade_alert)
            
            # Signal alerts DISABLED - only send trade executed alerts
            # Chris said: "Either buy or pass - no presenting signals"
            # signal_alert = check_new_signals()
            # if signal_alert:
            #     send_telegram(signal_alert)
            
        except Exception as e:
            print(f"Error: {e}")
        
        time.sleep(30)

if __name__ == "__main__":
    main()
