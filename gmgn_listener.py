#!/usr/bin/env python3
"""
GMGN Channel Monitor - Listens to GMGN.AI signals
"""
import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from telethon import TelegramClient
from telethon.events import NewMessage

SESSION = "/root/Dex-trading-bot/gmgn_monitor.session"
API_ID = 30571469
API_HASH = "85d1c3567f4182f4e4a88334ec04b935"
GMGN_CHANNEL = 7346593882  # gmgnai_sol numeric ID

SIGNALS_DIR = Path("/root/Dex-trading-bot/signals")

def parse_gmgn_signal(message: str) -> dict:
    signal = {"source": "gmgn", "raw": message, "parsed_at": datetime.utcnow().isoformat()}
    token_pattern = r'[1-9A-HJ-NP-Za-km-z]{32,44}'
    tokens = re.findall(token_pattern, message)
    if tokens:
        signal["token_address"] = tokens[0]
    if re.search(r'\bBUY\b', message, re.IGNORECASE):
        signal["action"] = "BUY"
    elif re.search(r'\bSELL\b', message, re.IGNORECASE):
        signal["action"] = "SELL"
    sol_pattern = r'(\d+(?:\.\d+)?)\s*SOL'
    sol_match = re.search(sol_pattern, message, re.IGNORECASE)
    if sol_match:
        signal["amount_sol"] = float(sol_match.group(1))
    return signal

def save_signal(signal: dict):
    symbol = signal["token_address"][:8]
    filename = SIGNALS_DIR / f"gmgn_{symbol}_{int(datetime.utcnow().timestamp()*1000)}.json"
    with open(filename, 'w') as f:
        json.dump(signal, f, indent=2)
    print(f"   💾 Saved: {filename.name}")

async def main():
    print("🎯 GMGN Monitor Starting...")
    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.start()
    me = await client.get_me()
    print(f"   ✅ Logged in as: {me.username}")
    print(f"   👂 Listening for GMGN signals... (Ctrl+C to stop)")
    
    @client.on(NewMessage(chats=GMGN_CHANNEL))
    async def handle_message(event):
        message = event.message.message or ""
        if any(kw in message.upper() for kw in ['BUY', 'SELL', 'SOL', 'ENTRY', 'TP']):
            signal = parse_gmgn_signal(message)
            if signal.get('action') and signal.get('token_address'):
                save_signal(signal)
                print(f"\n📡 GMGN: {message[:100]}...")
    
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
