#!/usr/bin/env python3
"""
Learning Journal - Tracks signals vs outcomes
Builds pattern recognition over time
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List

TRADES_DIR = Path(__file__).parent.parent / "trades"
JOURNAL_FILE = TRADES_DIR / "learning_journal.jsonl"
ANALYSIS_FILE = TRADES_DIR / "signal_analysis.json"


def log_signal(signal: dict):
    """Log a detected signal with timestamp"""
    entry = {
        "type": "signal",
        "timestamp": datetime.utcnow().isoformat(),
        "data": signal
    }
    
    with open(JOURNAL_FILE, 'a') as f:
        f.write(json.dumps(entry) + '\n')


def log_outcome(token: str, pnl_pct: float, exit_reason: str, hold_time_minutes: float):
    """Log what happened after a signal"""
    entry = {
        "type": "outcome",
        "timestamp": datetime.utcnow().isoformat(),
        "token": token,
        "pnl_pct": pnl_pct,
        "exit_reason": exit_reason,
        "hold_time_minutes": hold_time_minutes
    }
    
    with open(JOURNAL_FILE, 'a') as f:
        f.write(json.dumps(entry) + '\n')


def analyze_patterns() -> Dict:
    """Analyze what signals predicted winners vs losers"""
    signals = []
    outcomes = []
    
    if Path(JOURNAL_FILE).exists():
        with open(JOURNAL_FILE, 'r') as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    if entry['type'] == 'signal':
                        signals.append(entry)
                    elif entry['type'] == 'outcome':
                        outcomes.append(entry)
    
    # Match signals to outcomes
    signal_outcomes = []
    for sig in signals:
        token = sig['data'].get('token_address', '')
        matching = [o for o in outcomes if o.get('token') == token]
        if matching:
            outcome = matching[0]
            signal_outcomes.append({
                'signal': sig['data'],
                'outcome': outcome,
                'won': outcome.get('pnl_pct', 0) > 0
            })
    
    # Analyze patterns
    patterns = {
        'total_signals': len(signals),
        'total_with_outcomes': len(signal_outcomes),
        'wins': sum(1 for s in signal_outcomes if s['won']),
        'losses': sum(1 for s in signal_outcomes if not s['won']),
    }
    
    if patterns['total_with_outcomes'] > 0:
        patterns['win_rate'] = patterns['wins'] / patterns['total_with_outcomes']
        patterns['avg_win'] = sum(s['outcome']['pnl_pct'] for s in signal_outcomes if s['won']) / max(patterns['wins'], 1)
        patterns['avg_loss'] = sum(s['outcome']['pnl_pct'] for s in signal_outcomes if not s['won']) / max(patterns['losses'], 1)
    
    return patterns


def print_report():
    """Print learning report"""
    patterns = analyze_patterns()
    
    print("📊 Signal Learning Report")
    print("=" * 40)
    print(f"Total signals detected: {patterns['total_signals']}")
    print(f"With outcomes tracked: {patterns['total_with_outcomes']}")
    
    if patterns.get('win_rate'):
        print(f"\n🎯 Win rate: {patterns['win_rate']*100:.1f}%")
        print(f"Avg win: +{patterns['avg_win']:.1f}%")
        print(f"Avg loss: {patterns['avg_loss']:.1f}%")
    else:
        print("\n⏳ Collecting data...")


if __name__ == "__main__":
    print_report()