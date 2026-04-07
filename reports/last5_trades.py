import json, subprocess

trades = []
with open('/root/Dex-trading-bot/trades/sim_trades.jsonl') as f:
    for line in f:
        try:
            trades.append(json.loads(line))
        except:
            pass

recent = [t for t in reversed(trades) if '2026-04-0' in str(t.get('opened_at',''))][-5:]

lines = []
lines.append("📊 LAST 5 TRADES")
lines.append("━━━━━━━━━━━━━━")

for i, t in enumerate(recent, 1):
    token = t.get('token', '?')
    addr = t.get('token_address', '')
    entry_mcap = int(t.get('entry_mcap', t.get('mcap', 0)))
    exit_mcap = int(t.get('exit_mcap', 0)) if t.get('exit_mcap') else 0
    pnl = t.get('pnl_sol', 0)
    pnl_pct = t.get('net_pct', 0) * 100
    exit_r = t.get('exit_reason', 'OPEN')
    
    lines.append(f"\n{i}. {token}")
    lines.append(f"   Entry: ${entry_mcap:,}")
    lines.append(f"   Exit: ${exit_mcap:,}" if exit_mcap else f"   Exit: -")
    lines.append(f"   P&L: {pnl:+.4f} SOL ({pnl_pct:+.1f}%)")
    lines.append(f"   Exit: {exit_r}")
    lines.append(f"   Links:")
    lines.append(f"   • DexScreener: https://dexscreener.com/solana/{addr}")
    lines.append(f"   • DexTools: https://www.dextools.io/solana/token/{addr}")
    lines.append(f"   • PumpFun: https://pump.fun/{addr}")

lines.append("\n━━━━━━━━━━━━━━")
with open('/root/Dex-trading-bot/sim_wallet.json') as f:
    w = json.load(f)
lines.append(f"💰 {w['balances']['solana']} SOL | {w['balances']['ethereum']} ETH | {w['balances']['base']} BASE")

msg = "\n".join(lines)

result = subprocess.run(
    ['curl', '-s', '-X', 'POST', 
     'https://api.telegram.org/bot8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg/sendMessage',
     '-d', 'chat_id=6402511249',
     '-d', f'text={msg}'],
    capture_output=True, text=True
)
print("Sent" if result.returncode == 0 else f"Error: {result.stderr}")
