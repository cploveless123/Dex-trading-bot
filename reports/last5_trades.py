import json, requests
from datetime import datetime
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from trading_constants import CHRIS_STARTING_BALANCE, POSITION_SIZE, TP1_SELL_PCT, SIM_RESET_TIMESTAMP

trades = []
with open('/root/Dex-trading-bot/trades/sim_trades.jsonl') as f:
    for line in f:
        if line.strip():
            try:
                trades.append(json.loads(line))
            except:
                pass

# Correct balance: 1.0 + closed_pnl - locked_in_open_positions
# Only count session trades (after SIM_RESET_TIMESTAMP)
reset_ts = SIM_RESET_TIMESTAMP
session_trades = [t for t in trades if t.get('opened_at', '') > reset_ts]
closed_all = [t for t in session_trades if t.get('fully_exited') or t.get('trailing_stopped') or t.get('status') == 'closed']
open_full = [t for t in session_trades if t.get('status') == 'open']
open_partial = [t for t in session_trades if t.get('status') == 'open_partial']

closed_pnl = sum(t.get('pnl_sol', 0) for t in closed_all)
locked = (len(open_full) * POSITION_SIZE) + (len(open_partial) * POSITION_SIZE * ((100 - TP1_SELL_PCT) / 100))
balance = CHRIS_STARTING_BALANCE + closed_pnl - locked

wins = len([t for t in closed_all if t.get('pnl_sol', 0) > 0])
losses = len([t for t in closed_all if t.get('pnl_sol', 0) < 0])

closed_all.sort(key=lambda x: x.get('closed_at', x.get('opened_at', '')), reverse=True)
recent = closed_all[:5]

# Build message in Chris-approved format
lines = []
lines.append(f"📊 TRADE REPORT | {datetime.utcnow().strftime('%H:%M UTC')}")
lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
lines.append(f"")
lines.append(f"💰 Balance: {balance:.4f} SOL")
lines.append(f"📈 Record: {wins}W / {losses}L")
lines.append(f"")
lines.append(f"━━━━━━━━ OPEN POSITIONS ━━━━━━━━")
lines.append(f"")

for t in open_full + open_partial:
    sym = t.get('token', '?')
    ca = t.get('token_address', '')
    entry = t.get('entry_mcap', 0)
    partial = " (TP1 hit)" if t.get('status') == 'open_partial' else ""
    lines.append(f"• {sym}{partial} | Entry MC: ${entry:,}")
    lines.append(f"  🔗 https://dexscreener.com/solana/{ca}")
    lines.append(f"")

lines.append(f"━━━━━━━━ LAST 5 TRADES ━━━━━━━━")
lines.append(f"")

for t in recent:
    sym = t.get('token', '?')
    entry_m = t.get('entry_mcap', 0)
    exit_m = t.get('exit_mcap', entry_m)
    if not exit_m:
        exit_m = entry_m
    pnl = t.get('pnl_sol', 0)
    pnl_pct = t.get('pnl_pct', 0)
    reason = t.get('exit_reason', 'OPEN')
    opened = t.get('opened_at', '')
    closed_at = t.get('closed_at', '')
    pair = t.get('pair_address', '')
    opened_fmt = opened.split('T')[1][:8] if opened else ''
    closed_fmt = closed_at.split('T')[1][:8] if closed_at else ''
    pnl_str = f"+{pnl:.4f}" if pnl >= 0 else f"{pnl:.4f}"
    pnl_emoji = "🟢" if pnl >= 0 else "🔴"
    lines.append(f"{pnl_emoji} {sym} | {pnl_str} SOL ({pnl_pct:+.0f}%)")
    lines.append(f"   BUY: ${entry_m:,} @ {opened_fmt} | SELL: ${exit_m:,} @ {closed_fmt}")
    lines.append(f"   Reason: {reason}")
    lines.append(f"   🔗 https://dexscreener.com/solana/{pair}")
    lines.append(f"")

msg = "\n".join(lines)

resp = requests.post(
    "https://api.telegram.org/bot8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg/sendMessage",
    json={"chat_id": "6402511249", "text": msg, "parse_mode": "HTML"}
)
print("Trade report sent:", resp.status_code == 200)
print(f"Balance: {balance:.4f} SOL | {wins}W/{losses}L | open: {len(open_full)} full, {len(open_partial)} partial")