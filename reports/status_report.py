#!/usr/bin/env python3
import json
from trading_constants import CHRIS_STARTING_BALANCE, SIM_RESET_TIMESTAMP

with open("trades/sim_trades.jsonl") as f:
    trades = [json.loads(l) for l in f]

reset = SIM_RESET_TIMESTAMP
rt = [t for t in trades if t.get("opened_at","") > reset]
open_now = [t for t in rt if not t.get("closed_at")]
closed = [t for t in rt if t.get("closed_at")]
wins = [t for t in closed if t.get("pnl_sol",0) > 0]
losses = [t for t in closed if t.get("pnl_sol",0) < 0]
pnl = sum(t.get("pnl_sol",0) for t in closed)
bal = CHRIS_STARTING_BALANCE + pnl
wr = len(wins)/(len(wins)+len(losses))*100 if wins+losses else 0
closed.sort(key=lambda x: x.get("closed_at",""), reverse=True)

output = f"""TRADE REPORT | {datetime.utcnow().strftime('%H:%M UTC')}
Balance: {bal:.4f} SOL
Record: {len(wins)}W/{len(losses)}L ({wr:.0f}% WR)
Open: {len(open_now)} positions
"""
for t in open_now:
    output += f"  {t['token']} | entry ${t.get('entry_mcap',0):,}\n"

output += "Last closed:\n"
for t in closed[:5]:
    p = t.get("pnl_sol",0)
    output += f"  {t['token']} | {t.get('exit_reason','?')} | {p:+.4f} | {t.get('closed_at','')[:19]}\n"

print(output)
