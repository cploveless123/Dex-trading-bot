#!/usr/bin/env python3
"""
GMGN Monitor - No start() needed with existing session
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
GMGN_CHANNEL = 6887194564

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

async def main():
    print("🎯 GMGN Monitor Starting (using existing session)...")
    client = TelegramClient(SESSION, API_ID, API_HASH)
    
    # Just connect, don't start() - session should be valid
    await client.connect()
    
    me = await client.get_me()
    print(f"   Logged in as: {me.username}")
    
    channel = await client.get_entity(GMGN_CHANNEL)
    print(f"   Monitoring: {channel.title}")
    
    @client.on(NewMessage(channels=[GMGN_CHANNEL]))
    async def handle_signal(event):
        message = event.message.message or ""
        print(f"\n📡 GMGN: {message[:80]}...")
        
        signal = parse_gmgn_signal(message)
        if signal.get("token_address"):
            symbol = signal["token_address"][:8]
            filename = SIGNALS_DIR / f"gmgn_{symbol}_{int(datetime.utcnow().timestamp())}.json"
            with open(filename, 'w') as f:
                json.dump(signal, f, indent=2)
            print(f"   ✅ Saved")
    
    print("   Listening for signals...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())