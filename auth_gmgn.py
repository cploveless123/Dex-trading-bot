#!/usr/bin/env python3
"""
GMGN Direct Auth - Single shot
"""
import asyncio
from telethon import TelegramClient

async def main():
    client = TelegramClient('/root/Dex-trading-bot/gmgn.session', 30571469, '85d1c3567f4182f4e4a88334ec04b935')
    await client.start('+19894393061')
    print("✅ Auth complete!")
    me = await client.get_me()
    print(f"Logged in as: {me.username}")
    await client.disconnect()

asyncio.run(main())