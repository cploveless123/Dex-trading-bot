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

# Config
SESSION = "/root/Dex-trading-bot/gmgn_monitor.session"
API_ID = 30571469
API_HASH = "85d1c3567f4182f4e4a88334ec04b935"
GMGN_CHANNEL = 6887194564  # GMGN.AI

SIGNALS_DIR = Path(__file__).parent.parent / "signals"

# Token patterns
SOL_ADDRESS = "So11111111111111111111111111111111111111112"

def parse_gmgn_signal(message: str) -> dict:
    """Parse GMGN signal from message text"""
    signal = {
        "source": "gmgn",
        "raw": message,
        "parsed_at": datetime.utcnow().isoformat()
    }
    
    # Token address (Solana base58)
    token_pattern = r'[1-9A-HJ-NP-Za-km-z]{32,44}'
    tokens = re.findall(token_pattern, message)
    if tokens:
        signal["token_address"] = tokens[0]
    
    # Action
    if re.search(r'\bBUY\b', message, re.IGNORECASE):
        signal["action"] = "BUY"
    elif re.search(r'\bSELL\b', message, re.IGNORECASE):
        signal["action"] = "SELL"
    
    # Amount (SOL or token)
    sol_pattern = r'(\d+(?:\.\d+)?)\s*SOL'
    sol_match = re.search(sol_pattern, message, re.IGNORECASE)
    if sol_match:
        signal["amount_sol"] = float(sol_match.group(1))
    
    # Entry price
    entry_pattern = r'[Ee]ntry[:\s]*\$?([\d.]+)'
    entry_match = re.search(entry_pattern, message)
    if entry_match:
        signal["entry_price"] = float(entry_match.group(1))
    
    # Take profit targets
    tp_pattern = r'TP\d*[:\s]*\$?([\d.]+)'
    tps = re.findall(tp_pattern, message)
    if tps:
        signal["take_profits"] = tps
    
    return signal

def save_signal(signal: dict):
    """Save signal to file"""
    if "token_address" not in signal:
        return
    
    symbol = signal.get("token_address", "unknown")[:8]
    filename = SIGNALS_DIR / f"gmgn_{symbol}_{int(datetime.utcnow().timestamp())}.json"
    
    with open(filename, 'w') as f:
        json.dump(signal, f, indent=2)
    
    print(f"📡 GMGN Signal: {signal.get('action')} {symbol} {signal.get('amount_sol', '')}SOL")

async def main():
    print("🎯 GMGN Monitor Starting...")
    print(f"   Channel: GMGN.AI ({GMGN_CHANNEL})")
    
    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.start()
    
    print("✅ Connected to Telegram")
    
    @client.on(NewMessage(chats=GMGN_CHANNEL))
    async def handle_message(event):
        message = event.message.message or ""
        
        # Only process signals
        if any(kw in message.upper() for kw in ['BUY', 'SELL', 'SOL', 'ENTRY', 'TP']):
            signal = parse_gmgn_signal(message)
            if signal.get('action') and signal.get('token_address'):
                save_signal(signal)
                print(f"   💬 {message[:100]}...")
    
    print("👂 Listening for GMGN signals... (Ctrl+C to stop)")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())