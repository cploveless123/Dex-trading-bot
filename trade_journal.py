#!/usr/bin/env python3
"""
Trade Journal - Records all trades to trades.jsonl
"""
import json
import os
from datetime import datetime
from pathlib import Path


TRADES_FILE = Path(__file__).parent.parent / "trades" / "trades.jsonl"


def log_trade(trade: dict):
    """Log a trade to the journal"""
    trade['timestamp'] = datetime.utcnow().isoformat()
    
    with open(TRADES_FILE, 'a') as f:
        f.write(json.dumps(trade) + '\n')
    
    print(f"📝 Trade logged: {trade.get('type')} {trade.get('token_symbol')}")


def get_trades():
    """Read all trades from journal"""
    if not TRADES_FILE.exists():
        return []
    
    trades = []
    with open(TRADES_FILE, 'r') as f:
        for line in f:
            if line.strip():
                trades.append(json.loads(line))
    return trades


def get_open_positions():
    """Get all open positions"""
    return [t for t in get_trades() if t.get('status') == 'open']


def get_closed_trades():
    """Get all closed trades"""
    return [t for t in get_trades() if t.get('status') == 'closed']


def calculate_pnl():
    """Calculate total P&L from closed trades"""
    closed = get_closed_trades()
    total_pnl = sum(t.get('pnl_sol', 0) for t in closed)
    return total_pnl


if __name__ == "__main__":
    # Demo
    print(f"Trades file: {TRADES_FILE}")
    print(f"Open positions: {len(get_open_positions())}")
    print(f"Closed trades: {len(get_closed_trades())}")
    print(f"Total P&L: {calculate_pnl()} SOL")