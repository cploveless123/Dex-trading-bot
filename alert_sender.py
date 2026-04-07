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
LAST_TRADE_FILE = Path("/root/Dex-trading-bot/.last_alert_trade")

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
    if not LAST_TRADE_FILE.exists():
        LAST_TRADE_FILE.write_text("")
    
    if not TRADES_FILE.exists():
        return None
    
    last = LAST_TRADE_FILE.read_text().strip()
    with open(TRADES_FILE) as f:
        lines = [l for l in f.readlines() if l.strip()]
    
    if not lines:
        return None
    
    latest = lines[-1]
    latest_hash = hash(latest)
    
    if str(latest_hash) != last:
        LAST_TRADE_FILE.write_text(str(latest_hash))
        trade = json.loads(latest)
        token = trade.get('token', 'UNKNOWN')
        pnl = trade.get('pnl_sol', 0)
        action = trade.get('action', 'UNKNOWN')
        return f"🔔 *Trade {action}*\n💰 {token}: {pnl:+.4f} SOL"

def get_status():
    if not TRADES_FILE.exists():
        return "💰 Balance: 1.0 SOL | No trades yet"
    
    with open(TRADES_FILE) as f:
        lines = [json.loads(l) for l in f.readlines() if l.strip()]
    
    balance = 1.0 + sum(t.get('pnl_sol', 0) for t in lines)
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
            
            signal_alert = check_new_signals()
            if signal_alert:
                send_telegram(signal_alert)
            
        except Exception as e:
            print(f"Error: {e}")
        
        time.sleep(30)

if __name__ == "__main__":
    main()
