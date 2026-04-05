#!/usr/bin/env python3
"""
Telegram GMGN Signal Monitor
Connects to Telegram group and parses GMGN signals
"""
import asyncio
import json
import os
import re
from datetime import datetime
from pathlib import Path

from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError


# Configuration
SESSION_FILE = "gmgn_monitor.session"
SIGNALS_DIR = Path(__file__).parent.parent / "signals"

from dotenv import load_dotenv
from pathlib import Path

# Load environment
load_dotenv(Path(__file__).parent.parent / ".env")

# Get from environment or ask user
API_ID = os.getenv("TELEGRAM_API_ID", "")
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
PHONE = os.getenv("TELEGRAM_PHONE", "")
GMGN_CHANNEL_ID = os.getenv("GMGN_CHANNEL_ID", "")


class GMGNMonitor:
    def __init__(self):
        self.client = None
        self.signals_parsed = 0
        
    async def connect(self):
        """Connect to Telegram"""
        print("📱 Connecting to Telegram...")
        
        self.client = TelegramClient(
            SESSION_FILE,
            API_ID,
            API_HASH
        )
        
        await self.client.connect()
        
        if not await self.client.is_user_authorized():
            print("🔐 Need authorization...")
            await self.client.send_code_request(PHONE)
            code = input("Enter the code: ")
            try:
                await self.client.sign_in(PHONE, code)
            except SessionPasswordNeededError:
                password = input("Enter 2FA password: ")
                await self.client.sign_in(password=password)
        
        print("✅ Connected!")
        
    async def parse_signal(self, message: str) -> dict:
        """Parse GMGN signal from message text"""
        signal = {
            "raw": message,
            "parsed_at": datetime.utcnow().isoformat()
        }
        
        # Look for token address (base58 Solana address)
        token_pattern = r'[1-9A-HJ-NP-Za-km-z]{32,44}'
        tokens = re.findall(token_pattern, message)
        if tokens:
            signal["token_address"] = tokens[0]
        
        # Look for action (BUY/SELL)
        if re.search(r'\bBUY\b', message, re.IGNORECASE):
            signal["action"] = "BUY"
        elif re.search(r'\bSELL\b', message, re.IGNORECASE):
            signal["action"] = "SELL"
            
        # Look for amount/percentage
        amount_pattern = r'(\d+(?:\.\d+)?)\s*(%|SOL|USD)'
        amounts = re.findall(amount_pattern, message, re.IGNORECASE)
        if amounts:
            signal["amount"] = amounts[0][0]
            signal["amount_type"] = amounts[0][1]
            
        # Look for price targets
        tp_pattern = r'TP\d*[:\s]*(\d+(?:\.\d+)?)'
        tps = re.findall(tp_pattern, message)
        if tps:
            signal["take_profits"] = tps
            
        return signal
    
    async def save_signal(self, signal: dict):
        """Save parsed signal to file"""
        if "token_address" not in signal:
            return
            
        filename = SIGNALS_DIR / f"gmgn_{signal['token_address'][:8]}_{int(datetime.utcnow().timestamp())}.json"
        
        with open(filename, 'w') as f:
            json.dump(signal, f, indent=2)
        
        print(f"📡 Signal saved: {signal.get('action')} {signal.get('token_address', 'unknown')[:16]}...")
        self.signals_parsed += 1
        
    async def start_monitoring(self, channel_id: str):
        """Start monitoring a channel for signals"""
        print(f"🎯 Monitoring channel: {channel_id}")
        
        @self.client.on(events.NewMessage(chats=channel_id))
        async def handle_new_message(event):
            message = event.message.message or ""
            
            # Only process messages that look like GMGN signals
            if any(keyword in message.upper() for keyword in ['BUY', 'SELL', 'TOKEN', 'SOL', 'ENTRY']):
                print(f"\n📩 New message: {message[:100]}...")
                signal = await self.parse_signal(message)
                await self.save_signal(signal)
        
        print("👂 Listening for signals... (Ctrl+C to stop)")
        
        # Keep running
        await self.client.run_until_disconnected()


async def main():
    # Check configuration
    if not API_ID or not API_HASH:
        print("❌ Missing configuration!")
        print("\nSet these environment variables:")
        print("  export TELEGRAM_API_ID=your_api_id")
        print("  export TELEGRAM_API_HASH=your_api_hash")
        print("  export TELEGRAM_PHONE=+1234567890")
        print("  export GMGN_CHANNEL_ID=@your_channel")
        print("\nGet API keys from https://my.telegram.org/apps")
        return
    
    monitor = GMGNMonitor()
    await monitor.connect()
    
    if GMGN_CHANNEL_ID:
        await monitor.start_monitoring(GMGN_CHANNEL_ID)
    else:
        # List available chats to help user find the channel
        print("\n📋 Available chats:")
        async for dialog in monitor.client.iter_dialog():
            if dialog.is_channel or dialog.is_group:
                print(f"  {dialog.id}: {dialog.name}")
        
        channel_id = input("\nEnter GMGN channel ID (or @username): ")
        await monitor.start_monitoring(channel_id)


if __name__ == "__main__":
    asyncio.run(main())