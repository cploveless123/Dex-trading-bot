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

# Track price history for falling knife detection
# Key = token address, Value = list of (timestamp, price) tuples
_price_history = {}

# Track consecutive drops - if price drops 3+ times in a row, it's a falling knife
_consecutive_drops = {}

def is_falling_knife(addr, current_price):
    """
    Detect falling knife: price dropping 3+ consecutive scans.
    Returns (True, reason) if falling knife, (False, None) if stable/recovering.
    """
    now = time.time()
    
    # Initialize tracking for this token
    if addr not in _price_history:
        _price_history[addr] = []
        _consecutive_drops[addr] = 0
    
    # Add current price to history
    _price_history[addr].append((now, current_price))
    
    # Keep only last 10 observations (scans ~15s apart, so ~2.5 min of history)
    _price_history[addr] = _price_history[addr][-10:]
    
    history = _price_history[addr]
    
    # Need at least 2 data points to detect trend
    if len(history) < 2:
        return False, None
    
    # Check consecutive drops
    drops = 0
    for i in range(len(history) - 1, 0, -1):
        prev_time, prev_price = history[i - 1]
        curr_time, curr_price = history[i]
        # Only count if within last 3 observations
        if now - prev_time > 60:  # Skip if old data point
            continue
        if curr_price < prev_price:
            drops += 1
        else:
            break  # Found a rise, reset count
    
    _consecutive_drops[addr] = drops
    
    if drops >= 3:
        return True, f"Falling knife: {drops} consecutive drops"
    
    return False, None

def init_sold_tokens():
    """Load ALL closed positions from trade history - NEVER re-buy these"""
    try:
        with open(TRADES_FILE) as f:
            for line in f:
                t = json.loads(line)
                # Any token we've ever closed (closed_at is set) goes on blacklist
                if t.get('token_address') and t.get('closed_at') and t.get('action') == 'BUY':
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
    """Get full GMGN token data - ATH, bonded status, holder data"""
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
            
            # Holder data from GMGN (more accurate than DexScreener)
            # GMGN returns strings for some fields - convert properly
            holder_raw = d.get('holder_count', 0)
            holder_count = int(holder_raw) if holder_raw else 0
            
            top10_raw = d.get('top_10_holder_rate', 0) or d.get('dev', {}).get('top_10_holder_rate', 0) or 0
            try:
                top_10_holder_rate = float(top10_raw) if top10_raw else 0.0
            except (ValueError, TypeError):
                top_10_holder_rate = 0.0
            
            liq_raw = d.get('liquidity', 0)
            try:
                liq = float(liq_raw) if liq_raw else 0.0
            except (ValueError, TypeError):
                liq = 0.0
            
            return {
                'ath_mcap': ath_mcap,
                'ath_price': ath_price_val,
                'is_bonded': is_bonded,
                'holder_count': holder_count,
                'top_10_holder_rate': top_10_holder_rate,
                'liquidity': liq
            }
    except:
        pass
    return None

def get_ath_from_gmgn(addr):
    """Get ATH data from GMGN CLI - returns (ath_mcap, ath_price)"""
    data = get_gmgn_token_data(addr)
    if data:
        return data.get('ath_mcap'), data.get('ath_price')
    return None, None

def get_gmgn_holder_data(addr):
    """Get holder data from GMGN - returns (holder_count, top_10_holder_rate)"""
    data = get_gmgn_token_data(addr)
    if data:
        return data.get('holder_count', 0), data.get('top_10_holder_rate', 0)
    return 0, 0

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
        
        # Get GMGN data AFTER basic filters pass (optimization - GMGN is slow)
        # Only fetch GMGN if DexScreener data looks promising
        ath_mcap = None
        is_bonded = False
        gmgn_holders = 0
        gmgn_top10 = 0.0
        gmgn_liq = 0.0
        
        # Quick DexScreener holder check first (before slow GMGN call)
        ds_holders = int(p.get('holders', 0) or 0)
        ds_top10 = float(p.get('topHolderPercent', 0) or 0)
        
        # Only call GMGN if DexScreener shows 0 holders (need GMGN backup)
        # This is the main optimization to avoid slow GMGN calls
        gmgn_data = None
        if ds_holders == 0 or ds_top10 == 0:
            gmgn_data = get_gmgn_token_data(addr)
        
        if gmgn_data:
            ath_mcap = gmgn_data.get('ath_mcap')
            is_bonded = gmgn_data.get('is_bonded', False)
            gmgn_holders = int(gmgn_data.get('holder_count', 0)) if gmgn_data.get('holder_count') else 0
            gmgn_top10 = float(gmgn_data.get('top_10_holder_rate', 0)) if gmgn_data.get('top_10_holder_rate') else 0.0
            gmgn_liq = float(gmgn_data.get('liquidity', 0)) if gmgn_data.get('liquidity') else 0.0
        else:
            ath_mcap = None
            is_bonded = False
            gmgn_holders = 0
            gmgn_top10 = 0.0
            gmgn_liq = 0.0
        
        # Use GMGN holders/liquidity as primary, DexScreener as backup
        holders = gmgn_holders if gmgn_holders > 0 else ds_holders
        top10 = gmgn_top10 if gmgn_top10 > 0 else ds_top10
        liq = gmgn_liq if gmgn_liq > 0 else float(p.get('liquidity', {}).get('usd', 0) or 0)
        
        # Anti-patterns
        if top10 > 50:
            return None, None  # Dumper
        
        # Blacklist check
        is_bl, bl_reason = check_blacklist(p)
        if is_bl:
            return None, None
        
        # Mcap range
        if m < MIN_MCAP or m > MAX_MCAP:
            return None, None
        
        # Holders check (bot farm / min holders)
        if holders == 0 or top10 == 0:
            return None, f"B: holders={holders} top10={top10}% (bot farm)"
        if holders > 0 and holders < 15:
            return None, None
        
        # Track first seen time for peak window
        import time
        now = time.time()
        if addr not in _token_first_seen:
            _token_first_seen[addr] = now
        
        # Get pair age for peak window selection
        pair_age = get_pair_age_minutes(p)
        
        # Peak tracking - use LOCAL peak only
        # New pairs (<10 min): track peak for PEAK_WINDOW_NEW (90s)
        # Older pairs (>10 min): track peak for PEAK_WINDOW_OLD (180s)
        peak_window = PEAK_WINDOW_NEW if pair_age < 10 else PEAK_WINDOW_OLD
        
        time_watching = now - _token_first_seen[addr]
        if time_watching < peak_window:
            # Still within peak window - update peak if higher
            if addr not in _peak_prices or m > _peak_prices[addr]:
                _peak_prices[addr] = m
        else:
            # Past peak window - don't update peak anymore
            if addr not in _peak_prices:
                _peak_prices[addr] = m
        
        peak = _peak_prices.get(addr, m)
        dip_pct = (peak - m) / peak * 100 if peak > 0 else 0
        
        # Liquidity: ignore for mcap < $50K (still building)
        if liq < 1000 and m >= 50000:
            return None, None
        
        # 5min vol: ignore for fresh tokens (<20min) since volume builds up
        if pair_age >= 20 and v5 < 1000:
            return None, None
        
        # STRATEGY v5: Fresh launches (<60min) with proven momentum + pullback
        # Momentum = h1 or 24h showing big move, dip = pullback from peak
        
        if pair_age > 60:
            return None, f"B: age {pair_age:.1f}min >60min (too old)"
        
        # Need proven momentum (h1 or 24h > +50%)
        if chg60 < 50 and chg24 < 50:
            return None, f"B: h1 {chg60:+.1f}% 24h {chg24:+.1f}% (no momentum)"
        
        # Dip from local peak: 15-35%
        if dip_pct < DIP_MIN:
            return None, f"B: dip {dip_pct:.1f}% <{DIP_MIN}% (not enough pullback)"
        if dip_pct > DIP_MAX:
            return None, f"B: dip {dip_pct:.1f}% >{DIP_MAX}% (too deep)"
        
        # BS ratio for raydium: must be > 0.9 (pump.fun BS=0 is OK)
        if dex == 'raydium' and bs < 0.9:
            return None, f"B: BS {bs:.2f} <0.9"
        
        # ANTI-MOMENTUM: If chg5 > +15%, we're chasing — reject
        # EXCEPTION: Sustained momentum - if h1 > +100% and mcap < $60K, allow up to +50%
        sustained_momentum = chg60 > 100 and m < 60000
        
        # Falling knife check - reject if price is still falling on 5m
        if chg5 < 0:
            return None, f"B: chg5 {chg5:+.1f}% (falling knife, not a dip)"
        
        # Parabolic pump check (new pairs <30min): if chg5 > 15% of h1, it's parabolic
        # e.g. h1 +144%, chg5 +30% → 30/144 = 21% → parabolic, reject
        if pair_age < 30 and chg60 > 0 and chg5 / chg60 > 0.15:
            return None, f"B: chg5 {chg5:.1f}% / h1 {chg60:.0f}% = {chg5/chg60*100:.0f}% (parabolic - <30min)"
        
        if chg5 > 50:
            return None, f"B: chg5 +{chg5:.1f}% (extreme pump)"
        if chg5 > 15 and not sustained_momentum:
            return None, f"B: chg5 +{chg5:.1f}% (momentum pump, not dip)"
        
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
        
        # Skip if already in permanent blacklist (in-memory set - fast)
        if addr in _sold_tokens:
            continue
        
        # Only check file if we don't know about this token yet
        if addr not in _sold_tokens:
            already_open_or_sold = False
            try:
                with open(TRADES_FILE) as f:
                    for line in f:
                        t = json.loads(line)
                        if t.get('token_address') == addr:
                            if t.get('action') == 'BUY' and not t.get('closed_at'):
                                already_open_or_sold = True
                                break
                            if t.get('action') == 'BUY' and t.get('closed_at'):
                                _sold_tokens.add(addr)
                                break
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
        
        # === FALLING KNIFE CHECK ===
        # Track price across scans - reject if 3+ consecutive drops
        is_falling, fk_reason = is_falling_knife(addr, result['mcap'])
        if is_falling:
            print(f"   ❌ REJECT: {fk_reason} - skipping")
            continue
        
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
    print("🚀 Whale Momentum Scanner v5.1 - Dip in Momentum")
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
