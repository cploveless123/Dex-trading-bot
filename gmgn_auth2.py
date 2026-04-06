#!/usr/bin/env python3
"""
GMGN Auth with code - Login with phone + code
"""
import asyncio
from telethon import TelegramClient

phone = "19894393061"

async def main():
    print("Starting auth...")
    client = TelegramClient('/root/Dex-trading-bot/gmgn_fresh.session', 30571469, '85d1c3567f4182f4e4a88334ec04b935')
    
    await client.start(phone)
    print("Code sent!")
    
    # Wait for code input
    code = input("Enter code: ")
    
    await client.sign_in(phone, code)
    me = await client.get_me()
    print(f"✅ Logged in as: {me.username} ({me.id})")
    await client.disconnect()

asyncio.run(main())