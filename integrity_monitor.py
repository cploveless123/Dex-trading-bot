#!/usr/bin/env python3
"""
Integrity Monitor - Detect tampering with trading data
- Alerts if balance changes unexpectedly
- Alerts if SIM_RESET_TIMESTAMP moves forward
- Alerts if trade file is truncated
"""
import json, hashlib
from pathlib import Path
from datetime import datetime

TRADES_FILE = Path("/root/Dex-trading-bot/trades/sim_trades.jsonl")
CONSTANTS_FILE = Path("/root/Dex-trading-bot/trading_constants.py")
STATE_FILE = Path("/root/Dex-trading-bot/integrity_state.json")
ALERT_THRESHOLD = 0.05  # Alert if balance drifts more than 0.05 SOL unexplained

def get_file_hash(path):
    """Get SHA256 hash of a file"""
    try:
        with open(path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]
    except:
        return None

def load_state():
    """Load previous state"""
    try:
        return json.loads(STATE_FILE.read_text())
    except:
        return {}

def save_state(state):
    """Save current state"""
    STATE_FILE.write_text(json.dumps(state, indent=2))

def check_integrity():
    """Check for data tampering"""
    alerts = []
    state = load_state()
    
    # 1. Check SIM_RESET_TIMESTAMP hasn't moved forward
    try:
        with open(CONSTANTS_FILE) as f:
            content = f.read()
        for line in content.split('\n'):
            if 'SIM_RESET_TIMESTAMP' in line and '=' in line:
                # Get just the timestamp value, before any comment
                parts = line.split('=', 1)[1].split('#')[0].strip().strip("'\"")
                current_ts = parts
                prev_ts = state.get('sim_reset_timestamp', current_ts)
                if current_ts != prev_ts and prev_ts != 'UNKNOWN':
                    alerts.append(f"⚠️ SIM_RESET_TIMESTAMP changed: {prev_ts} → {current_ts}")
                state['sim_reset_timestamp'] = current_ts
                break
    except Exception as e:
        alerts.append(f"❌ Could not check constants: {e}")
    
    # 2. Check trade file line count
    try:
        with open(TRADES_FILE) as f:
            lines = f.readlines()
        current_count = len([l for l in lines if l.strip()])
        prev_count = state.get('trade_count', current_count)
        
        # Allow normal growth (new trades)
        expected_growth = max(0, current_count - prev_count)
        if expected_growth > 5:
            alerts.append(f"⚠️ Unusual trade growth: +{expected_growth} in one check cycle")
        
        state['trade_count'] = current_count
    except Exception as e:
        alerts.append(f"❌ Could not check trades: {e}")
    
    # 3. Check for balance consistency
    try:
        with open(TRADES_FILE) as f:
            trades = [json.loads(l) for l in f if l.strip()]
        
        reset_ts = state.get('sim_reset_timestamp', '2020-01-01T00:00:00.000000')
        reset_trades = [t for t in trades if t.get('opened_at', '') > reset_ts]
        
        # Calculate expected balance
        from trading_constants import CHRIS_STARTING_BALANCE as BAL, POSITION_SIZE, TP1_SELL_PCT
        
        closed_trades = [t for t in reset_trades if t.get('closed_at')]
        open_trades = [t for t in reset_trades if not t.get('closed_at')]
        
        closed_pnl = sum(t.get('pnl_sol', 0) for t in closed_trades)
        open_full = len([t for t in open_trades if t.get('status') == 'open'])
        open_partial = len([t for t in open_trades if t.get('status') == 'open_partial'])
        locked = (open_full * POSITION_SIZE) + (open_partial * POSITION_SIZE * 0.10)
        
        expected_balance = round(BAL + closed_pnl - locked, 4)
        
        prev_balance = state.get('last_balance', expected_balance)
        balance_diff = abs(expected_balance - prev_balance)
        
        # If balance changed without corresponding trades, alert
        if balance_diff > ALERT_THRESHOLD and expected_growth == 0:
            alerts.append(f"⚠️ Balance changed by {balance_diff:.4f} without new trades!")
        
        state['last_balance'] = expected_balance
    except Exception as e:
        alerts.append(f"❌ Could not check balance: {e}")
    
    # 4. Check file hash
    trade_hash = get_file_hash(TRADES_FILE)
    prev_hash = state.get('trade_hash')
    if prev_hash and trade_hash != prev_hash:
        if expected_growth == 0:
            alerts.append(f"⚠️ Trades file modified without new trades!")
    state['trade_hash'] = trade_hash
    
    # Save state
    save_state(state)
    
    return alerts

if __name__ == "__main__":
    alerts = check_integrity()
    if alerts:
        print("INTEGRITY ALERTS:")
        for a in alerts:
            print(f"  {a}")
    else:
        print("✅ Integrity check passed")
