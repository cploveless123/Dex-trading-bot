#!/usr/bin/env python3
"""
Alert Sender - Real-time buy/sell alerts to Telegram
"""
import json
import requests
from datetime import datetime

BOT_TOKEN = "8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg"
CHAT_ID = "6402511249"

def send_alert(token, action, entry_mcap, exit_mcap=None, pnl=0, pnl_pct=0, exit_reason="", token_address=""):
    """Send real-time trade alert with full details"""
    
    if action == "BUY":
        msg = f"""✅ BUY EXECUTED
================
Token: {token}
Entry MC: ${entry_mcap:,}
Amount: 0.1 SOL

Links:
DexScreener: https://dexscreener.com/solana/{token_address}
DexTools: https://www.dextools.io/solana/token/{token_address}
PumpFun: https://pump.fun/{token_address}

Exit Rules:
+20% → Sell 75%
+100% → Full exit
-20% → Stop loss"""
    
    elif action == "SELL":
        msg = f"""🔴 SELL EXECUTED
================
Token: {token}
Entry MC: ${entry_mcap:,}
Exit MC: ${exit_mcap:,}
P&L: {pnl:+.4f} SOL ({pnl_pct:+.1f}%)
Exit: {exit_reason}

Links:
DexScreener: https://dexscreener.com/solana/{token_address}
DexTools: https://www.dextools.io/solana/token/{token_address}
PumpFun: https://pump.fun/{token_address}"""
    
    resp = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": msg}
    )
    return resp.json()

if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        token = sys.argv[1]
        action = sys.argv[2]
        entry_mcap = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        print(send_alert(token, action, entry_mcap))
