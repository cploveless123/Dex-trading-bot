#!/usr/bin/env python3
"""
Real-time Alert Sender - Uses OpenClaw message tool
"""
import json
import time
import sys
from pathlib import Path

# Paths
SIGNALS_DIR = Path("/root/.openclaw/workspace/trading-bot/signals")
TRADES_FILE = Path("/root/.openclaw/workspace/trading-bot/trades/sim_trades.jsonl")
LAST_SIGNAL_FILE = Path("/root/.openclaw/workspace/trading-bot/.last_alert_signal")
LAST_TRADE_FILE = Path("/root/.openclaw/workspace/trading-bot/.last_alert_trade")

def format_gmgn_signal(sig):
    symbol = sig.get('symbol', 'UNKNOWN')
    token_addr = sig.get('token_address', '')
    action = sig.get('action', 'SIGNAL')
    change = sig.get('change_pct', 0)
    liquidity = sig.get('liquidity', 0)
    mcap = sig.get('mcap', 0)
    holders = sig.get('holders', 0)
    
    liq_str = f"${liquidity/1000:.1f}K" if liquidity >= 1000 else f"${liquidity:.0f}"
    mcap_str = f"${mcap/1000:.1f}K" if mcap >= 1000 else f"${mcap:.0f}"
    change_str = f"+{change:.1f}%" if change >= 0 else f"{change:.1f}%"
    
    emoji = '💊' if action == 'PUMP' else '🏐' if action == 'KOL_BUY' else '👑' if action == 'KOTH' else '📡'
    action_text = 'PUMP' if action == 'PUMP' else 'KOL BUY' if action == 'KOL_BUY' else action
    
    dex_link = f"https://dexscreener.com/solana/{token_addr}" if token_addr else ""
    buy_cmd = f"/buy {token_addr} 0.1" if token_addr else ""
    
    return f"""{emoji} GMGN ALERT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 {symbol}
🔗 CA: {token_addr}
📊 Signal: PRICE{change_str}

💎 FDV: {mcap_str}
💧 Liquidity: {liq_str}
👥 Holders: {holders}
🔗 {dex_link}

⚙️ {buy_cmd}"""

def format_trade(trade):
    symbol = trade.get('token', 'UNKNOWN')
    pnl = trade.get('pnl_sol', 0)
    action = trade.get('action', 'BUY')
    reason = trade.get('exit_reason', 'UNKNOWN')
    token_addr = trade.get('token_address', '')
    
    emoji = '💊' if action == 'PUMP' else '🏐' if action == 'KOL_BUY' else '👑' if action == 'KOTH' else '📡'
    action_text = 'PUMP' if action == 'PUMP' else 'KOL BUY' if action == 'KOL_BUY' else action
    result = f"✅ WIN +{pnl:.4f} SOL" if pnl > 0 else f"❌ LOSS {pnl:.4f} SOL"
    exit_text = "🎯 TP2 HIT" if reason == 'TP2' else "🎯 TP1 HIT" if reason == 'TP1' else "🛑 STOP LOSS" if reason == 'STOP_LOSS' else f"📤 {reason}"
    
    dex_link = f"https://dexscreener.com/solana/{token_addr}" if token_addr else ""
    buy_cmd = f"/buy {token_addr} 0.1" if token_addr else ""
    
    return f"""📊 TRADE COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{emoji} {symbol} ({action_text})
{result} | {exit_text}
🔗 {dex_link}

⚙️ {buy_cmd}"""

def check_new_signals():
    last_id = 0
    if LAST_SIGNAL_FILE.exists():
        try:
            last_id = int(LAST_SIGNAL_FILE.read_text().strip())
        except:
            last_id = 0
    
    new_signals = []
    for f in sorted(SIGNALS_DIR.glob("gmgn_*.json"), key=lambda x: -x.stat().st_mtime):
        try:
            fid = int(f.stem.split('_')[-1])
            if fid > last_id:
                with open(f) as fp:
                    sig = json.load(fp)
                    sig['_fid'] = fid
                    new_signals.append(sig)
        except:
            pass
    
    if new_signals:
        new_signals.sort(key=lambda x: x.get('_fid', 0), reverse=True)
        sig = new_signals[0]
        LAST_SIGNAL_FILE.write_text(str(sig.get('_fid', 0)))
        return format_gmgn_signal(sig)
    return None

def check_new_trades():
    last_line = ""
    if LAST_TRADE_FILE.exists():
        last_line = LAST_TRADE_FILE.read_text().strip()
    
    if not TRADES_FILE.exists():
        return None
    
    with open(TRADES_FILE, 'r') as f:
        lines = f.readlines()
    
    if not lines:
        return None
    
    latest = lines[-1].strip()
    if latest and latest != last_line:
        LAST_TRADE_FILE.write_text(latest)
        try:
            trade = json.loads(latest)
            return format_trade(trade)
        except:
            pass
    return None

def get_status():
    if not TRADES_FILE.exists():
        return "💰 Balance: 1.0 SOL | 0 trades"
    
    with open(TRADES_FILE, 'r') as f:
        lines = [json.loads(l) for l in f.readlines() if l.strip()]
    
    balance = 1.0 + sum(t.get('pnl_sol', 0) for t in lines)
    wins = len([t for t in lines if t.get('pnl_sol', 0) > 0])
    losses = len([t for t in lines if t.get('pnl_sol', 0) <= 0])
    
    return f"💰 Balance: {balance:.4f} SOL ({((balance-1)/1*100):+.1f}%)\n📈 Record: {wins}W/{losses}L"

if __name__ == "__main__":
    # Check for new trades first
    trade_alert = check_new_trades()
    if trade_alert:
        print(f"📊 TRADE: {trade_alert[:80]}...")
        # Send via OpenClaw message tool - parent will handle this
    
    # Then check for new signals  
    signal_alert = check_new_signals()
    if signal_alert:
        print(f"📡 SIGNAL: {signal_alert[:80]}...")
    
    if trade_alert or signal_alert:
        print(f"\n{get_status()}")
