import json, requests

trades = []
with open('/root/Dex-trading-bot/trades/sim_trades.jsonl') as f:
    for line in f:
        if line.strip():
            try:
                trades.append(json.loads(line))
            except:
                pass

with open('/root/Dex-trading-bot/sim_wallet.json') as f:
    w = json.load(f)

# Show LAST 10 trades (not just 5)
msg = "LAST 10 TRADES REPORT\n================\n\n"

if not trades:
    msg += "No trades this session\n\n"
else:
    recent = trades[-10:] if len(trades) >= 10 else trades
    for t in recent:
        token = t.get('token', '?')
        addr = t.get('token_address', '')
        entry_mcap = int(t.get('entry_mcap', t.get('mcap', 0)))
        exit_mcap = int(t.get('exit_mcap', 0)) if t.get('exit_mcap') else 0
        pnl = t.get('pnl_sol', 0)
        pnl_pct = (t.get('net_pct', 0) or t.get('pnl_pct', 0)) * 100
        exit_r = t.get('exit_reason', 'OPEN')
        
        msg += f"Token: {token}\n"
        msg += f"Entry MC: ${entry_mcap}\n"
        msg += f"Exit MC: ${exit_mcap}\n" if exit_mcap else "Exit MC: -\n"
        msg += f"P&L: {pnl:+.4f} SOL ({pnl_pct:+.1f}%)\n"
        msg += f"Exit: {exit_r}\n"
        if addr:
            msg += f"DexScreener: https://dexscreener.com/solana/{addr}\n"
            msg += f"DexTools: https://www.dextools.io/solana/token/{addr}\n"
            msg += f"PumpFun: https://pump.fun/{addr}\n"
        msg += "\n"

msg += "================\n"
msg += f"Wallet: {w['balances']['solana']:.4f} SOL, {w['balances']['ethereum']:.2f} ETH, {w['balances']['base']:.2f} BASE\n"
msg += f"Positions: {len([p for p in trades if not p.get('closed')])}"

resp = requests.post(
    "https://api.telegram.org/bot8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg/sendMessage",
    json={"chat_id": "6402511249", "text": msg}
)
print("Sent")
