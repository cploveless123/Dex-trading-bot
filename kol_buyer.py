#!/usr/bin/env python3
"""
KOL Buyer - Monitors gmgn-cli track kol for multi-KOL buys
Strongest signal: when 3+ different KOL wallets buy the same token
"""
import requests, json, subprocess, time
from datetime import datetime
from collections import Counter
from pathlib import Path
from trading_constants import MIN_MCAP, MAX_MCAP, MIN_VOLUME, MIN_HOLDERS, POSITION_SIZE
MIN_BS_RATIO = 1.5
MIN_5MIN_VOLUME = 1000
import gmgn_api_scorer

BOT_TOKEN = "8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg"
CHAT_ID = "6402511249"
TRADES_FILE = Path("/root/Dex-trading-bot/trades/sim_trades.jsonl")
SIGNALS_DIR = Path("/root/Dex-trading-bot/signals")
MIN_KOL_COUNT = 3  # Minimum KOLs buying same token to act
MIN_GMGN_SCORE = 50

BLACKLIST_TAGS = {'wash_trader', 'washbuy', 'bot'}  # Skip these KOLs

def get_kol_trades(limit=100):
    """Fetch latest KOL buy trades from gmgn-cli"""
    try:
        result = subprocess.run(
            ['gmgn-cli', 'track', 'kol', '--chain', 'sol', '--limit', str(limit), '--side', 'buy', '--raw'],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return json.loads(result.stdout).get('list', [])
    except:
        pass
    return []

def get_token_market_data(ca):
    """Get DexScreener market data for token"""
    try:
        r = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{ca}", timeout=8)
        if r.status_code == 200:
            data = r.json()
            pairs = data.get('pairs', [])
            if pairs:
                return max(pairs, key=lambda x: x.get('liquidity', {}).get('usd', 0))
    except:
        pass
    return None

def send_alert(msg):
    """Send Telegram alert"""
    import urllib.parse
    encoded = urllib.parse.urlencode({'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'HTML'})
    subprocess.run(
        ['curl', '-s', '-X', 'POST',
         f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
         '-d', encoded],
        capture_output=True, timeout=10
    )

def main():
    print("KOL Buyer starting...")
    print(f"Filters: Mcap ${MIN_MCAP:,}-${MAX_MCAP:,} | Vol ${MIN_VOLUME:,}+ | 5min ${MIN_5MIN_VOLUME:,}+ | BS {MIN_BS_RATIO}+ | Holders {MIN_HOLDERS}+")
    print(f"Signal: {MIN_KOL_COUNT}+ KOLs buying same token + GMGN score {MIN_GMGN_SCORE}+\n")
    
    last_scan = {}
    
    while True:
        try:
            trades = get_kol_trades(200)
            if not trades:
                print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] No KOL trades found")
                time.sleep(60)
                continue
            
            # Count KOLs per token (by CA)
            kol_by_token = {}
            for t in trades:
                ca = t.get('base_address', '')
                sym = t.get('base_token', {}).get('symbol', '')
                info = t.get('maker_info', {})
                tags = set(info.get('tags', []))
                wallet = t.get('maker', '')
                tw = info.get('twitter_username', '') or info.get('name', 'unknown')
                sol = float(t.get('quote_amount', 0))
                
                # Skip blacklisted KOLs
                if tags & BLACKLIST_TAGS:
                    continue
                
                if not ca or not sym:
                    continue
                
                if ca not in kol_by_token:
                    kol_by_token[ca] = {
                        'sym': sym, 'ca': ca,
                        'kol_wallets': {},
                        'total_sol': 0,
                        'txs': 0
                    }
                
                # Track unique KOLs
                if wallet not in kol_by_token[ca]['kol_wallets']:
                    kol_by_token[ca]['kol_wallets'][wallet] = {
                        'twitter': tw, 'tags': list(tags), 'sol': 0
                    }
                kol_by_token[ca]['kol_wallets'][wallet]['sol'] += sol
                kol_by_token[ca]['total_sol'] += sol
                kol_by_token[ca]['txs'] += 1
            
            # Find tokens with multiple KOLs
            multi_kol = {ca: data for ca, data in kol_by_token.items() 
                        if len(data['kol_wallets']) >= MIN_KOL_COUNT}
            
            if multi_kol:
                print(f"\n[{datetime.utcnow().strftime('%H:%M:%S')}] Found {len(multi_kol)} tokens with {MIN_KOL_COUNT}+ KOLs\n")
            
            # Check owned
            with open(TRADES_FILE) as f:
                owned = {t['token_address'] for t in [json.loads(l) for l in f] 
                        if t.get('status') in ['open', 'open_partial']}
            
            for ca, data in sorted(multi_kol.items(), key=lambda x: len(x[1]['kol_wallets']), reverse=True):
                if ca in owned:
                    continue
                
                sym = data['sym']
                kol_count = len(data['kol_wallets'])
                kol_names = [v['twitter'] for v in list(data['kol_wallets'].values())[:5]]
                
                # Get market data
                market = get_token_market_data(ca)
                if not market:
                    continue
                
                mcap = market.get('fdv', 0) or 0
                vol24 = market.get('volume', {}).get('h24', 0) or 0
                vol5 = market.get('volume', {}).get('m5', 0) or 0
                buys = market.get('txns', {}).get('h24', {}).get('buys', 0) or 0
                sells = market.get('txns', {}).get('h24', {}).get('sells', 0) or 1
                bs = buys / sells
                dex = market.get('dexId', '')
                holders = market.get('holders', 0) or 0
                
                # Apply filters
                if dex != 'pumpfun':
                    continue
                if not (MIN_MCAP <= mcap <= MAX_MCAP):
                    continue
                if vol24 < MIN_VOLUME:
                    continue
                if vol5 < MIN_5MIN_VOLUME:
                    continue
                if bs < MIN_BS_RATIO:
                    continue
                if holders > 0 and holders < MIN_HOLDERS:
                    continue
                
                # GMGN API score
                sig = {'action': 'KOL_BUY', 'symbol': sym, 'ca': ca}
                gmgn_data = gmgn_api_scorer.get_gmgn_token_data(ca)
                sec_data = gmgn_api_scorer.get_gmgn_security(ca)
                
                if not gmgn_data:
                    continue
                
                score_result = gmgn_api_scorer.score_with_gmgn_api(sig, gmgn_data, sec_data, vol24, mcap)
                score = score_result['score']
                
                if score < MIN_GMGN_SCORE:
                    print(f"  ❌ {sym}: {kol_count} KOLs but score {score} < {MIN_GMGN_SCORE}")
                    continue
                
                # BUY!
                print(f"\n🚀 KOL BUY: {sym} — {kol_count} KOLs!")
                print(f"   Mcap: ${mcap:,.0f} | vol5m=${vol5:,.0f} | bs={bs:.1f}")
                print(f"   GMGN Score: {score}/100")
                print(f"   KOLs: {kol_names}")
                
                trade = {
                    'token': sym, 'token_address': ca, 'pair_address': market.get('pairAddress', ca),
                    'source': 'kol_buyer', 'action': 'BUY', 'opened_at': datetime.utcnow().isoformat(),
                    'entry_mcap': int(mcap), 'entry_liquidity': 0, 'status': 'open',
                    'entry_reason': f'KOL_{kol_count}WALLET',
                    'gmgn_score': score,
                    'gmgn_api_base_score': score_result['base_score'],
                    'gmgn_action': 'KOL_BUY',
                    'gmgn_holders': score_result['gmgn_holders'],
                    'gmgn_top10_pct': score_result['gmgn_top10_pct'],
                    'gmgn_creator_count': score_result['gmgn_creator_count'],
                    'gmgn_bot_degen_rate': score_result['gmgn_bot_degen_rate'],
                    'gmgn_smart_wallets': score_result['gmgn_smart_wallets'],
                    'gmgn_renowned_wallets': score_result['gmgn_renowned_wallets'],
                    'gmgn_vol_mcap_ratio': score_result['vol_mcap_ratio'],
                    'kol_count': kol_count,
                    'kol_wallets': list(data['kol_wallets'].keys())[:5],
                }
                
                with open(TRADES_FILE, 'a') as f:
                    f.write(json.dumps(trade) + '\n')
                
                owned.add(ca)
                
                EXIT_PLAN = f"""🎯 Exit Plan:
+45% → Sell initial investment (~74% of position)
📊 Trailing stop: sell remaining if 30% drop from peak
⚠️ Stop: -30%"""
                
                msg = f"""✅ KOL BUY | {datetime.utcnow().strftime('%H:%M UTC')}
━━━━━━━━━━━━━━━
💰 <b>{sym}</b>

📍 Entry MC: ${int(mcap):,}
💵 Amount: {POSITION_SIZE} SOL
🏆 GMGN Score: {score}/100
📊 Vol/MCap: {score_result['vol_mcap_ratio']:.1f}x
📊 KOL Count: {kol_count} wallets
📊 Holders: {score_result['gmgn_holders']} | Top10: {score_result['gmgn_top10_pct']:.1f}%
📊 BotDegen: {score_result['gmgn_bot_degen_rate']:.1f}%

🔗 https://dexscreener.com/solana/{ca}
🥧 https://pump.fun/{ca}

{EXIT_PLAN}"""
                
                send_alert(msg)
                print(f"   ✅ BOUGHT & ALERTED!")
            
            time.sleep(60)  # Scan every minute
            
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(30)

if __name__ == '__main__':
    main()
