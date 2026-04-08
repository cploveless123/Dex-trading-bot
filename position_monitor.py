#!/usr/bin/env python3
"""
Position Monitor v2 - Auto-execute TP/stop for open positions
Live peak tracking via persistent cache file

NEW STRATEGY: TP1 at +100%, TP2 at +200%, TP3 at +500%, trailing stop at 30%
"""
import requests, json
from datetime import datetime
import time
from pathlib import Path
from trading_constants import (
    REAL_TP1_PCT, TP1_PERCENT, TP1_SELL_PCT,
    TP2_PERCENT, TP2_SELL_PCT, TP3_PERCENT, TP3_SELL_PCT,
    STOP_LOSS_PERCENT, TRAILING_STOP_PCT, EXIT_PLAN_TEXT, SIM_RESET_TIMESTAMP,
    POSITION_SIZE, MAX_OPEN_POSITIONS
)

TRADES_FILE = Path("/root/Dex-trading-bot/trades/sim_trades.jsonl")
PEAK_CACHE_FILE = Path("/root/Dex-trading-bot/position_peak_cache.json")
CHECK_INTERVAL = 5
_MIN_FETCH_INTERVAL = 5

BOT_TOKEN = "8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg"

def send_alert(msg, label="ALERT"):
    """Send alert via Telegram"""
    import urllib.request, urllib.parse
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": "6402511249", "text": msg, "parse_mode": "HTML"}
    try:
        req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode())
        resp = urllib.request.urlopen(req, timeout=10)
        print(f"[{label}] ✅ Alert sent")
    except Exception as e:
        print(f"[{label}] ❌ Alert failed: {e}")

def load_peak_cache():
    try:
        with open(PEAK_CACHE_FILE) as f:
            return json.load(f)
    except:
        return {}

def save_peak_cache(cache):
    with open(PEAK_CACHE_FILE, 'w') as f:
        json.dump(cache, f)

def get_mcap_from_dex(ca):
    """Fetch current mcap from DexScreener with rate limiting"""
    try:
        r = requests.get(f"https://api.dexscreener.com/dex/tokens/{ca}", timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            data = r.json()
            if data.get('pairs'):
                for p in data['pairs']:
                    if p.get('chainId') == 'solana' and p.get('marketCap'):
                        return float(p['marketCap'])
    except:
        pass
    return None

def count_open_positions():
    """Count currently open positions from trades file"""
    try:
        with open(TRADES_FILE) as f:
            trades = [json.loads(l) for l in f]
        reset = SIM_RESET_TIMESTAMP
        open_pos = [t for t in trades if t.get('opened_at','') > reset and not t.get('closed_at') and t.get('status') != 'closed']
        return len(open_pos)
    except:
        return 0

def check_positions():
    """Check all open positions for TP/stop triggers"""
    with open(TRADES_FILE) as f:
        trades = [json.loads(l) for f in f]

    reset = SIM_RESET_TIMESTAMP
    peak_cache = load_peak_cache()
    updated = False

    for t in trades:
        if t.get('opened_at', '') <= reset:
            continue
        if t.get('closed_at'):
            continue
        if t.get('status') not in ('open', 'open_partial'):
            continue

        ca = t.get('token_address', '')
        sym = t.get('token', '?')
        entry = t.get('entry_mcap', 0)
        if not ca or not entry:
            continue

        ca_key = ca[:20]
        if ca_key not in peak_cache:
            peak_cache[ca_key] = {'peak_mcap': entry, 'baseline': entry}

        cache = peak_cache[ca_key]

        # Update peak
        mcap = get_mcap_from_dex(ca)
        if mcap is None:
            print(f"  {sym}: error fetching mcap")
            continue

        if mcap > cache['peak_mcap']:
            cache['peak_mcap'] = mcap

        tp1_sold = t.get('tp1_sold')
        tp2_sold = t.get('tp2_sold')
        tp3_sold = t.get('tp3_sold')
        trailing_stopped = t.get('trailing_stopped')
        peak = cache['peak_mcap']
        gains_pct = ((mcap - entry) / entry) * 100

        # === RUG PULL MONITOR ===
        if t.get('status') == 'open' and not tp1_sold:
            if gains_pct <= -50 and not t.get('emergency_stopped'):
                t['status'] = 'closed'
                t['exit_reason'] = 'RUG_PROTECTION'
                t['closed_at'] = datetime.utcnow().isoformat()
                t['pnl_sol'] = POSITION_SIZE * -0.50
                t['pnl_pct'] = -50
                updated = True
                msg = f"""🚨 RUG PROTECTION | {datetime.utcnow().strftime('%H:%M UTC')}
━━━━━━━━━━━━━━━
💰 {sym}
📍 Entry MC: ${int(entry):,}
📊 Exit MC: ${int(mcap):,} (-50% crash!)
💰 Loss: {t['pnl_sol']:.4f} SOL

⚠️ Emergency exit -50% drop detected!
🔗 https://dexscreener.com/solana/{ca}
🥧 https://pump.fun/{ca}"""
                send_alert(msg, "RUG")
                print(f"🚨 {sym} RUG PROTECTION @ ${mcap:,.0f} (-50% from entry)")
                continue

        # === TP1 HIT (+100%) ===
        if not tp1_sold and gains_pct >= REAL_TP1_PCT:
            t['tp1_sold'] = True
            t['partial_exit'] = True
            t['status'] = 'open_partial'
            t['closed_at'] = datetime.utcnow().isoformat()
            t['exit_reason'] = 'TP1_AUTO'
            pnl_tp1 = POSITION_SIZE * TP1_SELL_PCT / 100 * (REAL_TP1_PCT / 100)
            t['pnl_sol'] = pnl_tp1
            t['pnl_pct'] = REAL_TP1_PCT
            cache['baseline'] = mcap
            cache['peak_mcap'] = mcap
            save_peak_cache(peak_cache)
            updated = True

            msg = f"""🏆 TP1 HIT (+{TP1_PERCENT}%) | {datetime.utcnow().strftime('%H:%M UTC')}
━━━━━━━━━━━━━━━
💰 {sym}
📍 Entry MC: ${int(entry):,}
💵 Sold: {TP1_SELL_PCT}% of position @ MC ${int(mcap):,}
📊 +{REAL_TP1_PCT:.1f}% (+{pnl_tp1:.4f} SOL)

💵 Remaining 50% still riding 🚀
🔗 https://dexscreener.com/solana/{ca}
🥧 https://pump.fun/{ca}

📊 Next Targets:
📈 TP2: +{TP2_PERCENT}% → Sell 25% more
📈 TP3: +{TP3_PERCENT}% → Sell remaining 25%
📊 Trailing: {TRAILING_STOP_PCT}% from peak"""
            send_alert(msg, "TP1")
            print(f"✅ {sym} TP1 HIT @ ${mcap:,.0f}")
            continue

        # === TP2 HIT (+200%) ===
        if tp1_sold and not tp2_sold and gains_pct >= REAL_TP2_PCT:
            t['tp2_sold'] = True
            t['partial_exit'] = True
            t['status'] = 'open_partial'
            t['closed_at'] = datetime.utcnow().isoformat()
            t['exit_reason'] = 'TP2_AUTO'
            pnl_tp2 = POSITION_SIZE * TP2_SELL_PCT / 100 * (REAL_TP2_PCT / 100)
            prev_pnl = t.get('pnl_sol', 0)
            t['pnl_sol'] = prev_pnl + pnl_tp2
            cache['peak_mcap'] = mcap
            save_peak_cache(peak_cache)
            updated = True

            msg = f"""🏆🏆 TP2 HIT (+{TP2_PERCENT}%) | {datetime.utcnow().strftime('%H:%M UTC')}
━━━━━━━━━━━━━━━
💰 {sym}
📍 Entry MC: ${int(entry):,}
📊 Current MC: ${int(mcap):,} (+{gains_pct:.0f}%)
💵 Sold another {TP2_SELL_PCT}% @ MC ${int(mcap):,}
💰 Total PnL so far: {t['pnl_sol']:.4f} SOL

💵 Remaining 25% still riding 🚀
🔗 https://dexscreener.com/solana/{ca}
🥧 https://pump.fun/{ca}

📊 Next Target:
📈 TP3: +{TP3_PERCENT}% → Sell remaining 25%
📊 Trailing: {TRAILING_STOP_PCT}% from peak"""
            send_alert(msg, "TP2")
            print(f"✅ {sym} TP2 HIT @ ${mcap:,.0f}")
            continue

        # === TP3 HIT (+500%) ===
        if tp2_sold and not tp3_sold and gains_pct >= REAL_TP3_PCT:
            t['tp3_sold'] = True
            t['partial_exit'] = True
            t['status'] = 'open_partial'
            t['closed_at'] = datetime.utcnow().isoformat()
            t['exit_reason'] = 'TP3_AUTO'
            pnl_tp3 = POSITION_SIZE * TP3_SELL_PCT / 100 * (REAL_TP3_PCT / 100)
            prev_pnl = t.get('pnl_sol', 0)
            t['pnl_sol'] = prev_pnl + pnl_tp3
            cache['peak_mcap'] = mcap
            save_peak_cache(peak_cache)
            updated = True

            msg = f"""🏆🏆🏆 TP3 HIT (+{TP3_PERCENT}%) | {datetime.utcnow().strftime('%H:%M UTC')}
━━━━━━━━━━━━━━━
💰 {sym}
📍 Entry MC: ${int(entry):,}
📊 Current MC: ${int(mcap):,} (+{gains_pct:.0f}%)
💵 Sold final {TP3_SELL_PCT}% @ MC ${int(mcap):,}
💰 TOTAL PNL: {t['pnl_sol']:.4f} SOL 🚀🚀🚀

🔗 https://dexscreener.com/solana/{ca}
🥧 https://pump.fun/{ca}

✅ FULL EXIT COMPLETE - Position fully closed"""
            send_alert(msg, "TP3")
            print(f"✅ {sym} TP3 HIT @ ${mcap:,.0f} - FULL EXIT")
            continue

        # === TRAILING STOP (remaining position) ===
        if tp1_sold and not trailing_stopped:
            if cache['peak_mcap'] > entry:
                drawdown_pct = ((cache['peak_mcap'] - mcap) / cache['peak_mcap']) * 100
            else:
                drawdown_pct = 0

            if drawdown_pct >= TRAILING_STOP_PCT:
                t['trailing_stopped'] = True
                t['exit_reason'] = 'TRAILING_STOP'
                t['closed_at'] = datetime.utcnow().isoformat()
                remaining_pct = gains_pct
                remaining_pnl = POSITION_SIZE * (100 - TP1_SELL_PCT - TP2_SELL_PCT - TP3_SELL_PCT) / 100 * (remaining_pct / 100)
                prev_pnl = t.get('pnl_sol', 0)
                t['pnl_sol'] = prev_pnl + remaining_pnl
                updated = True
                del peak_cache[ca_key]

                msg = f"""🛑 TRAILING STOP | {datetime.utcnow().strftime('%H:%M UTC')}
━━━━━━━━━━━━━━━
💰 {sym}
📍 Entry MC: ${int(entry):,}
📊 Exit MC: ${int(mcap):,} ({remaining_pct:.1f}% from entry)
💰 Total PnL: {t['pnl_sol']:.4f} SOL

🔗 https://dexscreener.com/solana/{ca}
🥧 https://pump.fun/{ca}

📋 Exit: {TRAILING_STOP_PCT}% drop from peak ${int(cache['peak_mcap']):,}"""
                send_alert(msg, "TRAILING_STOP")
                print(f"✅ {sym} TRAILING STOP @ ${mcap:,.0f} ({drawdown_pct:.0f}% drop from peak)")
                continue

        # === STOP LOSS ===
        if not tp1_sold and gains_pct <= STOP_LOSS_PERCENT:
            t['status'] = 'closed'
            t['exit_reason'] = 'STOP_AUTO'
            t['closed_at'] = datetime.utcnow().isoformat()
            t['pnl_sol'] = POSITION_SIZE * (gains_pct / 100)
            t['pnl_pct'] = gains_pct
            updated = True
            if ca_key in peak_cache:
                del peak_cache[ca_key]

            msg = f"""🔴 STOP LOSS | {datetime.utcnow().strftime('%H:%M UTC')}
━━━━━━━━━━━━━━━
💰 {sym}
📍 Entry MC: ${int(entry):,}
📊 Exit MC: ${int(mcap):,} ({gains_pct:.1f}%)
💰 Loss: {t['pnl_sol']:.4f} SOL

🔗 https://dexscreener.com/solana/{ca}
🥧 https://pump.fun/{ca}

📋 Closed: stop loss triggered"""
            send_alert(msg, "STOP_LOSS")
            print(f"🔴 {sym} STOP LOSS @ ${mcap:,.0f}")
            continue

        # === LOG LIVE PEAK ===
        baseline = cache.get('baseline', entry)
        if baseline > entry:
            drawdown = ((baseline - mcap) / baseline) * 100
        else:
            drawdown = 0
        print(f"  {sym}: mcap=${mcap:,.0f} | gain={gains_pct:+.1f}% | peak=${peak:,.0f} | dd={drawdown:+.0f}%")

    save_peak_cache(peak_cache)

    if updated:
        with open(TRADES_FILE, 'w') as f:
            for t in trades:
                f.write(json.dumps(t) + '\n')

    return updated

def main():
    print(f"📊 Position Monitor v3 starting...")
    print(f"📋 Exit Plan: TP1 +{TP1_PERCENT}% (sell {TP1_SELL_PCT}%) | TP2 +{TP2_PERCENT}% (sell {TP2_SELL_PCT}%) | TP3 +{TP3_PERCENT}% (sell {TP3_SELL_PCT}%) | Trailing {TRAILING_STOP_PCT}% | Stop {STOP_LOSS_PERCENT}%")
    print(f"📋 Peak cache: {PEAK_CACHE_FILE}")
    print(f"⏰ Checking every {CHECK_INTERVAL}s")
    send_alert("✅ Position Monitor v3 online - NEW STRATEGY: TP1 +100%, TP2 +200%, TP3 +500%, Trailing 30%", "STARTUP")

    while True:
        try:
            check_positions()
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    main()
