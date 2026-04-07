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
    """Send real-time trade alert with full details and timestamp"""
    
    timestamp = datetime.utcnow().strftime("%H:%M UTC")
    
    if action == "BUY":
        msg = f"""✅ BUY EXECUTED | {timestamp}
━━━━━━━━━━━━━━━
💰 {token}

📍 Entry MC: ${entry_mcap:,}
💵 Amount: 0.05 SOL

🔗 https://dexscreener.com/solana/{token_address}
🥧 https://pump.fun/{token_address}

🎯 Exit Plan:
+25% → Sell 50%
+100% → Sell 50%


⚠️ Stop: -25%"""
    
    elif action == "SELL":
        pnl_emoji = "🟢" if pnl >= 0 else "🔴"
        msg = f"""🔴 SELL EXECUTED | {timestamp}
━━━━━━━━━━━━━━━
💰 {token}

📍 Entry MC: ${entry_mcap:,}
📍 Exit MC: ${exit_mcap:,}
{pnl_emoji} P&L: {pnl:+.4f} SOL ({pnl_pct:+.1f}%)
📋 Reason: {exit_reason}

🔗 https://dexscreener.com/solana/{token_address}
🥧 https://pump.fun/{token_address}"""
    
    resp = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": msg}
    )
    
    return resp.status_code == 200
