#!/usr/bin/env python3
"""
Whale Momentum Scanner v3
Chris's Strategy v2.0 - Dip 15-50%, TP3 restored

Rules:
- Mcap: $5K - $95K
- BS: >0.2 (<5 min), >0.9 (>5 min)
- Liquidity: >$1K (waived for bonding curve)
- Top10%: ignore if 0
- 5min vol: >$1K

New pairs (<5 min):
- h1 > +50%, 5min > +50%

Older pairs (>5 min):
- 24hr > +25%, h1 > -39%, 5min > -39%

Dip: 11-39% from peak
"""
import requests, json, time
from datetime import datetime
from pathlib import Path
from trading_constants import (
    MIN_MCAP, MAX_MCAP, MIN_BS_RATIO,
    MIN_HOLDERS, MIN_5MIN_VOLUME, POSITION_SIZE,
    TICKER_BLACKLIST, MAX_OPEN_POSITIONS, SIM_RESET_TIMESTAMP,
    DIP_MIN, DIP_MAX, PEAK_WINDOW_NEW, PEAK_WINDOW_OLD,
    NEW_PUMP_COOLDOWN, OLD_PUMP_COOLDOWN
)

TRADES_FILE = Path("/root/Dex-trading-bot/trades/sim_trades.jsonl")
WHALE_DB = Path("/root/Dex-trading-bot/whales/whale_db.json")

# Track peak price for each token
_peak_prices = {}

# Track first observation time for cooldown after big pumps
_token_first_seen = {}

# Track sold tokens - NEVER re-buy these (permanent blacklist)
_sold_tokens = set()

def init_sold_tokens():
    """Load ALL closed positions from trade history - NEVER re-buy these"""
    try:
        with open(TRADES_FILE) as f:
            for line in f:
                t = json.loads(line)
                # Any token we've ever closed (sold) goes on blacklist
                if t.get('token_address') and t.get('status') == 'closed' and t.get('action') == 'BUY':
                    _sold_tokens.add(t['token_address'])
    except:
        pass

def get_pair_age_minutes(p):
    created = p.get('pairCreatedAt', 0)
    if not created:
        return 999
    return (datetime.utcnow().timestamp() * 1000 - created) / 60000

def is_ascii(s):
    try:
        return s.isascii()
    except:
        return True

def check_blacklist(p_data):
    """Check NoMint and Blacklist"""
    if p_data.get('mintable') or p_data.get('immutable') == False:
        return True, "mintable"
    if p_data.get('blacklist'):
        return True, "blacklisted"
    return False, "OK"

def get_gmgn_token_data(addr):
    """Get full GMGN token data - ATH, bonded status, etc"""
    try:
        import subprocess
        r = subprocess.run(
            ['gmgn-cli', 'token', 'info', '--chain', 'sol', '--address', addr],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode == 0:
            d = json.loads(r.stdout)
            
            # ATH mcap
            ath_price = d.get('ath_price', 0)
            supply_str = d.get('total_supply', d.get('circulating_supply', '0'))
            try:
                supply = float(supply_str)
            except:
                supply = 0
            ath_price_val = float(ath_price) if ath_price else 0
            ath_mcap = None
            if ath_price_val > 0 and supply > 0:
                ath_mcap = ath_price_val * supply
            
            # Bonded status
            migrated_pool = d.get('migrated_pool', '')
            is_bonded = migrated_pool and len(str(migrated_pool)) > 5
            
            return ath_mcap, ath_price_val, is_bonded
    except:
        pass
    return None, None, False

def get_ath_from_gmgn(addr):
    """Get ATH data from GMGN CLI - returns (ath_mcap, ath_price)"""
    ath_mcap, ath_price, _ = get_gmgn_token_data(addr)
    return ath_mcap, ath_price

def scan_token(addr):
    """Scan a single token"""
    try:
        r = requests.get(f'https://api.dexscreener.com/latest/dex/tokens/{addr}', timeout=10)
        if r.status_code != 200:
            return None, None
        data = r.json()
        pairs = data.get('pairs', [])
        if not pairs:
            return None, None
        
        p = max(pairs, key=lambda x: x.get('liquidity', {}).get('usd', 0))
        m = float(p.get('fdv', 0) or p.get('marketCap', 0) or 0)
        v5 = float(p.get('volume', {}).get('m5', 0) or 0)
        v24 = float(p.get('volume', {}).get('h24', 0) or 0)
        sym = p.get('baseToken', {}).get('symbol', '?')
        pair_addr = p.get('pairAddress', '')
        dex = p.get('dexId', '')
        
        # Basic checks
        if not is_ascii(sym):
            return None, None
        if sym in TICKER_BLACKLIST:
            return None, None
        
        # Get price changes
        chg1 = float(p.get('priceChange', {}).get('m1', 0) or 0)
        chg5 = float(p.get('priceChange', {}).get('m5', 0) or 0)
        chg60 = float(p.get('priceChange', {}).get('h1', 0) or 0)
        chg24 = float(p.get('priceChange', {}).get('h24', 0) or 0)
        
        # BS ratio
        liq = float(p.get('liquidity', {}).get('usd', 0) or 0)
        bs_mcap = float(p.get('bondingCurve', {}).get('mcap', 0) or 0)
        bs = bs_mcap / max(liq, 1) if bs_mcap > 0 else (m / max(liq, 1) if liq > 0 else 1)
        
        # Holders
        holders = int(p.get('holders', 0) or 0)
        
        # Get extra data from p
        p_data = p
        
        # Anti-patterns
        top10 = float(p.get('topHolderPercent', 0) or 0)
        if top10 > 50:
            return None, None  # Dumper
        
        # Blacklist check
        is_bl, bl_reason = check_blacklist(p_data)
        if is_bl:
            return None, None
        
        # Mcap range: $5K - $95K
        if m < 5000 or m > 95000:
            return None, None
        
        # Holders
        if holders > 0 and holders < 15:
            return None, None
        
        # Liquidity: ignore if mcap < $50K AND (new pair OR bonding curve)
        # (deferred until after we calculate pair_age)
        
        # 5min vol
        if v5 < 1000:
            return None, None
        
        # Peak tracking - use LOCAL peak only (not GMGN ATH which can be parabolic pump peak)
        # Track peak from observed prices during this session
        if addr not in _peak_prices or m > _peak_prices[addr]:
            _peak_prices[addr] = m
        peak = _peak_prices.get(addr, m)
        
        # Track first seen time
        import time
        now = time.time()
        if addr not in _token_first_seen:
            _token_first_seen[addr] = now
        
        if peak > 0:
            dip_pct = (peak - m) / peak * 100
        else:
            dip_pct = 0
        
        # Get GMGN data only for bonded status (informational), NOT for peak
        _, _, is_bonded = get_gmgn_token_data(addr)
        
        pair_age = get_pair_age_minutes(p)
        
        # Liquidity: ignore for mcap < $50K (still building)
        if liq < 1000 and m >= 50000:
            return None, None
        
        # STRATEGY: Buy the dip, not the pump
        # Key filter: 5m must be < +15% (reject parabolic pumps)
        # For pump.fun: h1 can be wild, focus on 5m and dip%
        
        if pair_age < 5:
            # NEW PAIRS (<5 min): 5m < +15%, dip 15-50%
            if chg5 > 15:
                return None, f"B: 5m +{chg5:.1f}% (parabolic pump)"
            if dip_pct < DIP_MIN:
                return None, f"B: dip <{DIP_MIN}% (no pullback)"
            if dip_pct > DIP_MAX:
                return None, f"B: dip >{DIP_MAX}% (too deep)"
        else:
            # OLDER PAIRS (>5 min): 5m < +15%, dip 15-50%, h1 not deeply red
            if chg5 > 15:
                return None, f"B: 5m +{chg5:.1f}% (parabolic pump)"
            if chg60 < -75:
                return None, f"B: h1 {chg60:+.1f}% (coin is dying)"
            if dip_pct < DIP_MIN:
                return None, f"B: dip <{DIP_MIN}% (no pullback)"
            if dip_pct > DIP_MAX:
                return None, f"B: dip >{DIP_MAX}% (too deep)"
            
            # BS ratio for older: pump.fun tokens BS=0 is OK (bonding curve), raydium needs BS > 0.9
            if dex == 'raydium' and bs < 0.9:
                return None, f"B: BS <0.9"
        
        return {
            "token": sym,
            "address": addr,
            "mcap": m,
            "bs": bs,
            "holders": holders,
            "chg1": chg1,
            "chg5": chg5,
            "chg60": chg60,
            "chg24": chg24,
            "v5": v5,
            "liq": liq,
            "dip_pct": dip_pct,
            "age": pair_age,
            "dex": dex,
            "is_bonded": is_bonded
        }, "OK"
        
    except Exception as e:
        return None, str(e)

def check_and_buy():
    """Main scan + buy loop"""
    whales = load_whales()
    
    # Get tokens from DexScreener
    try:
        resp = requests.get(
            "https://api.dexscreener.com/token-profiles/latest/v1",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        if resp.status_code != 200:
            return None, None
        tokens = resp.json()[:50]
    except:
        return None, None
    
    # Check max positions
    try:
        with open(TRADES_FILE) as f:
            existing = [json.loads(l) for l in f]
        reset = SIM_RESET_TIMESTAMP
        open_pos = [t for t in existing if t.get('opened_at','') > reset and not t.get('closed_at')]
        if len(open_pos) >= MAX_OPEN_POSITIONS:
            return None, None
    except:
        existing = []
    
    bought = None
    
    for tok_data in tokens:
        addr = tok_data.get('tokenAddress', '')
        if not addr:
            continue
        
        # Skip if already open OR previously sold
        # Check both in-memory set AND trade file
        # PERMANENT BLACKLIST - check trade file EVERY time
        already_open_or_sold = False
        try:
            with open(TRADES_FILE) as f:
                for line in f:
                    t = json.loads(line)
                    if t.get('token_address') == addr:
                        # Skip if currently open (any status with no closed_at)
                        if t.get('action') == 'BUY' and not t.get('closed_at'):
                            already_open_or_sold = True
                            break
                        # PERMANENT BLACKLIST - never re-buy if ever closed
                        if t.get('status') == 'closed' and t.get('action') == 'BUY':
                            _sold_tokens.add(addr)
        except:
            pass
        if addr in _sold_tokens or already_open_or_sold:
            continue
        
        result, msg = scan_token(addr)
        if result is None:
            continue
        
        # Log the scan
        bonded_tag = " [BONDED]" if result.get('is_bonded') else ""
        print(f"✅ CANDIDATE: {result['token']}{bonded_tag} | Mcap ${result['mcap']:,.0f} | Age {result['age']:.1f}min | Dip {result['dip_pct']:.1f}% | h1 {result['chg60']:+.1f}% | 5m {result['chg5']:+.1f}%")
        
        # Execute buy (simulated)
        trade = {
            "token": result['token'],
            "token_address": addr,
            "pair_address": addr,
            "amount_sol": POSITION_SIZE,
            "entry_mcap": int(result['mcap']),
            "entry_liquidity": result['liq'],
            "dex": result['dex'],
            "action": "BUY",
            "source": "whale_momentum_SCANNER",
            "opened_at": datetime.utcnow().isoformat(),
            "status": "open",
            "entry_reason": "SCAN_DIP",
            "bs_ratio": result['bs'],
            "chg60": result['chg60'],
            "chg5": result['chg5'],
            "dip_pct": result['dip_pct']
        }
        
        with open(TRADES_FILE, "a") as f:
            f.write(json.dumps(trade) + "\n")
        
        print(f"✅ BUY: {result['token']} @ ${result['mcap']:,.0f}")
        bought = result
        break
    
    return bought

def load_sold_tokens():
    """Load tokens we've sold from trade history"""
    try:
        with open(TRADES_FILE) as f:
            for line in f:
                t = json.loads(line)
                if t.get('token_address') and t.get('status') == 'closed' and t.get('action') == 'BUY':
                    _sold_tokens.add(t['token_address'])
    except:
        pass

def load_whales():
    try:
        with open(WHALE_DB) as f:
            d = json.load(f)
        return [w['wallet'] for w in d.get('whales', []) if w.get('winrate', 0) >= 0.5 and w.get('buy_count', 0) >= 3]
    except:
        return []

def main():
    print("🚀 Whale Momentum Scanner v4 - Dip in Momentum")
    print(f"   Mcap: $5K-$95K | Dip: 10-50% | Age-based rules")
    init_sold_tokens()  # Load ALL closed positions
    whales = load_whales()
    print(f"   Loaded {len(whales)} whales, {len(_sold_tokens)} sold (blacklisted)")
    print("Starting scans...")
    
    while True:
        try:
            check_and_buy()
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(15)  # Scan every 15 seconds

if __name__ == "__main__":
    main()
