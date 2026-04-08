#!/usr/bin/env python3
"""
GMGN Signal Buyer - Acts directly on GMGN signals that pass our filters
Scans the signals directory instead of relying on DexScreener's noisy endpoint
"""
import requests, json, time
from datetime import datetime
from pathlib import Path
from itertools import islice
from trading_constants import (
    MIN_MCAP, MAX_MCAP, MIN_VOLUME, POSITION_SIZE, EXIT_PLAN_TEXT,
    MIN_BS_RATIO, MIN_HOLDERS, MIN_GMGN_SCORE, MAX_OPEN_POSITIONS, SIM_RESET_TIMESTAMP,
    GMGN_VOL_MCAP_MIN
)

import gmgn_api_scorer
import gmgn_signal_scorer
import send_alert

TRADES_FILE = Path("/root/Dex-trading-bot/trades/sim_trades.jsonl")
SIGNALS_DIR = Path("/root/Dex-trading-bot/signals")
MIN_GMGN_SCORE = 50  # Only buy high quality signals

def get_token_market_data(ca: str):
    """Get full market data from DexScreener for a specific token"""
    try:
        r = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{ca}", timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        pairs = data.get('pairs', [])
        if not pairs:
            return None
        # Get best pair by liquidity
        best = max(pairs, key=lambda x: x.get('liquidity', {}).get('usd', 0))
        return best
    except:
        return None

def should_buy_from_signal(sig: dict, market: dict) -> tuple:
    """Check if a GMGN signal passes our buy criteria. Returns (should_buy, reasons)"""
    reasons_why_not = []
    
    # Get market data
    mcap = market.get('fdv', 0) or 0
    v = market.get('volume', {}).get('h24', 0) or 0
    v5 = market.get('volume', {}).get('m5', 0) or 0
    dex = market.get('dexId', '')
    buys = market.get('txns', {}).get('h24', {}).get('buys', 0) or 0
    sells = market.get('txns', {}).get('h24', {}).get('sells', 0) or 1
    bs = buys / sells if sells > 0 else 0
    holders = market.get('holders', 0) or 0
    
    # Check pump.fun
    if dex not in ['pumpfun', 'pumpswap']:
        reasons_why_not.append(f"not pumpfun/pumpswap ({dex})")
    
    # === PULLBACK DETECTION (Chris's insight) ===
    # Buy AFTER the first pump + dump cycle, not during the pump
    # Sweet spot: price up 5-40% in 5min (showing momentum) but NOT at peak
    # If 5min change > 50%, we caught the top - SKIP
    # If 5min change negative but > -20%, pullback entry is GOOD
    chg5 = market.get('priceChange', {}).get('m5', 0) or 0
    if chg5 > 50:
        reasons_why_not.append(f"5min pump {chg5:+.0f}% too hot (chasing top)")
        return False, reasons_why_not  # Hard skip - too late
    if chg5 < -30:
        reasons_why_not.append(f"5min dump {chg5:+.0f}% (falling knife)")
        return False, reasons_why_not  # Hard skip - might keep dumping
    # chg5 between -30 and 50 is acceptable for buying
    if chg5 > 5 and chg5 <= 50:
        reasons_why_not.append(f"5min {chg5:+.0f}% momentum zone (ideal entry window)")
    elif chg5 >= 0 and chg5 <= 5:
        reasons_why_not.append(f"5min {chg5:+.0f}% no momentum yet")
    
    # Mcap check
    if mcap < MIN_MCAP:
        reasons_why_not.append(f"mcap low (${mcap:,.0f})")
    if mcap > MAX_MCAP:
        reasons_why_not.append(f"mcap high (${mcap:,.0f})")
    
    # Volume check
    if v < MIN_VOLUME:
        reasons_why_not.append(f"vol low (${v:,.0f})")
    
    # 5min volume
    if v5 > 0 and v5 < MIN_5MIN_VOLUME:
        reasons_why_not.append(f"5min vol low (${v5:,.0f})")
    
    # Buy/sell ratio
    if bs < MIN_BS_RATIO:
        reasons_why_not.append(f"bs low ({bs:.1f})")
    
    # Holders
    if holders > 0 and holders < MIN_HOLDERS:
        reasons_why_not.append(f"holders low ({holders})")
    
    # Blacklist check
    sym = sig.get('symbol', '')
    if sym in TICKER_BLACKLIST:
        reasons_why_not.append(f"blacklisted ({sym})")
    
    # Re-entry check
    ca = sig.get('ca', '')
    if ca:
        with open(TRADES_FILE) as f:
            existing = [json.loads(l) for l in f]
        
        recently_closed = False
        for t in existing:
            if t.get('token_address') == ca and t.get('exit_reason') in ['STOP_AUTO', 'MANUAL_CLOSE', 'TP1_AUTO', 'TP2']:
                from datetime import datetime as dt
                closed = t.get('closed_at', '')
                if closed:
                    try:
                        closed_ts = dt.fromisoformat(closed.replace('Z', '+00:00'))
                        age = (dt.utcnow() - closed_ts.replace(tzinfo=None)).total_seconds() / 60
                        if age < REENTRY_LOCKOUT_MINUTES:
                            # Check if strong enough to override
                            gmgn_score = sig.get('gmgn_score', 0)
                            if not (bs >= REENTRY_BS_THRESHOLD and gmgn_score >= 70):
                                recently_closed = True
                                break
                    except:
                        pass
        
        if recently_closed:
            reasons_why_not.append("recently closed (lockout)")
    
    # GMGN score check
    gmgn_score = sig.get('gmgn_score', 0)
    if gmgn_score < MIN_GMGN_SCORE:
        reasons_why_not.append(f"GMGN score low ({gmgn_score})")
    
    should = len(reasons_why_not) == 0
    return should, reasons_why_not

def check_and_buy():
    """Main loop - check recent GMGN signals and buy if they pass criteria"""
    print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] GMGN Buyer scanning...")
    
    # Check max open positions
    try:
        with open(TRADES_FILE) as f:
            all_trades = [json.loads(l) for l in f]
        reset = SIM_RESET_TIMESTAMP
        open_pos = [t for t in all_trades if t.get('opened_at','') > reset and not t.get('closed_at') and t.get('status') != 'closed']
        if len(open_pos) >= MAX_OPEN_POSITIONS:
            print(f"⏳ Max open positions ({MAX_OPEN_POSITIONS}) reached, skipping GMGN scan")
            return
    except:
        pass
    
    # Get recent GMGN signals (last 50)
    signal_files = sorted(SIGNALS_DIR.glob('gmgn_*.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:50]
    
    # Already tracking what we own
    with open(TRADES_FILE) as f:
        existing = [json.loads(l) for l in f]
    owned = {t['token_address'] for t in existing if t.get('status') in ['open', 'open_partial']}
    
    bought_count = 0
    
    for sf in signal_files:
        try:
            sig = json.load(open(sf))
            ca = sig.get('ca', '')
            sym = sig.get('symbol', '')
            
            if not ca or not sym:
                continue
            
            # Skip if already owned
            if ca in owned:
                continue
            
            # Skip if blacklisted
            if sym in TICKER_BLACKLIST:
                continue
            
            # Get market data from DexScreener
            market = get_token_market_data(ca)
            if not market:
                continue
            
            should_buy, reasons = should_buy_from_signal(sig, market)
            
            if should_buy:
                mcap = market.get('fdv', 0) or 0
                liq = market.get('liquidity', {}).get('usd', 0) or 0
                
                # Get GMGN API data for rich scoring
                gmgn_data = gmgn_api_scorer.get_gmgn_token_data(ca)
                gmgn_sec = gmgn_api_scorer.get_gmgn_security(ca)
                api_score_result = gmgn_api_scorer.score_with_gmgn_api(sig, gmgn_data, gmgn_sec)
                api_score = api_score_result['score']
                
                if api_score < MIN_GMGN_API_SCORE:
                    print(f"  ❌ {sym}: GMGN API score {api_score}/100 < {MIN_GMGN_API_SCORE}")
                    continue
                
                print(f"\n✅ BUY SIGNAL: {sym}")
                print(f"   Mcap: ${mcap:,.0f} | Liq: ${liq:,.0f} | GMGN API Score: {api_score}/100")
                print(f"   Holders: {api_score_result['gmgn_holders']} | Top10: {api_score_result['gmgn_top10_pct']:.1f}% | CreatorTokens: {api_score_result['gmgn_creator_count']}")
                print(f"   Action: {sig.get('action')} | Smart: {api_score_result['gmgn_smart_wallets']} | KOL: {api_score_result['gmgn_renowned_wallets']}")
                print(f"   Score breakdown: {api_score_result['breakdown']}")
                
                # Execute simulated buy
                now = datetime.utcnow().isoformat()
                
                # Record trade
                trade = {
                    'token': sym,
                    'token_address': ca,
                    'pair_address': market.get('pairAddress', ca),
                    'source': 'gmgn_api_buyer',
                    'action': 'BUY',
                    'opened_at': now,
                    'amount_sol': 0.10 if sig.get('action') == 'KOL_BUY' else 0.05,
                    'entry_mcap': int(mcap),
                    'entry_price': market.get('priceUsd', 0),
                    'entry_liquidity': int(liq),
                    'status': 'open',
                    'entry_reason': sig.get('action', 'GMGN'),
                    'gmgn_score': api_score,
                    'gmgn_api_base_score': api_score_result['base_score'],
                    'gmgn_action': sig.get('action', ''),
                    'gmgn_holders': api_score_result['gmgn_holders'],
                    'gmgn_top10_pct': api_score_result['gmgn_top10_pct'],
                    'gmgn_creator_count': api_score_result['gmgn_creator_count'],
                    'gmgn_bot_degen_rate': api_score_result['gmgn_bot_degen_rate'],
                    'gmgn_smart_wallets': api_score_result['gmgn_smart_wallets'],
                    'gmgn_renowned_wallets': api_score_result['gmgn_renowned_wallets'],
                }
                
                with open(TRADES_FILE, 'a') as f:
                    f.write(json.dumps(trade) + '\n')
                
                # Send alert
                send_buy_alert(trade, market)
                
                owned.add(ca)  # Don't buy twice in same scan
                bought_count += 1
                
            else:
                # Log why not (for learning)
                if reasons and sym not in ['', '?']:
                    pass  # Silently skip failed checks
                    
        except Exception as e:
            pass
    
    if bought_count == 0:
        print(f"  No new signals passed filters this scan")
    
    return bought_count

def send_buy_alert(trade, market):
    """Send buy alert to Telegram"""
    import urllib.request, urllib.parse
    
    sym = trade['token']
    ca = trade['token_address']
    entry = trade['entry_mcap']
    gmgn_score = trade.get('gmgn_score', 0)
    action = trade.get('gmgn_action', '')
    holders = trade.get('gmgn_holders', 0)
    lp_burnt = trade.get('gmgn_lp_burnt', False)
    
    liq = market.get('liquidity', {}).get('usd', 0) or 0
    
    # Use amount from trade record (0.10 for KOL_BUY, 0.05 for others)
    amt_sol = trade.get('amount_sol', POSITION_SIZE)
    
    msg = f"""✅ BUY EXECUTED | {datetime.utcnow().strftime('%H:%M UTC')}
━━━━━━━━━━━━━━━
💰 {sym}

📍 Entry MC: ${entry:,}
💵 Amount: {amt_sol} SOL
🏆 GMGN Score: {gmgn_score}/100 ({action})
📊 Holders: {holders} | LP Burnt: {lp_burnt}
💧 Liquidity: ${liq:,.0f}

🔗 https://dexscreener.com/solana/{ca}
🥧 https://pump.fun/{ca}

{EXIT_PLAN_TEXT}"""
    
    try:
        url = "https://api.telegram.org/bot8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg/sendMessage"
        data = {"chat_id": "6402511249", "text": msg, "parse_mode": "HTML"}
        req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode())
        urllib.request.urlopen(req, timeout=10)
    except:
        pass

def main():
    print("GMGN Signal Buyer starting...")
    print(f"Filters: Mcap ${MIN_MCAP:,}-${MAX_MCAP:,} | Vol ${MIN_VOLUME:,}+ | BS {MIN_BS_RATIO}+ | Holders {MIN_HOLDERS}+ | GMGN Score {MIN_GMGN_SCORE}+")
    
    while True:
        try:
            check_and_buy()
        except Exception as e:
            print(f"Error: {e}")
        
        time.sleep(120)  # Scan every 60 seconds

if __name__ == "__main__":
    main()
