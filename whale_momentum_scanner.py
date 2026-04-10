#!/usr/bin/env python3
"""
Whale Momentum Scanner v3
Chris's Strategy: Dip detection with age-based rules

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
    TICKER_BLACKLIST, MAX_OPEN_POSITIONS, SIM_RESET_TIMESTAMP
)

TRADES_FILE = Path("/root/Dex-trading-bot/trades/sim_trades.jsonl")
WHALE_DB = Path("/root/Dex-trading-bot/whales/whale_db.json")

# Track peak price for each token
_peak_prices = {}

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

def get_ath_from_gmgn(addr):
    """Get ATH data from GMGN CLI - returns (ath_mcap, ath_price)"""
    try:
        import subprocess
        r = subprocess.run(
            ['gmgn-cli', 'token', 'info', '--chain', 'sol', '--address', addr],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode == 0:
            d = json.loads(r.stdout)
            ath_price = d.get('ath_price', 0)
            supply_str = d.get('total_supply', d.get('circulating_supply', '0'))
            try:
                supply = float(supply_str)
            except:
                supply = 0
            ath_price_val = float(ath_price) if ath_price else 0
            if ath_price_val > 0 and supply > 0:
                ath_mcap = ath_price_val * supply
                return float(ath_mcap), float(ath_price)
    except:
        pass
    return None, None

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
        
        # Peak tracking - use GMGN ATH mcap if available
        ath_mcap, _ = get_ath_from_gmgn(addr)
        if ath_mcap and ath_mcap > m:
            peak = ath_mcap  # Use ATH as reference if token has pumped before
        else:
            if addr not in _peak_prices or m > _peak_prices[addr]:
                _peak_prices[addr] = m
            peak = _peak_prices.get(addr, m)
        
        if peak > 0:
            dip_pct = (peak - m) / peak * 100
        else:
            dip_pct = 0
        
        pair_age = get_pair_age_minutes(p)
        
        # Liquidity: ignore for mcap < $50K (still building)
        if liq < 1000 and m >= 50000:
            return None, None
        
        if pair_age < 5:
            # NEW PAIRS (<5 min): h1 > +50%, 5min > +50%
            if chg60 < 50:
                return None, f"B: new h1 <+50%"
            if chg5 < 50:
                return None, f"B: new 5min <+50%"
            if dip_pct < 10:
                return None, f"B: dip <10%"
            if dip_pct > 39:
                return None, f"B: dip >39%"
        else:
            # OLDER PAIRS (>5 min): 24hr > +25%, h1 > -39%, 5min > -39%
            if chg24 < 25:
                return None, f"B: 24hr <+25%"
            if chg60 < -39:
                return None, f"B: h1 <-39%"
            if chg5 < -39:
                return None, f"B: 5min <-39%"
            if dip_pct < 10:
                return None, f"B: dip <10%"
            if dip_pct > 39:
                return None, f"B: dip >39%"
            
            # BS ratio for older
            if bs < 0.9:
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
            "dex": dex
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
        try:
            with open(TRADES_FILE) as f:
                for line in f:
                    t = json.loads(line)
                    if t.get('token_address') == addr and t.get('status') == 'closed' and t.get('action') == 'BUY':
                        _sold_tokens.add(addr)
                        break
        except:
            pass
        if addr in _sold_tokens:
            continue
        
        result, msg = scan_token(addr)
        if result is None:
            continue
        
        # Log the scan
        print(f"✅ CANDIDATE: {result['token']} | Mcap ${result['mcap']:,.0f} | Age {result['age']:.1f}min | Dip {result['dip_pct']:.1f}% | h1 {result['chg60']:+.1f}% | 5m {result['chg5']:+.1f}%")
        
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
    print("🚀 Whale Momentum Scanner v3 - Chris's Strategy")
    print(f"   Mcap: $5K-$95K | Dip: 11-39% | Age-based rules")
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
