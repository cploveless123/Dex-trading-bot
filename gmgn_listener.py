#!/usr/bin/env python3
"""GMGN Monitor - All channels"""
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

# All GMGN channels to monitor
GMGN_CHANNELS = [
    6887194564,  # gmgnaibot
    7346593882,   # @gmgn
    2065600367,   # @gmgnai
    2456265043,   # @gmgnsol
    1918096124,   # @gmgnBase
]

SIGNALS_DIR = Path("/root/Dex-trading-bot/signals")

def parse_gmgn_signal(message: str) -> dict:
    signal = {"source": "gmgn", "raw": message, "parsed_at": datetime.utcnow().isoformat()}
    
    # Token address
    token_pattern = r'[1-9A-HJ-NP-Za-km-z]{32,44}'
    tokens = re.findall(token_pattern, message)
    if tokens:
        signal["token_address"] = tokens[0]
    
    # Action
    if re.search(r'\bBUY\b', message, re.IGNORECASE):
        signal["action"] = "BUY"
    elif re.search(r'\bSELL\b', message, re.IGNORECASE):
        signal["action"] = "SELL"
    elif re.search(r'\bPUMP\b', message, re.IGNORECASE):
        signal["action"] = "PUMP"
    
    # Amount
    sol_pattern = r'(\d+(?:\.\d+)?)\s*SOL'
    sol_match = re.search(sol_pattern, message, re.IGNORECASE)
    if sol_match:
        signal["amount_sol"] = float(sol_match.group(1))
    
    return signal

async def main():
    print("🎯 GMGN Monitor Starting (all channels)...")
    client = TelegramClient(SESSION, API_ID, API_HASH)
    
    await client.connect()
    me = await client.get_me()
    print(f"   Logged in as: {me.username}")
    
    # Get all channel entities
    for ch_id in GMGN_CHANNELS:
        try:
            entity = await client.get_entity(ch_id)
            print(f"   Monitoring: {getattr(entity, 'username', None) or getattr(entity, 'first_name', 'Unknown')}")
        except:
            pass
    
    @client.on(NewMessage(chats=GMGN_CHANNELS))
    async def handle_signal(event):
        message = event.message.message or ""
        if len(message) > 10:  # Filter noise
            print(f"\n📡 GMGN: {message[:60]}...")
            
            signal = parse_gmgn_signal(message)
            if signal.get("token_address"):
                symbol = signal["token_address"][:10]
                filename = SIGNALS_DIR / f"gmgn_{symbol}_{int(datetime.utcnow().timestamp())}.json"
                with open(filename, 'w') as f:
                    json.dump(signal, f, indent=2)
                print(f"   ✅ Saved: {filename.name}")
                
                # Also send Telegram alert
                import os
                os.system(f'''curl -s -X POST "https://api.telegram.org/bot8650620888:AAHMOK5S6mRx5eZR_Kr0APe_NiMCXAg0Vys/sendMessage" -d "chat_id=6402511249" -d "text=📡 GMGN SIGNAL: {message[:200]}"''')
    
    print("   👂 Listening for all GMGN signals...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
