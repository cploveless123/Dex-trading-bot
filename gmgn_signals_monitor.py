#!/usr/bin/env python3
"""
GMGN Featured Signals Monitor
Listens to @gmgnsignals channel for trading signals
"""
import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from telethon import TelegramClient
from telethon.events import NewMessage

# Config
SESSION = "/root/.openclaw/workspace/trading-bot/gmgn_monitor.session"
API_ID = 30571469
API_HASH = "85d1c3567f4182f4e4a88334ec04b935"
GMGN_CHANNEL = 2202241417  # GMGN Featured Signals(Lv2) - SOL

SIGNALS_DIR = Path(__file__).parent.parent / "signals"
JOURNAL_FILE = Path(__file__).parent.parent / "trades" / "learning_journal.jsonl"

def parse_gmgn_signal(message: str) -> dict:
    """Parse GMGN signal from message text"""
    signal = {
        "source": "gmgn_featured",
        "raw": message,
        "parsed_at": datetime.utcnow().isoformat()
    }
    
    # Token CA (contract address) - base58 Solana format
    ca_pattern = r'CA:\s*\n*`?([1-9A-HJ-NP-Za-km-z]{32,44})`?'
    ca_match = re.search(ca_pattern, message.replace('\n', ''))
    if ca_match:
        signal["token_address"] = ca_match.group(1)
    
    # Symbol/name - find after $ or the main token name
    symbol_pattern = r'\*\*\$?([A-Z]+)\*\*|([A-Z]{2,15})\s*\('
    symbol_match = re.search(symbol_pattern, message)
    if symbol_match:
        signal["symbol"] = symbol_match.group(1) or symbol_match.group(2)
    
    # Action - KOL Buy, Pump, KOTH, etc.
    if 'KOL Buy' in message or '🟢🟢' in message:
        signal["action"] = "KOL_BUY"
    if 'KOTH' in message:
        signal["action"] = "KOTH"
    if 'PUMP' in message:
        signal["action"] = "PUMP"
    if 'Sell' in message or '🔴' in message:
        signal["action"] = "SELL"
    
    # Price change
    change_pattern = r'📈[^:]*:\s*\*\*([\d.]+)%\*\*'
    change_match = re.search(change_pattern, message)
    if change_match:
        signal["change_pct"] = float(change_match.group(1))
    
    # FDV/Mcap
    mcap_pattern = r'FDV[:\s]+\$?([\d.]+)([KMB])?'
    mcap_match = re.search(mcap_pattern, message)
    if mcap_match:
        value = float(mcap_match.group(1))
        unit = mcap_match.group(2)
        if unit == 'K':
            value *= 1000
        elif unit == 'M':
            value *= 1000000
        elif unit == 'B':
            value *= 1000000000
        signal["mcap"] = value
    
    # Liquidity
    liq_pattern = r'Liq[:\s]+\$?([\d.]+)([KMB])?'
    liq_match = re.search(liq_pattern, message)
    if liq_match:
        value = float(liq_match.group(1))
        unit = liq_match.group(2)
        if unit == 'K':
            value *= 1000
        elif unit == 'M':
            value *= 1000000
        signal["liquidity"] = value
    
    # DexScreener link
    dex_link = re.search(r'https://dexscreener\.com/solana/[1-9A-HJ-NP-Za-km-z]+', message)
    if dex_link:
        signal["dex_link"] = dex_link.group(0)
    
    return signal

def save_signal(signal: dict):
    """Save signal to file and log to journal"""
    if not signal.get("token_address"):
        return
    
    symbol = signal.get("symbol", "UNKNOWN")
    filename = SIGNALS_DIR / f"gmgn_{symbol}_{int(datetime.utcnow().timestamp())}.json"
    
    with open(filename, 'w') as f:
        json.dump(signal, f, indent=2)
    
    # Log to learning journal
    entry = {
        "type": "gmgn_signal",
        "timestamp": datetime.utcnow().isoformat(),
        "data": signal
    }
    JOURNAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(JOURNAL_FILE, 'a') as f:
        f.write(json.dumps(entry) + '\n')
    
    action = signal.get("action", "SIGNAL")
    change = signal.get("change_pct", 0)
    mcap = signal.get("mcap", 0)
    liq = signal.get("liquidity", 0)
    
    print(f"📡 GMGN: [{action}] {symbol} | +{change}% | FDV: ${mcap:,.0f} | Liq: ${liq:,.0f}")
    print(f"   CA: {signal.get('token_address', '')[:16]}...")

async def main():
    print("🎯 GMGN Featured Signals Monitor Starting...")
    print(f"   Channel: {GMGN_CHANNEL}")
    
    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.start()
    
    print("✅ Connected to Telegram")
    
    @client.on(NewMessage(chats=GMGN_CHANNEL))
    async def handle_message(event):
        message = event.message.message or ""
        
        # Parse any message that looks like a signal
        if any(kw in message for kw in ['CA:', 'KOL', 'PUMP', 'KOTH', 'FDV', 'Liq']):
            signal = parse_gmgn_signal(message)
            if signal.get("token_address"):
                save_signal(signal)
    
    print("👂 Listening for GMGN signals... (Ctrl+C to stop)")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())