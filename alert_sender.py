from trading_constants import EXIT_PLAN_TEXT, TP1_SELL_PCT, POSITION_SIZE, SIM_RESET_TIMESTAMP, CHRIS_STARTING_BALANCE

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
import pytz

# Config
BOT_TOKEN = "8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg"
CHAT_ID = "6402511249"

SIGNALS_DIR = Path("/root/Dex-trading-bot/signals")
TRADES_FILE = Path("/root/Dex-trading-bot/trades/sim_trades.jsonl")
LAST_SIGNAL_FILE = Path("/root/Dex-trading-bot/.last_alert_signal")
# Track alerted trades to prevent duplicate alerts on file updates
ALERTED_TRADES_FILE = Path("/root/Dex-trading-bot/.alerted_trades")
LAST_TRADE_INDEX_FILE = Path("/root/Dex-trading-bot/.last_alert_index")



def format_trade_alert(trade):
    """Format trade alert with full details"""
    timestamp = datetime.utcnow().strftime("%H:%M %Z")
    token = trade.get('token_name', trade.get('token', '疯'))
    action = trade.get('action', 'UNKNOWN')
    token_addr = trade.get('token_address', '')
    entry_mcap = int(trade.get('entry_mcap', trade.get('mcap', 0)))
    exit_mcap = int(trade.get('exit_mcap', 0)) if trade.get('exit_mcap') else 0
    pnl = trade.get('pnl_sol', 0)
    pnl_pct = (trade.get('net_pct', 0) or trade.get('pnl_pct', 0)) * 100
    exit_r = trade.get('exit_reason', 'OPEN')
    
    # Calculate wallet balance correctly - only count PnL from after reset
    with open(TRADES_FILE) as f:
        all_trades = [json.loads(l) for l in f]
    reset_ts = SIM_RESET_TIMESTAMP
    reset_trades = [t for t in all_trades if t.get('opened_at', '') > reset_ts]
    closed_pnl = sum(t.get('pnl_sol', 0) for t in reset_trades if t.get('closed_at'))
    # Full open positions: locked at POSITION_SIZE each
    open_full = len([t for t in reset_trades if t.get('status') == 'open'])
    # Partial exits: remaining % locked (v5.5 = 100% - 40% = 60% at TP2)
    open_partial = len([t for t in reset_trades if t.get('status') == 'open_partial'])
    locked = open_full * POSITION_SIZE + open_partial * POSITION_SIZE * 0.60
    balance = CHRIS_STARTING_BALANCE + closed_pnl - locked
    
    if action == "BUY":
        msg = f"""✅ BUY EXECUTED | {timestamp}
━━━━━━━━━━━━━━━
💰 {token}

📍 Entry MC: ${entry_mcap:,}
💵 Amount: {POSITION_SIZE} SOL
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

def format_tp1_alert(trade):
    """Format TP1 partial exit alert"""
    timestamp = datetime.utcnow().strftime("%H:%M %Z")
    token = trade.get('token_name', trade.get('token', '疯'))
    token_addr = trade.get('token_address', '')
    entry_mcap = int(trade.get('entry_mcap', 0))
    tp1_pnl = trade.get('pnl_sol', 0)  # pnl_sol holds the TP1 profit
    pnl_pct = trade.get('pnl_pct', 0)  # already in percent form
    
    with open(TRADES_FILE) as f:
        all_trades = [json.loads(l) for l in f]
    closed_pnl = sum(t.get('pnl_sol', 0) for t in all_trades if t.get('status') in ['closed', 'open_partial', None])
    open_full = len([t for t in all_trades if t.get('status') == 'open'])
    open_partial = len([t for t in all_trades if t.get('status') == 'open_partial'])
    locked = open_full * POSITION_SIZE + open_partial * POSITION_SIZE * ((100 - TP1_SELL_PCT) / 100)
    balance = CHRIS_STARTING_BALANCE + closed_pnl - locked
    
    remaining_pct = 100 - TP1_SELL_PCT
    msg = f"""🎯 TP1 HIT (Partial Exit) | {timestamp}
━━━━━━━━━━━━━━━
💰 {token}
📍 Entry MC: ${entry_mcap:,}
🟢 Sold {TP1_SELL_PCT}%: +{tp1_pnl:.4f} SOL ({pnl_pct:.1f}%)
💰 Wallet: {balance:.4f} SOL ({remaining_pct}% still in trade)

🔗 https://dexscreener.com/solana/{token_addr}
🥧 https://pump.fun/{token_addr}

{EXIT_PLAN_TEXT}"""
    return msg

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
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
    """Check for NEW trades only - only alert on trades added since last check"""
    if not TRADES_FILE.exists():
        return None
    
    # Get last alerted index
    last_index = 0
    if LAST_TRADE_INDEX_FILE.exists():
        try:
            last_index = int(LAST_TRADE_INDEX_FILE.read_text().strip())
        except:
            last_index = 0
    
    with open(TRADES_FILE) as f:
        lines = [l for l in f.readlines() if l.strip()]
    
    if not lines:
        return None
    
    # Only check trades AFTER the last alerted index
    for i in range(last_index, len(lines)):
        line = lines[i]
        trade = json.loads(line)
        token_addr = trade.get('token_address', '')
        action = trade.get('action', '')
        status = trade.get('status', '')
        
        # Only alert on NEW buys (action=BUY, status=open) or newly closed trades
        # New buy opened
        if action == 'BUY' and status == 'open':
            # Mark as alerted by updating index
            LAST_TRADE_INDEX_FILE.write_text(str(i + 1))
            return format_trade_alert(trade)
        
        # TP1 partial exit hit - send partial sell alert
        if status == 'open_partial' and trade.get('exit_reason') == 'TP1_AUTO':
            LAST_TRADE_INDEX_FILE.write_text(str(i + 1))
            return format_tp1_alert(trade)
        
        # Trade fully closed (TP2 or stop loss) - position_monitor handles these alerts
        # So we don't send duplicate alerts here
    
    # No new trades
    LAST_TRADE_INDEX_FILE.write_text(str(len(lines)))
    return None

def get_status():
    if not TRADES_FILE.exists():
        return "💰 Balance: 1.0 SOL | No trades yet"
    
    with open(TRADES_FILE) as f:
        all_trades = [json.loads(l) for l in f.readlines() if l.strip()]
    
    # Only count trades since reset
    reset_trades = [t for t in all_trades if t.get('opened_at', '') > SIM_RESET_TIMESTAMP]
    closed_pnl = sum(t.get('pnl_sol', 0) for t in reset_trades if t.get('closed_at'))
    open_full = [t for t in reset_trades if t.get('status') == 'open' and not t.get('closed_at')]
    open_partial = [t for t in reset_trades if t.get('status') == 'open_partial' and not t.get('closed_at')]
    locked = len(open_full) * POSITION_SIZE + len(open_partial) * POSITION_SIZE * ((100 - TP1_SELL_PCT) / 100)
    balance = CHRIS_STARTING_BALANCE + closed_pnl - locked
    wins = len([t for t in reset_trades if t.get('pnl_sol', 0) > 0])
    losses = len([t for t in reset_trades if t.get('pnl_sol', 0) < 0])
    
    # Build open positions string
    open_pos_str = ""
    if open_full or open_partial:
        open_pos_str = "\n\n📋 OPEN POSITIONS:"
        for t in open_full + open_partial:
            name = t.get('token_name', '?')
            ca = t.get('token_address', '')
            entry = t.get('entry_mcap', 0)
            open_pos_str += f"\n• {name} | Entry ${int(entry):,}"
            open_pos_str += f"\n  🔗 https://dexscreener.com/solana/{ca}"
    
    return f"💰 Balance: {balance:.4f} SOL\n📈 {len(reset_trades)} trades | {wins}W/{losses}L{open_pos_str}"

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
