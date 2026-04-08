#!/usr/bin/env python3
"""
GMGN Signals Monitor - With DexScreener links
"""
import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from telethon import TelegramClient

SESSION = "/root/Dex-trading-bot/gmgn.session"
API_ID = 30571469
API_HASH = "85d1c3567f4182f4e4a88334ec04b935"
CHANNELS = [
    '@gmgnai',         # 💎GMGN Degen Group - Official
    '@gmgnsignals',    # GMGN Featured Signals (Lv2) - SOL
    '@gmgn_trading',   # Solana Trading
    '@pump_sol_alert', # Portal for Pump Alert Channel - GMGN
    '@solnewlp',       # Portal for Solana New Pool Channel - GMGN
    '@sollpburnt',     # Portal for Sol LP Burn - GMGN
    '@gmgn_degencalls', # 💎Portal for Degen Calls - GMGN
]
SIGNALS_DIR = Path("/root/Dex-trading-bot/signals")
JOURNAL_FILE = Path("/root/Dex-trading-bot/trades/learning_journal.jsonl")

def get_dexscreener_link(token_addr):
    """Generate DexScreener link for token"""
    if token_addr:
        return f"https://dexscreener.com/solana/{token_addr}"
    return ""

def format_gmgn_signal(sig: dict) -> str:
    """Format GMGN signal in Chris's exact style"""
    symbol = sig.get('symbol', 'UNKNOWN')
    token_addr = sig.get('token_address', '')
    action = sig.get('action', 'SIGNAL')
    change = sig.get('change_pct', 0)
    liquidity = sig.get('liquidity', 0)
    mcap = sig.get('mcap', 0)
    holders = sig.get('holders', 0)
    
    # Format liquidity
    if liquidity >= 1000000:
        liq_str = f"${liquidity/1000000:.1f}M"
    elif liquidity >= 1000:
        liq_str = f"${liquidity/1000:.1f}K"
    else:
        liq_str = f"${liquidity:.0f}"
    
    # Format mcap
    if mcap >= 1000000:
        mcap_str = f"${mcap/1000000:.2f}M"
    elif mcap >= 1000:
        mcap_str = f"${mcap/1000:.1f}K"
    else:
        mcap_str = f"${mcap:.0f}"
    
    change_str = f"+{change:.1f}%" if change >= 0 else f"{change:.1f}%"
    
    # Action emoji
    if action == 'KOL_BUY':
        emoji = '🏐'
        action_text = 'KOL BUY'
    elif action == 'PUMP':
        emoji = '💊'
        action_text = 'PUMP'
    elif action == 'KOTH':
        emoji = '👑'
        action_text = 'KOTH'
    else:
        emoji = '📡'
        action_text = 'SIGNAL'
    
    # Dex link
    dex_link = f"https://dexscreener.com/solana/{token_addr}" if token_addr else ""
    buy_cmd = f"/buy {token_addr} 0.1 on GMGN bot" if token_addr else ""
    
    return f"""🏐 GMGN ALERT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 {symbol} | {sig.get('source_channel', 'GMGN')}
🔗 CA: {token_addr}
📊 Signal: PRICE{change_str}

💎 FDV: {mcap_str}
💧 Liquidity: {liq_str}
👥 Holders: {holders}
🔗 {dex_link}

⚙️ Reply GO to execute (manually on GMGN)
⚙️ Or: {buy_cmd}"""

def parse_signal(text):
    signal = {'source': 'gmgn', 'raw': text, 'parsed_at': datetime.utcnow().isoformat()}
    
    # Token CA - multiple patterns to catch different formats
    ca_patterns = [
        r'CA:\s*\n*`?([1-9A-HJ-NP-Za-km-z]{32,44})',
        r'`([1-9A-HJ-NP-Za-km-z]{32,44})`',
        r'https://gmgn\.ai/sol/token/([1-9A-HJ-NP-Za-km-z]{32,44})'
    ]
    for pattern in ca_patterns:
        ca = re.search(pattern, text.replace('\n', ''))
        if ca:
            token_addr = ca.group(1)
            signal['token_address'] = token_addr
            signal['dexscreener_link'] = get_dexscreener_link(token_addr)
            break
    
    # Symbol - multiple patterns
    sym_patterns = [
        r'\*\*\$([A-Z0-9]{2,15})\*\*',  # **$SYMBOL**
        r'\*\*([A-Z][A-Z0-9]{1,10})\*\*',  # **SYMBOL**
        r'\*\*([a-zA-Z][a-zA-Z0-9]{2,15})\*\*',  # **Name**
        r'pump\.fun/([A-Za-z0-9]+)',  # pump.fun token
    ]
    for pattern in sym_patterns:
        sym = re.search(pattern, text)
        if sym:
            potential = sym.group(1).upper()
            # Filter out common false positives
            if potential not in ['PUMP', 'KOTH', 'CA', 'GMGN', 'SOL']:
                signal['symbol'] = potential[:10]
                break
    
    # Action - check emoji and text
    if 'KOL Buy' in text or '🟢🟢' in text or '🏐' in text:
        signal['action'] = 'KOL_BUY'
    elif 'KOTH' in text or '👑' in text:
        signal['action'] = 'KOTH'
    elif 'PUMP' in text or '💊' in text:
        signal['action'] = 'PUMP'
    
    # Change % - look for +number%
    chg = re.search(r'\+([\d.]+)%', text)
    if chg:
        signal['change_pct'] = float(chg.group(1))
    
    # Liquidity - look for $X.XM or $X.XK
    liq = re.search(r'\$?([\d.]+)([KMB])\s*(?:Liq|K)', text, re.IGNORECASE)
    if liq:
        val = float(liq.group(1))
        unit = liq.group(2).upper()
        if unit == 'K': val *= 1000
        elif unit == 'M': val *= 1000000
        elif unit == 'B': val *= 1000000000
        signal['liquidity'] = val
    
    # Also check for plain $X.XM or $X.XK anywhere
    liq2 = re.search(r'\$?([\d.]+)([KMB])', text)
    if liq2 and 'liquidity' not in signal:
        val = float(liq2.group(1))
        unit = liq2.group(2).upper()
        if unit == 'K': val *= 1000
        elif unit == 'M': val *= 1000000
        elif unit == 'B': val *= 1000000000
        if val > 1000:  # Only if looks like liquidity
            signal['liquidity'] = val
        signal['action'] = 'PUMP'
    
    # Change %
    chg = re.search(r'\+([\d.]+)%', text)
    if chg:
        signal['change_pct'] = float(chg.group(1))
    
    # Liquidity
    liq = re.search(r'Liq[:\s]+\$?([\d.]+)([KMB])?', text)
    if liq:
        val = float(liq.group(1))
        unit = liq.group(2)
        if unit == 'K': val *= 1000
        elif unit == 'M': val *= 1000000
        signal['liquidity'] = val
    
    # MCAP
    mcap = re.search(r'FDV[:\s]+\$?([\d.]+)([KMB])?', text)
    if mcap:
        val = float(mcap.group(1))
        unit = mcap.group(2)
        if unit == 'K': val *= 1000
        elif unit == 'M': val *= 1000000
        signal['mcap'] = val
    
    # Rug Detection - parse from GMGN raw text
    if 'NoMint' in text or '✅' in text:
        signal['no_mint'] = True
    if 'Blacklist' in text:
        signal['no_blacklist'] = True
    if 'Burnt' in text or '✅Burnt' in text:
        signal['lp_burnt'] = True
    
    # Rug probability (higher = riskier)
    rug_match = re.search(r'Rug Probability.*?:\s*\*\*(\d+\.?\d*)%', text)
    if rug_match:
        signal['rug_probability'] = float(rug_match.group(1))
    
    # Top holder percentage (higher = more centralized)
    top10_match = re.search(r'TOP\s*10:\s*\*\*(\d+\.?\d*)%', text)
    if top10_match:
        signal['top_10_pct'] = float(top10_match.group(1))
    
    # Holder count (low = risky)
    holder_match = re.search(r'Holder[s]?:\s*\*\*(\d+)', text)
    if holder_match:
        signal['holders'] = int(holder_match.group(1))
    
    # Dev wallet balance (high = risky)
    dev_bal_match = re.search(r'Balance SOL:\s*\*\*?(\d+\.?\d*)\s*SOL', text)
    if dev_bal_match:
        signal['dev_balance_sol'] = float(dev_bal_match.group(1))
    
    # Age (very new = risky)
    age_match = re.search(r'(?:Open|ago):\s*\*\*(\d+)([smh])', text)
    if age_match:
        val = int(age_match.group(1))
        unit = age_match.group(2)
        if unit == 's':
            signal['age_seconds'] = val
        elif unit == 'm':
            signal['age_minutes'] = val
        elif unit == 'h':
            signal['age_minutes'] = val * 60
    
    # Sniper indicators - bots buying heavily at launch
    tx_match = re.search(r'TXs:\s*\*\*(\d+)', text)
    if tx_match:
        signal['tx_count'] = int(tx_match.group(1))
    
    return signal

async def main():
    print("GMGN Monitor Starting")
    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.connect()
    
    entities = []
    for ch in CHANNELS:
        try:
            e = await client.get_entity(ch)
            entities.append(e)
            print(f"Watching: {e.title}")
        except Exception as ex:
            print(f"Failed to join {ch}: {ex}")
    
    if not entities:
        print("No channels joined!")
        await client.disconnect()
        return
    
    # Track last seen message IDs per channel
    last_ids = {str(e.id): None for e in entities}
    
    while True:
        try:
            for entity in entities:
                async for msg in client.iter_messages(entity, limit=5):
                    key = str(entity.id)
                    if msg.id != last_ids[key] and msg.text:
                        last_ids[key] = msg.id
                        
                        if any(kw in msg.text for kw in ['KOL', 'PUMP', 'KOTH', 'BUY', 'SNIPER']):
                            signal = parse_signal(msg.text)
                            signal['source_channel'] = entity.title
                            
                            if signal.get('token_address'):
                                symbol = signal.get('symbol', 'UNK')
                                fname = SIGNALS_DIR / f"gmgn_{symbol}_{msg.id}.json"
                                with open(fname, 'w') as f:
                                    json.dump(signal, f, indent=2)
                                
                                JOURNAL_FILE.parent.mkdir(parents=True, exist_ok=True)
                                with open(JOURNAL_FILE, 'a') as f:
                                    f.write(json.dumps({"type": "gmgn_signal", "timestamp": datetime.utcnow().isoformat(), "data": signal}) + '\n')
                                
                                formatted = format_gmgn_signal(signal)
                                print(f"\n{formatted}")
            
            await asyncio.sleep(15)
        except Exception as e:
            print(f"Error: {e}")
            await asyncio.sleep(5)
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())