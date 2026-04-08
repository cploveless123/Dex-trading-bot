#!/usr/bin/env python3
"""
GMGN API Scorer - Uses GMGN API + DexScreener for rich token data
Fetches smart money, holder concentration, creator history, vol/mcap ratio
"""
import subprocess, json
import requests
from pathlib import Path

def get_dexscreener_vol(ca: str) -> tuple:
    """Get 24h volume and mcap from DexScreener, return (vol, mcap, ratio)"""
    try:
        r = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{ca}", timeout=8)
        if r.status_code == 200:
            data = r.json()
            pairs = data.get('pairs', [])
            if pairs:
                p = max(pairs, key=lambda x: x.get('liquidity', {}).get('usd', 0))
                mcap = p.get('fdv', 0) or 0
                vol = p.get('volume', {}).get('h24', 0) or 0
                ratio = vol/mcap if mcap > 0 else 0
                return vol, mcap, ratio
    except:
        pass
    return 0, 0, 0

def get_gmgn_token_data(ca: str) -> dict:
    """Fetch rich token data from GMGN API"""
    try:
        r = subprocess.run(
            ['gmgn-cli', 'token', 'info', '--chain', 'sol', '--address', ca],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode == 0:
            return json.loads(r.stdout)
    except:
        pass
    return {}

def get_gmgn_security(ca: str) -> dict:
    """Fetch security data from GMGN API"""
    try:
        r = subprocess.run(
            ['gmgn-cli', 'token', 'security', '--chain', 'sol', '--address', ca],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode == 0:
            return json.loads(r.stdout)
    except:
        pass
    return {}

def score_with_gmgn_api(sig: dict, gmgn_data: dict, security_data: dict, dex_vol: float = 0, dex_mcap: float = 0) -> dict:
    """Enhanced scoring using GMGN API data + DexScreener vol data - returns score + breakdown"""
    score = 0
    breakdown = {}
    
    # === LIQUIDITY (from GMGN API) ===
    liq = float(gmgn_data.get('liquidity', 0))
    if liq >= 50000: score += 25; breakdown['liq'] = '25 (50K+)'
    elif liq >= 30000: score += 20; breakdown['liq'] = '20 (30K+)'
    elif liq >= 15000: score += 15; breakdown['liq'] = '15 (15K+)'
    elif liq >= 5000: score += 10; breakdown['liq'] = '10 (5K+)'
    else: breakdown['liq'] = '0 (<5K)'
    
    # === HOLDERS ===
    holders = int(gmgn_data.get('holder_count', 0))
    if holders >= 200: score += 20; breakdown['holders'] = '20 (200+)'
    elif holders >= 100: score += 18; breakdown['holders'] = '18 (100+)'
    elif holders >= 50: score += 14; breakdown['holders'] = '14 (50+)'
    elif holders >= 20: score += 8; breakdown['holders'] = '8 (20+)'
    else: breakdown['holders'] = '0 (<20)'
    
    # === TOP 10 HOLDER CONCENTRATION ===
    stat = gmgn_data.get('stat', {})
    top10_rate = float(stat.get('top_10_holder_rate', 0))
    if top10_rate < 0.15: score += 15; breakdown['top10'] = '15 (<15%)'
    elif top10_rate < 0.25: score += 10; breakdown['top10'] = '10 (<25%)'
    elif top10_rate < 0.40: score += 5; breakdown['top10'] = '5 (<40%)'
    else: score += 0; breakdown['top10'] = '0 (40%+)'
    
    # === CREATOR HISTORY (serial creator = risky) ===
    creator_count = int(stat.get('creator_created_count', 0))
    if creator_count == 0: score += 10; breakdown['creator'] = '10 (no prior tokens)'
    elif creator_count <= 5: score += 7; breakdown['creator'] = '7 (1-5 tokens)'
    elif creator_count <= 50: score += 3; breakdown['creator'] = '3 (6-50 tokens)'
    else: score += 0; breakdown['creator'] = f'0 ({creator_count} tokens)'
    
    # === SMART MONEY (bot degen rate) ===
    bot_degen_rate = float(stat.get('bot_degen_rate', 0))
    if bot_degen_rate >= 0.15: score += 10; breakdown['botdegen'] = '10 (15%+)'
    elif bot_degen_rate >= 0.08: score += 7; breakdown['botdegen'] = '7 (8%+)'
    elif bot_degen_rate >= 0.03: score += 4; breakdown['botdegen'] = '4 (3%+)'
    else: breakdown['botdegen'] = '0 (<3%)'
    
    # === SECURITY ===
    if security_data.get('renounced_mint') and security_data.get('renounced_freeze_account'):
        score += 5; breakdown['renounced'] = '5 (both)'
    elif security_data.get('renounced_mint') or security_data.get('renounced_freeze_account'):
        score += 2; breakdown['renounced'] = '2 (one)'
    else: breakdown['renounced'] = '0 (neither)'
    
    if float(security_data.get('buy_tax', 1)) == 0 and float(security_data.get('sell_tax', 1)) == 0:
        score += 5; breakdown['tax'] = '5 (0% tax)'
    else: breakdown['tax'] = '0 (has tax)'
    
    # === WALLET TAGS ===
    wt = gmgn_data.get('wallet_tags_stat', {})
    smart = int(wt.get('smart_wallets', 0))
    renowned = int(wt.get('renowned_wallets', 0))
    if smart >= 5: score += 10; breakdown['smart'] = f'10 ({smart} smart)'
    elif smart >= 2: score += 6; breakdown['smart'] = f'6 ({smart} smart)'
    elif smart >= 1: score += 3; breakdown['smart'] = f'3 ({smart} smart)'
    else: breakdown['smart'] = '0 (no smart)'
    
    if renowned >= 3: score += 5; breakdown['kol'] = '5 (3+ KOL)'
    elif renowned >= 1: score += 3; breakdown['kol'] = '3 (KOL)'
    else: breakdown['kol'] = '0'
    
    # === VOL/MCAP RATIO (Chris's insight: ~3x predicts pumps) ===
    # Fetch from DexScreener if not provided
    if dex_mcap <= 0 or dex_vol <= 0:
        dex_vol, dex_mcap, vol_ratio = get_dexscreener_vol(sig.get('ca', '') or sig.get('token_address', ''))
    else:
        vol_ratio = dex_vol/dex_mcap if dex_mcap > 0 else 0
    
    if vol_ratio >= 2.0 and vol_ratio <= 4.0:  # Chris's sweet spot
        score += 10; breakdown['volmcap'] = f'10 ({vol_ratio:.1f}x - sweet spot)'
    elif vol_ratio > 4.0 and vol_ratio <= 6.0:
        score += 7; breakdown['volmcap'] = f'7 ({vol_ratio:.1f}x - active)'
    elif vol_ratio > 6.0:
        score += 3; breakdown['volmcap'] = f'3 ({vol_ratio:.1f}x - caution)'
    elif vol_ratio >= 1.0:
        score += 5; breakdown['volmcap'] = f'5 ({vol_ratio:.1f}x - developing)'
    else:
        breakdown['volmcap'] = '0 (<1x)'
    
    # === ACTION MULTIPLIER ===
    action = sig.get('action', 'PUMP')
    mult = {'KOL_BUY': 1.5, 'KOTH': 1.3, 'PUMP': 1.0, 'NEW_POOL': 1.1, 'SNIPER': 1.2}.get(action, 1.0)
    final_score = int(score * mult)
    
    return {
        'score': final_score,
        'base_score': score,
        'multiplier': mult,
        'action': action,
        'breakdown': breakdown,
        'gmgn_liquidity': liq,
        'gmgn_holders': holders,
        'gmgn_top10_pct': top10_rate * 100,
        'gmgn_creator_count': creator_count,
        'gmgn_bot_degen_rate': bot_degen_rate * 100,
        'gmgn_smart_wallets': smart,
        'gmgn_renowned_wallets': renowned,
        'dex_vol': dex_vol,
        'dex_mcap': dex_mcap,
        'vol_mcap_ratio': vol_ratio if 'vol_ratio' in dir() else (dex_vol/dex_mcap if dex_mcap > 0 else 0),
    }

if __name__ == '__main__':
    import sys
    ca = sys.argv[1] if len(sys.argv) > 1 else "63Q4cWET37oCVGaRqf9RF88JGk5GDiw5T7qekhMApump"
    sig = {'action': sys.argv[2] if len(sys.argv) > 2 else 'PUMP', 'symbol': 'TEST'}
    gmgn = get_gmgn_token_data(ca)
    sec = get_gmgn_security(ca)
    result = score_with_gmgn_api(sig, gmgn, sec)
    print(f"GMGN Score: {result['score']}/100 (base {result['base_score']})")
    for k, v in result['breakdown'].items():
        print(f"  {k}: {v}")
    print(f"Key: liq=${result['gmgn_liquidity']:,.0f} | holders={result['gmgn_holders']} | top10={result['gmgn_top10_pct']:.1f}%")
    print(f"Creator: {result['gmgn_creator_count']} tokens | BotDegen: {result['gmgn_bot_degen_rate']:.1f}%")
