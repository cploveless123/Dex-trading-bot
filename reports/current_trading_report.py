#!/usr/bin/env python3
"""Current trading report - compact view sent to Telegram"""
import json, requests
from datetime import datetime
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from trading_constants import POSITION_SIZE, TP1_SELL_PCT, SIM_RESET_TIMESTAMP, EXIT_PLAN_TEXT

TRADES_FILE = Path(__file__).parent.parent / "trades" / "sim_trades.jsonl"

with open(TRADES_FILE) as f:
    trades = [json.loads(l) for l in f]

reset_ts = SIM_RESET_TIMESTAMP
reset_trades = [t for t in trades if t.get('opened_at', '') > reset_ts]
closed = [t for t in reset_trades if t.get('status') == 'closed']
open_full = [t for t in reset_trades if t.get('status') == 'open']
open_partial = [t for t in reset_trades if t.get('status') == 'open_partial']
open_pos = open_full + open_partial

closed_pnl = sum(t.get('pnl_sol', 0) for t in closed)
locked = len(open_full) * POSITION_SIZE + len(open_partial) * POSITION_SIZE * ((100 - TP1_SELL_PCT) / 100)
balance = 1.0 + closed_pnl - locked

wins = len([t for t in closed if t.get('pnl_sol', 0) > 0])
losses = len([t for t in closed if t.get('pnl_sol', 0) < 0])

ts = datetime.utcnow().strftime("%H:%M UTC")

lines = []
lines.append(f"📊 TRADING REPORT | {ts}")
lines.append(f"━━━━━━━━━━━━━━━━━━━━")
lines.append(f"💰 Balance: {balance:.4f} SOL | {wins}W/{losses}L")
lines.append(f"📋 Open: {len(open_pos)} | Locked: {locked:.4f} SOL")
lines.append(f"")
lines.append(f"🎯 EXIT PLAN:")
lines.append(f"+35% → Sell initial investment")
lines.append(f"📊 Trailing stop: 20% from peak")
lines.append(f"⚠️ Stop: -25%")
lines.append(f"")

if open_pos:
    lines.append(f"OPEN POSITIONS ({len(open_pos)}):")
    for t in open_pos:
        sym = t.get('token', '?')
        entry = t.get('entry_mcap', 0)
        partial = " (TP1 hit)" if t.get('status') == 'open_partial' else ""
        lines.append(f"• {sym}{partial} @ ${entry:,}")
    lines.append(f"")

closed.sort(key=lambda x: x.get('closed_at', ''), reverse=True)
if closed[:3]:
    lines.append(f"LAST CLOSED:")
    for t in closed[:3]:
        sym = t.get('token', '?')
        pnl = t.get('pnl_sol', 0)
        pct = t.get('pnl_pct', 0)
        reason = t.get('exit_reason', '?')
        emoji = "🟢" if pnl > 0 else "🔴"
        lines.append(f"{emoji} {sym} | {pnl:+.4f} SOL | {reason}")

msg = "\n".join(lines)

resp = requests.post(
    "https://api.telegram.org/bot8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg/sendMessage",
    json={"chat_id": "6402511249", "text": msg, "parse_mode": "HTML"}
)
print(f"Sent: {resp.status_code == 200}, Balance: {balance:.4f} SOL")
