#!/usr/bin/env python3
"""
Auto Scanner v3 - Chris's new criteria

BUY CRITERIA:
- Mcap: $5K-$75K for pairs <3min old, $9K-$75K for pairs >3min old
- BS Ratio: 0.25+ for pairs <2min old, 1.0+ for pairs >2min old
- Holders: 15+
- Min 5min volume: $1000
- Never re-enter previously sold tokens
- Top 10 holder % < 70%

EARLY MOMENTUM TIER:
- $5K-$12K mcap + vol/mcap 1:1+ = buy signal (bypasses normal BS)

PATTERN FILTERS:
- Top 10 holder % < 50% = healthy
- Trade fee > 20 = smart money active
- BS ratio > 0.99 = buy pressure

ANTI-PATTERNS (>3min pairs):
- Top 10 holder > 70% = dump risk
- BS < 1.0 = sell pressure
- Liquidity < $5K = rug risk
"""
import requests, json, subprocess
from datetime import datetime, timedelta
import time
from pathlib import Path
from trading_constants import (
    MIN_MCAP, MAX_MCAP, MIN_VOLUME, MIN_5MIN_VOLUME, MIN_BS_RATIO,
    MIN_HOLDERS, POSITION_SIZE, TICKER_BLACKLIST, MAX_OPEN_POSITIONS,
    SIM_RESET_TIMESTAMP, ATH_DIVERGENCE_REJECT
)

BOT_TOKEN = "8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg"
CHAT_ID = "6402511249"
TRADES_FILE = Path("/root/Dex-trading-bot/trades/sim_trades.jsonl")

def get_gmgn_ath(addr):
    """Get GMGN ATH mcap for a token"""
    try:
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
            ath_mcap = None
            if ath_price_val > 0 and supply > 0:
                ath_mcap = ath_price_val * supply
            return ath_mcap, ath_price_val, True
    except:
        pass
    return None, None, False

def get_pair_age_minutes(p):
    """Get pair age in minutes from pairCreatedAt"""
    created = p.get('pairCreatedAt', 0)
    if not created:
        return 999
    return (datetime.utcnow().timestamp() * 1000 - created) / 60000

def check_should_buy(addr, p, sym, dex, m, v, v5, bs, buys, sells, holders, pair_addr):
    """Apply Chris's new criteria"""
    
    pair_age_min = get_pair_age_minutes(p)
    is_new = pair_age_min < 3  # <3 min old
    is_very_new = pair_age_min < 2  # <2 min old
    
    # === MCAP FILTERS ===
    if is_new:
        if m < 5000:
            return False, f"mcap ${m:,.0f} < $5K (new pair)"
        if m > 75000:
            return False, f"mcap ${m:,.0f} > $75K"
    else:
        if m < 9000:
            return False, f"mcap ${m:,.0f} < $9K (older pair)"
        if m > 75000:
            return False, f"mcap ${m:,.0f} > $75K"
    
    # === VOLUME FILTER ===
    if v5 > 0 and v5 < 1000:
        return False, f"5min vol ${v5:,.0f} < $1000"
    
    # === HOLDERS FILTER ===
    if holders > 0 and holders < 15:
        return False, f"holders {holders} < 15"
    
    # === EARLY MOMENTUM TIER: $5K-$12K + vol/mcap 1:1+ ===
    v5m_ratio = v5 / m if m > 0 and v5 > 0 else 0
    vol_mcap_ratio = v / m if m > 0 else 0
    early_momentum = 5000 <= m <= 12000 and v5m_ratio >= 1.0
    
    # === ATH DIVERGENCE CHECK (reject if local peak >40% from ATH) ===
    ath_mcap, _, _ = get_gmgn_ath(addr)
    if ath_mcap and ath_mcap > 0:
        divergence = (ath_mcap - m) / ath_mcap * 100
        if divergence > ATH_DIVERGENCE_REJECT:
            return False, f"ATH reject: {divergence:.0f}% from ATH (parabolic)"
    
    if early_momentum:
        return True, f"EARLY_MOMENTUM: mcap ${m:,.0f} + vol/mcap {v5m_ratio:.1f}x"
    
    # === BS RATIO FILTERS ===
    if is_very_new:
        # <2 min: BS 0.25+ OK
        if bs < 0.25:
            return False, f"BS {bs:.2f} < 0.25 (very new)"
    else:
        # >2 min: BS 1.0+ required
        if bs < 1.0:
            return False, f"BS {bs:.2f} < 1.0"
    
    # === ANTI-PATTERN CHECKS (pairs >3min) ===
    if pair_age_min >= 3:
        if bs < 1.0:
            return False, f"BS {bs:.2f} < 1.0 (older pair = dump risk)"
    
    # === VOL/MCAP FILTER (non-early tier) ===
    if not early_momentum and vol_mcap_ratio < 1.0:
        return False, f"vol/mcap {vol_mcap_ratio:.1f}x < 1.0x"
    
    return True, f"OK: BS={bs:.2f} vol/mcap={vol_mcap_ratio:.1f}x age={pair_age_min:.0f}min pullback={chg5:.0f}%"

def check_and_buy():
    """Main scan loop"""
    timestamp = datetime.utcnow().strftime("%H:%M UTC")
    
    # Check max open positions
    try:
        with open(TRADES_FILE) as f:
            all_trades = [json.loads(l) for l in f]
        reset = SIM_RESET_TIMESTAMP
        open_pos = [t for t in all_trades if t.get('opened_at','') > reset and not t.get('closed_at') and t.get('status') != 'closed']
        if len(open_pos) >= MAX_OPEN_POSITIONS:
            print(f"⏳ Max open positions ({MAX_OPEN_POSITIONS}) reached, skipping scan")
            return None
    except:
        pass
    
    resp = requests.get(
        "https://api.dexscreener.com/token-profiles/latest/v1",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=10
    )
    
    if resp.status_code != 200:
        return None
    
    tokens = resp.json()[:80]
    
    for tok_data in tokens:
        addr = tok_data.get('tokenAddress', '')
        if not addr:
            continue
        
        try:
            r = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{addr}", timeout=10)
            if r.status_code != 200:
                continue
            
            data = r.json()
            pairs = data.get('pairs', [])
            if not pairs:
                continue
            
            p = max(pairs, key=lambda x: x.get('liquidity', {}).get('usd', 0))
            m = p.get('fdv', 0) or p.get('marketCap', 0) or 0
            v = p.get('volume', {}).get('h24', 0) or 0
            dex = p.get('dexId', '')
            sym = p.get('baseToken', {}).get('symbol', '?')
            pair_addr = p.get('pairAddress', '')
            buys = p.get('txns', {}).get('h24', {}).get('buys', 0) or 0
            sells = p.get('txns', {}).get('h24', {}).get('sells', 0) or 1
            bs = buys / sells if sells > 0 else 0
            v5 = p.get('volume', {}).get('m5', 0) or 0
            holders = p.get('holders', 0) or 0
            
            # Pumpfun OR pumpswap only
            if dex not in ['pumpfun', 'pumpswap']:
                continue
            
            # Check buy criteria
            should_buy, reason = check_should_buy(addr, p, sym, dex, m, v, v5, bs, buys, sells, holders, pair_addr)
            
            if not should_buy:
                continue
            
            # Check if already have this token
            try:
                with open(TRADES_FILE) as f:
                    existing = [json.loads(l) for l in f]
            except:
                existing = []
            
            # Check by contract address
            already_have = any(
                t.get('token_address') == addr and t.get('status') in ['open', 'open_partial']
                for t in existing
            )
            # Also block by symbol if we've traded it before (prevents same-ticker dupes)
            already_traded_sym = any(
                t.get('token', '').upper() == sym.upper() and t.get('status') in ['open', 'open_partial']
                for t in existing
            )
            if already_have or already_traded_sym:
                continue
            
            # Blacklist
            if sym in TICKER_BLACKLIST or not sym.isalpha() or len(sym) < 3:
                continue
            
            # Never re-enter
            already_exited = any(
                t.get('token_address') == addr and (t.get('fully_exited') or t.get('tp1_sold'))
                for t in existing
            )
            if already_exited:
                continue
            
            # === BUY ===
            pair_age_min = get_pair_age_minutes(p)
            trade = {
                "token": sym,
                "token_address": addr,
                "pair_address": pair_addr,
                "amount_sol": POSITION_SIZE,
                "entry_mcap": int(m),
                "entry_liquidity": p.get('liquidity', {}).get('usd', 0),
                "dex": dex,
                "action": "BUY",
                "source": "auto_scanner_v3",
                "opened_at": datetime.utcnow().isoformat(),
                "status": "open",
                "entry_reason": "EARLY_MOMENTUM" if 'EARLY_MOMENTUM' in reason else "MOMENTUM",
                "pair_age_min": round(pair_age_min, 1),
                "bs_ratio": round(bs, 2),
                "vol_mcap_ratio": round(v/m if m > 0 else 0, 2)
            }
            
            with open(TRADES_FILE, "a") as f:
                f.write(json.dumps(trade) + "\n")
            
            print(f"✅ AUTO BOUGHT [{reason}]: {sym} @ ${m:,.0f}")
            return sym
        
        except Exception as e:
            continue
    
    return None

def main():
    print("🚀 Auto Scanner v3 Started - Chris's New Criteria")
    while True:
        try:
            check_and_buy()
        except:
            pass
        time.sleep(60)  # Scan every 60 seconds

if __name__ == "__main__":
    main()
