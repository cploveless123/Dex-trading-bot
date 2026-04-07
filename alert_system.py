#!/usr/bin/env python3
"""
Real-time Alert System - Sends Telegram alerts for signals and trades
"""
import json
import time
from datetime import datetime
from pathlib import Path
import os

# Config - these would be set by the main system
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

SIGNALS_DIR = Path("/root/.openclaw/workspace/trading-bot/signals")
TRADES_FILE = Path("/root/.openclaw/workspace/trading-bot/trades/sim_trades.jsonl")
LAST_SIGNAL_FILE = Path("/root/.openclaw/workspace/trading-bot/.last_signal_sent")
LAST_TRADE_FILE = Path("/root/.openclaw/workspace/trading-bot/.last_trade_sent")

def send_telegram_message(text):
    """Send message via Telegram bot"""
    import urllib.request
    import urllib.parse
    
    if not TELEGRAM_BOT_TOKEN:
        print(f"📱 (Telegram not configured - would send): {text[:100]}...")
        return True
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    
    try:
        req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode())
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"Failed to send Telegram: {e}")
        return False

def format_gmgn_signal(sig):
    """Format signal in GMGN style"""
    symbol = sig.get('symbol', sig.get('token_address', 'UNKNOWN')[:8])
    action = sig.get('action', 'SIGNAL')
    source = sig.get('source', 'GMGN')
    
    if action == 'KOL_BUY':
        emoji = '🏐'
        action_text = f'{source.upper()} BUY'
    elif action == 'PUMP':
        emoji = '💊'
        action_text = f'{source.upper()} PUMP'
    elif action == 'KOTH':
        emoji = '👑'
        action_text = f'{source.upper()} KOTH'
    else:
        emoji = '📡'
        action_text = f'{source.upper()} SIGNAL'
    
    change = sig.get('change_pct', 0)
    liquidity = sig.get('liquidity', 0)
    mcap = sig.get('mcap', 0)
    
    liq_str = f"${liquidity/1000:.0f}K" if liquidity >= 1000 else f"${liquidity:.0f}"
    mcap_str = f"${mcap/1000:.0f}K" if mcap >= 1000 else f"${mcap:.0f}"
    
    token_addr = sig.get('token_address', '')
    dex_link = f"https://dexscreener.com/solana/{token_addr}" if token_addr else ""
    
    output = f"""{emoji} {action_text}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 {symbol}
📊 VOL +{change:.1f}%
💎 FDV: {mcap_str} | Liq: {liq_str}
🎯 TP1: +25% → Sell 75% | TP2: +75% → Sell 25% | Stop: -25%
🔗 {dex_link}"""
    
    return output

def format_trade(trade):
    """Format completed trade"""
    symbol = trade.get('token', 'UNKNOWN')
    source = trade.get('source', 'GMGN')
    pnl = trade.get('pnl_sol', 0)
    action = trade.get('action', 'BUY')
    reason = trade.get('exit_reason', 'UNKNOWN')
    token_addr = trade.get('token_address', '')
    dex_link = f"https://dexscreener.com/solana/{token_addr}" if token_addr else ""
    
    if action == 'KOL_BUY':
        emoji = '🏐'
    elif action == 'PUMP':
        emoji = '💊'
    elif action == 'KOTH':
        emoji = '👑'
    else:
        emoji = '📡'
    
    if pnl > 0:
        result = f"✅ WIN +{pnl:.4f} SOL"
    else:
        result = f"❌ LOSS {pnl:.4f} SOL"
    
    if reason == 'TP2':
        exit_text = "🎯🎯 TP2 HIT!"
    elif reason == 'TP1':
        exit_text = "🎯 TP1 HIT"
    elif reason == 'STOP_LOSS':
        exit_text = "🛑 STOP LOSS"
    else:
        exit_text = f"📤 {reason}"
    
    output = f"""📊 TRADE COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{emoji} {symbol}
{result} | {exit_text}
🔗 {dex_link}"""
    
    return output

def check_for_new_signals():
    """Check for new signals and send alerts"""
    last_id = 0
    if LAST_SIGNAL_FILE.exists():
        try:
            last_id = int(LAST_SIGNAL_FILE.read_text().strip())
        except:
            last_id = 0
    
    new_signals = []
    
    # Check GMGN signals
    for f in sorted(SIGNALS_DIR.glob("gmgn_*.json"), key=lambda x: -x.stat().st_mtime):
        try:
            fid = int(f.stem.split('_')[-1])
            if fid > last_id:
                with open(f) as fp:
                    sig = json.load(fp)
                    sig['_file_id'] = fid
                    new_signals.append(sig)
        except:
            pass
    
    # Check DexScreener signals
    for f in sorted(SIGNALS_DIR.glob("dexs_*.json"), key=lambda x: -x.stat().st_mtime):
        try:
            fid = int(f.stem.split('_')[-1])
            if fid > last_id:
                with open(f) as fp:
                    sig = json.load(fp)
                    sig['_source'] = 'dexscreener'
                    sig['_file_id'] = fid
                    new_signals.append(sig)
        except:
            pass
    
    # Sort by ID and get newest
    new_signals.sort(key=lambda x: x.get('_file_id', 0), reverse=True)
    
    if new_signals:
        sig = new_signals[0]
        last_id = sig.get('_file_id', last_id)
        LAST_SIGNAL_FILE.write_text(str(last_id))
        
        # Format and send
        text = format_gmgn_signal(sig)
        send_telegram_message(text)
        return sig
    
    return None

def check_for_new_trades():
    """Check for new completed trades and send alerts"""
    last_trade = ""
    if LAST_TRADE_FILE.exists():
        last_trade = LAST_TRADE_FILE.read_text().strip()
    
    if not TRADES_FILE.exists():
        return None
    
    # Read last trade
    with open(TRADES_FILE, 'r') as f:
        lines = f.readlines()
    
    if not lines:
        return None
    
    last_line = lines[-1].strip()
    if last_line == last_trade:
        return None
    
    # New trade
    try:
        trade = json.loads(last_line)
        LAST_TRADE_FILE.write_text(last_line)
        
        text = format_trade(trade)
        send_telegram_message(text)
        return trade
    except:
        pass
    
    return None

def get_balance():
    """Calculate current balance"""
    if not TRADES_FILE.exists():
        return 1.0, 0, 0
    
    with open(TRADES_FILE, 'r') as f:
        lines = f.readlines()
    
    balance = 1.0
    wins = 0
    losses = 0
    
    for line in lines:
        if line.strip():
            try:
                trade = json.loads(line)
                pnl = trade.get('pnl_sol', 0)
                balance += pnl
                if pnl > 0:
                    wins += 1
                else:
                    losses += 1
            except:
                pass
    
    return balance, wins, losses

def run_alert_loop():
    """Main alert loop"""
    print("🔔 Alert System Started")
    
    while True:
        try:
            # Check for new signals
            sig = check_for_new_signals()
            if sig:
                print(f"📡 Sent signal alert: {sig.get('symbol', '?')}")
            
            # Check for new trades
            trade = check_for_new_trades()
            if trade:
                print(f"📊 Sent trade alert: {trade.get('token', '?')} - {trade.get('pnl_sol', 0):+.4f}")
            
            time.sleep(10)  # Check every 10 seconds
            
        except Exception as e:
            print(f"Alert error: {e}")
            time.sleep(30)

if __name__ == "__main__":
    run_alert_loop()
