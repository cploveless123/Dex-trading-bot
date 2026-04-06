#!/usr/bin/env python3
"""
Telegram Re-auth Script
"""
import asyncio
import os
from pathlib import Path
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from dotenv import load_dotenv

# Load config
dotenv_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path)

SESSION_FILE = "/root/Dex-trading-bot/gmgn_monitor.session"
API_ID = 30571469
API_HASH = "85d1c3567f4182f4e4a88334ec04b935"
PHONE = "+19894393061"

async def reauth():
    print("🔐 Telegram Re-auth")
    print(f"Session: {SESSION_FILE}")
    print(f"API ID: {API_ID}")
    print(f"Phone: {PHONE}")
    
    if not API_ID or not API_HASH or not PHONE:
        print("Missing TELEGRAM_API_ID, TELEGRAM_API_HASH, or TELEGRAM_PHONE in .env")
        return
    
    # Remove old session
    if Path(SESSION_FILE).exists():
        os.remove(SESSION_FILE)
        print("Removed old session")
    
    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    await client.connect()
    
    print(f"Sending code to {PHONE}...")
    await client.send_code_request(PHONE)
    
    code = input("Enter code from Telegram: ")
    
    try:
        await client.sign_in(PHONE, code)
        print("✅ Success! Connected to Telegram")
    except SessionPasswordNeededError:
        password = input("Enter 2FA password: ")
        await client.sign_in(password=password)
        print("✅ Success! Connected to Telegram")
    except Exception as e:
        print(f"Error: {e}")
        return
    
    # Verify connection
    me = await client.get_me()
    print(f"Logged in as: {me.first_name} (@{me.username})")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(reauth())