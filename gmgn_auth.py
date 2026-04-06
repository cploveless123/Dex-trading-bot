#!/usr/bin/env python3
"""
GMGN Auth Helper - Just login and save session
"""
import asyncio
from telethon import TelegramClient

async def main():
    print("Starting auth...")
    client = TelegramClient('/root/Dex-trading-bot/gmgn_new.session', 30571469, '85d1c3567f4182f4e4a88334ec04b935')
    await client.start()
    me = await client.get_me()
    print(f"✅ Logged in as: {me.username} ({me.id})")
    await client.disconnect()

asyncio.run(main())