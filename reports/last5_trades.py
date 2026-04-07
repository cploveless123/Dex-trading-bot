import json, requests
from datetime import datetime

trades = []
with open('/root/Dex-trading-bot/trades/sim_trades.jsonl') as f:
    for line in f:
        if line.strip():
            try:
                trades.append(json.loads(line))
            except:
                pass

# Calculate balance and record
balance = 1.0 + sum(t.get('pnl_sol', 0) for t in trades)
wins = len([t for t in trades if t.get('pnl_sol', 0) > 0])
losses = len([t for t in trades if t.get('pnl_sol', 0) < 0])

# Get closed and open trades
closed = [t for t in trades if t.get('closed') or t.get('status') == 'closed']
closed.sort(key=lambda x: x.get('closed_at', x.get('opened_at', '')), reverse=True)
recent = closed[:5]

open_pos = [t for t in trades if t.get('status') == 'open']

# Build message in Chris-approved format
msg = f"📊 TRADE REPORT | {datetime.utcnow().strftime('%H:%M UTC')}\n"
msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
msg += f"💰 Balance: {balance:.4f} SOL\n"
msg += f"📈 Record: {wins}W / {losses}L\n\n"
msg += "━━━━━━━━ OPEN POSITIONS ━━━━━━━━\n\n"

for t in open_pos:
    sym = t.get('token', '?')
    pair = t.get('pair_address', '')
    entry = t.get('entry_mcap', 0)
    # Get live mcap
    try:
        resp = requests.get(f"https://api.dexscreener.com/latest/dex/pairs/solana/{pair}", timeout=10)
        data = resp.json()
        p = data.get('pairs', [{}])[0] if data.get('pairs') else {}
        mcap = p.get('fdv', 0) or 0
        chg = ((mcap - entry) / entry * 100) if entry > 0 else 0
        status = "🟢" if chg >= 0 else "🔴"
    except:
        status = "⚠️"
        chg = 0
        mcap = entry
    msg += f"{status} {sym}\n"
    msg += f"   Entry: ${entry:,} → Live: ${mcap:,.0f} ({chg:+.0f}%)\n"
    msg += f"   https://dexscreener.com/solana/{pair}\n\n"

msg += "━━━━━━━━ LAST 5 TRADES ━━━━━━━━\n\n"

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
    msg += f"{pnl_emoji} {sym} | {pnl_str} SOL ({pnl_pct:+.0f}%)\n"
    msg += f"   BUY: ${entry_m:,} @ {opened_fmt} | SELL: ${exit_m:,} @ {closed_fmt}\n"
    msg += f"   Reason: {reason}\n"
    msg += f"   https://dexscreener.com/solana/{pair}\n\n"

resp = requests.post(
    "https://api.telegram.org/bot8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg/sendMessage",
    json={"chat_id": "6402511249", "text": msg}
)
print("Trade report sent:", resp.status_code == 200)
