#!/usr/bin/env python3
"""Wilson progress report - sends to Telegram"""
import json
import requests
from datetime import datetime
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from trading_constants import POSITION_SIZE, TP1_SELL_PCT, EXIT_PLAN_TEXT, SIM_RESET_TIMESTAMP, CHRIS_STARTING_BALANCE

TRADES_FILE = Path(__file__).parent.parent / "trades" / "sim_trades.jsonl"

with open(TRADES_FILE) as f:
    trades = [json.loads(l) for l in f]

reset_ts = SIM_RESET_TIMESTAMP
reset_trades = [t for t in trades if t.get('opened_at', '') > reset_ts]
closed_all = [t for t in reset_trades if t.get('closed_at')]
open_full = [t for t in reset_trades if t.get('status') == 'open' and not t.get('closed_at')]
open_partial = [t for t in reset_trades if t.get('status') == 'open_partial' and not t.get('closed_at')]
open_pos = open_full + open_partial

closed_pnl = sum(t.get('pnl_sol', 0) for t in closed_all)
locked = (len(open_full) * POSITION_SIZE) + (len(open_partial) * POSITION_SIZE * ((100 - TP1_SELL_PCT) / 100))
balance = CHRIS_STARTING_BALANCE + closed_pnl
available = CHRIS_STARTING_BALANCE + closed_pnl - locked

wins = len([t for t in closed_all if t.get('pnl_sol', 0) > 0])
losses = len([t for t in closed_all if t.get('pnl_sol', 0) < 0])
breakeven = len([t for t in closed_all if t.get('pnl_sol', 0) == 0])
winrate = (wins / len(closed_all) * 100) if closed_all else 0

closed_all.sort(key=lambda x: x.get('closed_at', x.get('opened_at', '')), reverse=True)
recent_closed = closed_all[:5]

ts = datetime.utcnow().strftime("%H:%M UTC")

lines = []
lines.append(f"WILSON PROGRESS REPORT")
lines.append(f"{ts}")
lines.append(f"")
lines.append(f"━━━━━━━━━━━━━━━━━━━━")
lines.append(f"")
lines.append(f"💰 SIM WALLET")
lines.append(f"• Available: {available:.4f} SOL")
lines.append(f"• Locked (open positions): {locked:.4f} SOL")
lines.append(f"• Balance (after locks): {balance:.4f} SOL")
lines.append(f"")
lines.append(f"📈 RECORD: {wins}W / {losses}L ({winrate:.0f}% win rate)")
lines.append(f"• Total closed: {len(closed_all)} trades")
lines.append(f"• Open positions: {len(open_pos)} ({len(open_partial)} partial)")
lines.append(f"")
lines.append(f"🎯 EXIT PLAN:")
lines.append(EXIT_PLAN_TEXT)
lines.append(f"")
lines.append(f"━━━━━━━━━━━━━━━━━━━━")
lines.append(f"")
lines.append(f"📋 OPEN POSITIONS ({len(open_pos)}):")

for t in open_pos:
    sym = t.get('token', '?')
    entry = t.get('entry_mcap', 0)
    ca = t.get('token_address', '')
    partial = " (TP1 hit)" if t.get('status') == 'open_partial' else ""
    lines.append(f"• {sym}{partial} | Entry MC: ${entry:,}")
    lines.append(f"  🔗 https://dexscreener.com/solana/{ca}")

lines.append(f"")
lines.append(f"━━━━━━━━━━━━━━━━━━━━")
lines.append(f"")
lines.append(f"📋 LAST 5 CLOSED:")

for t in recent_closed:
    sym = t.get('token', '?')
    pnl = t.get('pnl_sol', 0)
    pct = t.get('pnl_pct', 0)
    reason = t.get('exit_reason', '?')
    emoji = "🟢" if pnl > 0 else "🔴"
    lines.append(f"{emoji} {sym} | {pnl:+.4f} SOL ({pct:+.0f}%) | {reason}")

lines.append(f"")
lines.append(f"━━━━━━━━━━━━━━━━━━━━")
lines.append(f"_Reports sent hourly. Balance from trade log._")

msg = "\n".join(lines)

resp = requests.post(
    "https://api.telegram.org/bot8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg/sendMessage",
    json={"chat_id": "6402511249", "text": msg, "parse_mode": "HTML"}
)
print(f"Sent: {resp.status_code == 200}, Balance: {balance:.4f} SOL, {wins}W/{losses}L")
