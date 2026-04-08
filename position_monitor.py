#!/usr/bin/env python3
"""
Position Monitor v2 - Auto-execute TP/stop for open positions
Live peak tracking via persistent cache file
"""
import requests, json
from datetime import datetime
import time
from pathlib import Path
from trading_constants import (
    REAL_TP1_PCT, TP1_PERCENT, TP1_SELL_PCT, TP2_PERCENT, TP2_SELL_PCT,
    STOP_LOSS_PERCENT, TRAILING_STOP_PCT, EXIT_PLAN_TEXT, SIM_RESET_TIMESTAMP,
    POSITION_SIZE
)

BOT_TOKEN = "8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg"
CHAT_ID = "6402511249"
TRADES_FILE = "/root/Dex-trading-bot/trades/sim_trades.jsonl"
PEAK_CACHE_FILE = "/root/Dex-trading-bot/position_peak_cache.json"
CHECK_INTERVAL = 60  # Check every 60 seconds

def load_peak_cache():
    """Load cached peak mcaps from disk"""
    if Path(PEAK_CACHE_FILE).exists():
        try:
            with open(PEAK_CACHE_FILE) as f:
                return json.load(f)
        except:
            pass
    return {}

def save_peak_cache(cache):
    """Persist peak mcap cache to disk"""
    with open(PEAK_CACHE_FILE, 'w') as f:
        json.dump(cache, f)

def get_live_mcap(tok_address):
    """Get current mcap for a token"""
    try:
        resp = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{tok_address}", timeout=10)
        data = resp.json()
        pairs = data.get('pairs', [])
        if pairs:
            p = max(pairs, key=lambda x: x.get('liquidity', {}).get('usd', 0))
            return float(p.get('fdv', 0) or 0)
    except:
        pass
    return None

def send_alert(msg, label="ALERT"):
    """Send alert via Telegram"""
    import urllib.request, urllib.parse
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
    try:
        req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode())
        resp = urllib.request.urlopen(req, timeout=10)
        print(f"[{label}] ✅ Alert sent")
    except Exception as e:
        print(f"[{label}] ❌ Alert failed: {e}")

def check_positions():
    """Check all open positions for TP/stop hits"""
    # Load peak cache
    peak_cache = load_peak_cache()
    
    with open(TRADES_FILE) as f:
        trades = [json.loads(l) for l in f]
    
    updated = False
    
    for t in trades:
        if t.get('status') not in ['open', 'open_partial']:
            continue
        
        sym = t.get('token', '?')
        ca = t.get('token_address', '')
        entry = float(t.get('entry_mcap', 0))
        if not ca or not entry:
            continue
        
        mcap = get_live_mcap(ca)
        if mcap is None or mcap == 0:
            continue
        
        # === LIVE PEAK TRACKING ===
        ca_key = ca[:20]  # Use first 20 chars as key
        if ca_key not in peak_cache:
            peak_cache[ca_key] = {'peak_mcap': entry, 'baseline': entry}
        
        cache = peak_cache[ca_key]
        
        # Update peak if current mcap is higher (only while in active trade)
        if mcap > cache['peak_mcap']:
            cache['peak_mcap'] = mcap
        
        tp1_sold = t.get('tp1_sold')
        tp2_sold = t.get('tp2_sold')
        trailing_stopped = t.get('trailing_stopped')
        peak = cache['peak_mcap']
        
        gains_pct = ((mcap - entry) / entry) * 100
        
        # === TP1 HIT ===
        if not tp1_sold and gains_pct >= REAL_TP1_PCT:
            t['tp1_sold'] = True
            t['partial_exit'] = True
            t['status'] = 'open_partial'
            t['closed_at'] = datetime.utcnow().isoformat()
            t['exit_reason'] = 'TP1_AUTO'
            t['pnl_sol'] = POSITION_SIZE * TP1_SELL_PCT / 100 * (REAL_TP1_PCT / 100)
            t['pnl_pct'] = REAL_TP1_PCT
            # Reset baseline to TP1 price — trailing stop measures from here
            # CRITICAL: Save immediately to disk so process restart won't lose this
            cache['baseline'] = mcap
            cache['peak_mcap'] = mcap
            save_peak_cache(peak_cache)  # Save BEFORE exit to ensure persistence
            print(f"  🔧 {sym} TP1 @ ${mcap:,.0f} — baseline reset to ${mcap:,.0f}, cache saved")
            updated = True
            
            msg = f"""🏆 TP1 HIT | {datetime.utcnow().strftime('%H:%M UTC')}
━━━━━━━━━━━━━━━
💰 {sym}
📊 +{REAL_TP1_PCT:.1f}% (+{t['pnl_sol']:.4f} SOL sold)

💵 Sold {TP1_SELL_PCT}% of position @ mcap ${mcap:,.0f}
💰 Remaining 26% riding with trailing stop

🔗 https://dexscreener.com/solana/{ca}
🥧 https://pump.fun/{ca}

📊 Exit Plan:
📈 TP2: +100% (sell remaining 26%)
⚠️ Stop: {STOP_LOSS_PERCENT}% (trailing)
⏰ Check again in {CHECK_INTERVAL}s"""
            send_alert(msg, "TP1")
            print(f"✅ {sym} TP1 HIT @ ${mcap:,.0f}")
        
        # === TRAILING STOP (remaining position after TP1) ===
        elif tp1_sold and not tp2_sold and not trailing_stopped:
            # Measure drawdown from PEAK (highest mcap after TP1)
            # This is the correct trailing stop: 30% drop from peak
            if cache['peak_mcap'] > entry:
                drawdown_pct = ((cache['peak_mcap'] - mcap) / cache['peak_mcap']) * 100
            else:
                drawdown_pct = 0
            
            TRAIL_STOP_THRESHOLD = 30  # % drop from peak to trigger trailing stop
            
            if drawdown_pct >= TRAIL_STOP_THRESHOLD:
                t['trailing_stopped'] = True
                t['tp2_sold'] = True
                t['exit_reason'] = 'TRAILING_STOP'
                t['closed_at'] = datetime.utcnow().isoformat()
                
                remaining_pct = gains_pct  # Net gain from entry
                tp2_pnl = POSITION_SIZE * (100 - TP1_SELL_PCT) / 100 * (remaining_pct / 100)
                prev_pnl = t.get('pnl_sol', 0)
                t['pnl_sol'] = prev_pnl + tp2_pnl
                updated = True
                
                # Clean up cache
                del peak_cache[ca_key]
                
                msg = f"""🛑 TRAILING STOP | {datetime.utcnow().strftime('%H:%M UTC')}
━━━━━━━━━━━━━━━
💰 {sym}
📊 Remaining sold @ {remaining_pct:.1f}% (from entry)
💰 Total PnL: {t['pnl_sol']:.4f} SOL

🔗 https://dexscreener.com/solana/{ca}
🥧 https://pump.fun/{ca}

📋 Exit: Trailing stop ({TRAIL_STOP_THRESHOLD}% drop from peak ${int(cache['peak_mcap']):,})"""
                send_alert(msg, "TRAILING_STOP")
                print(f"✅ {sym} TRAILING STOP @ ${mcap:,.0f} ({drawdown_pct:.0f}% drop from peak ${int(cache['peak_mcap']):,})")
        
        # === STOP LOSS ===
        elif not tp1_sold and gains_pct <= STOP_LOSS_PERCENT:
            t['status'] = 'closed'
            t['exit_reason'] = 'STOP_AUTO'
            t['closed_at'] = datetime.utcnow().isoformat()
            t['pnl_sol'] = POSITION_SIZE * (gains_pct / 100)
            t['pnl_pct'] = gains_pct
            updated = True
            
            # Clean up cache
            if ca_key in peak_cache:
                del peak_cache[ca_key]
            
            msg = f"""🔴 STOP LOSS | {datetime.utcnow().strftime('%H:%M UTC')}
━━━━━━━━━━━━━━━
💰 {sym}
📊 {gains_pct:.1f}% @ mcap ${mcap:,.0f}
💰 Loss: {t['pnl_sol']:.4f} SOL

🔗 https://dexscreener.com/solana/{ca}
🥧 https://pump.fun/{ca}

📋 Closed: stop loss triggered"""
            send_alert(msg, "STOP_LOSS")
            print(f"🔴 {sym} STOP LOSS @ ${mcap:,.0f}")
        
        # === LOG LIVE PEAK ===
        else:
            baseline = cache.get('baseline', entry)
            if baseline > entry:
                drawdown = ((baseline - mcap) / baseline) * 100
            else:
                drawdown = 0
            print(f"  {sym}: mcap=${mcap:,.0f} | gain={gains_pct:+.1f}% | peak=${peak:,.0f} | dd={drawdown:+.0f}%")
    
    # Save updated peak cache
    save_peak_cache(peak_cache)
    
    # Write updated trades file
    if updated:
        with open(TRADES_FILE, 'w') as f:
            for t in trades:
                f.write(json.dumps(t) + '\n')
    
    return updated

def main():
    print(f"📊 Position Monitor v2 starting...")
    print(f"📋 Exit Plan: TP1 +{REAL_TP1_PCT:.1f}% (sell {TP1_SELL_PCT}%) | Trailing {TRAILING_STOP_PCT}% drop | Stop {STOP_LOSS_PERCENT}%")
    print(f"📋 Peak cache: {PEAK_CACHE_FILE}")
    print(f"⏰ Checking every {CHECK_INTERVAL}s")
    
    # Verify Telegram
    send_alert("✅ Position Monitor v2 online", "STARTUP")
    
    while True:
        try:
            check_positions()
        except Exception as e:
            print(f"❌ Error in check_positions: {e}")
        time.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    main()
