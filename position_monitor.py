#!/usr/bin/env python3
"""
Position Monitor v3 - Auto-execute TP/stop for open positions
Live peak tracking via persistent cache file

EXIT STRATEGY (Chris's):
- TP1: +50% minimum → then 10% trailing from peak → sell 50%
- TP2: +200% → sell 25%
- TP3: +500% → sell 25%
- Trailing: 20% from peak on remaining
- Stop: -20%
"""
import requests, json
from datetime import datetime
import time
from pathlib import Path
from trading_constants import (
    TP1_PERCENT, TP1_TRAILING_PCT, TP1_SELL_PCT,
    TP2_PERCENT, TP2_TRAILING_PCT, TP2_SELL_PCT,
    TP3_PERCENT, TP3_TRAILING_PCT, TP3_SELL_PCT,
    TP4_PERCENT, TP4_TRAILING_PCT, TP4_SELL_PCT,
    TP5_PERCENT, TP5_TRAILING_PCT, TP5_SELL_PCT,
    STOP_LOSS_PERCENT, TRAILING_STOP_PCT, SIM_RESET_TIMESTAMP,
    POSITION_SIZE, MAX_OPEN_POSITIONS
)

TRADES_FILE = Path("/root/Dex-trading-bot/trades/sim_trades.jsonl")
PEAK_CACHE_FILE = Path("/root/Dex-trading-bot/position_peak_cache.json")
CHECK_INTERVAL = 5
_MIN_FETCH_INTERVAL = 5

BOT_TOKEN = "8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg"

def get_balance():
    """Calculate current balance from trades"""
    from trading_constants import CHRIS_STARTING_BALANCE as BAL, SIM_RESET_TIMESTAMP as RESET
    try:
        with open(TRADES_FILE) as f:
            lines = f.readlines()
        rt = [json.loads(l) for l in lines if json.loads(l).get('opened_at','') > RESET]
        has_pnl = [t for t in rt if t.get('pnl_sol') is not None]
        total_pnl = sum(t.get('pnl_sol',0) for t in has_pnl)
        return round(BAL + total_pnl, 4)
    except:
        return 0.0

def send_alert(msg, label="ALERT"):
    """Send alert via Telegram"""
    import urllib.request, urllib.parse
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": "6402511249", "text": msg, "parse_mode": "HTML"}
    try:
        req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode())
        resp = urllib.request.urlopen(req, timeout=10)
        print(f"[{label}] Alert sent")
    except Exception as e:
        print(f"[{label}] Alert failed: {e}")

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
    """Fetch current mcap from DexScreener"""
    try:
        r = requests.get(
            f"https://api.dexscreener.com/latest/dex/tokens/{ca}",
            timeout=5,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        if r.status_code == 200:
            data = r.json()
            if data.get('pairs'):
                for p in data['pairs']:
                    if p.get('chainId') == 'solana' and p.get('marketCap'):
                        return float(p['marketCap'])
    except:
        pass
    return None

def check_positions():
    """Check all open positions for TP/stop triggers"""
    with open(TRADES_FILE) as f:
        trades = [json.loads(l) for l in f]

    reset = SIM_RESET_TIMESTAMP
    peak_cache = load_peak_cache()
    updated = False

    for t in trades:
        if t.get('opened_at', '') <= reset:
            continue
        if t.get('fully_exited'):
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

        # Update peak with current mcap
        mcap = get_mcap_from_dex(ca)
        if mcap is None:
            print(f"  {sym}: error fetching mcap")
            continue

        if mcap > cache['peak_mcap']:
            cache['peak_mcap'] = mcap

        tp1_sold = t.get('tp1_sold')
        tp2_sold = t.get('tp2_sold')
        tp3_sold = t.get('tp3_sold')
        tp4_sold = t.get('tp4_sold')
        tp5_sold = t.get('tp5_sold')
        trailing_stopped = t.get('trailing_stopped')
        peak = cache['peak_mcap']
        gains_pct = ((mcap - entry) / entry) * 100

        # === STOP LOSS (-20%) ===
        if not tp1_sold and gains_pct <= STOP_LOSS_PERCENT:
            t['status'] = 'closed'; t['fully_exited'] = True
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
💰 Balance: {get_balance()} SOL
💰 Loss: {t["pnl_sol"]:.4f} SOL

🔗 https://dexscreener.com/solana/{ca}
🥧 https://pump.fun/{ca}

📋 Stop loss triggered"""
            send_alert(msg, "STOP_LOSS")
            print(f"🔴 {sym} STOP LOSS @ ${mcap:,.0f} ({gains_pct:.1f}%)")
            continue

        # === TP1 HIT (+35% → HOLD for v5.5) ===
        if not tp1_sold and gains_pct >= TP1_PERCENT:
            t['tp1_sold'] = True
            cache['baseline'] = mcap
            cache['peak_mcap'] = mcap
            save_peak_cache(peak_cache)
            updated = True
            if TP1_SELL_PCT > 0:
                # v5.4: actual partial sell
                t['partial_exit'] = True
                t['status'] = 'open_partial'
                t['closed_at'] = datetime.utcnow().isoformat()
                t['exit_reason'] = 'TP1_AUTO'
                sell_pct = (mcap - entry) / entry * 100
                pnl_tp1 = POSITION_SIZE * TP1_SELL_PCT / 100 * (sell_pct / 100)
                t['pnl_sol'] = pnl_tp1
                t['pnl_pct'] = sell_pct
                msg = f"""🏆 TP1 (+{TP1_PERCENT}% → sell {TP1_SELL_PCT}%) | {datetime.utcnow().strftime('%H:%M UTC')}
━━━━━━━━━━━━━━━
💰 {sym}
📍 Entry MC: ${int(entry):,}
📊 Sold at MC: ${int(mcap):,} (+{sell_pct:.1f}%)
💵 Sold: {TP1_SELL_PCT}% of position
💰 Balance: {get_balance()} SOL
💰 PnL so far: {pnl_tp1:.4f} SOL

💵 Remaining {100 - TP1_SELL_PCT}% still riding
🔗 https://dexscreener.com/solana/{ca}
🥧 https://pump.fun/{ca}

📊 Next Targets:
📈 TP2: +{TP2_PERCENT}% → Sell {TP2_SELL_PCT}% more
📈 TP3: +{TP3_PERCENT}% → Sell remaining {TP3_SELL_PCT}%
📊 Trailing: {TRAILING_STOP_PCT}% from peak"""
                send_alert(msg, "TP1")
                print(f"✅ {sym} TP1 HIT @ ${mcap:,.0f} (+{sell_pct:.1f}%)")
            else:
                # v5.5: TP1 reached but HOLDING - no sell, just track peak
                msg = f"""🚀 TP1 (+{TP1_PERCENT}% HIT - HOLDING) | {datetime.utcnow().strftime('%H:%M UTC')}
━━━━━━━━━━━━━━━
💰 {sym}
📍 Entry MC: ${int(entry):,}
📊 Current MC: ${int(mcap):,} (+{gains_pct:.1f}%)
💵 Position: Full ride in play (100% held)

🔗 https://dexscreener.com/solana/{ca}
🥧 https://pump.fun/{ca}

📊 Next Targets:
📈 TP2: +{TP2_PERCENT}% → Sell {TP2_SELL_PCT}%
📈 TP3: +{TP3_PERCENT}% → Sell {TP3_SELL_PCT}%
📈 TP5: +{TP5_PERCENT}% → Sell remaining!
⚠️ Stop: {STOP_LOSS_PERCENT}%"""
                send_alert(msg, "TP1_HOLD")
                print(f"🚀 {sym} TP1 HIT - HOLDING @ ${mcap:,.0f} (+{gains_pct:.1f}%)")
            continue

    # === TP2 HIT (+100%) ===
        if tp1_sold and not tp2_sold:
            if gains_pct >= TP2_PERCENT:
                t['tp2_sold'] = True
                t['partial_exit'] = True
                t['status'] = 'open_partial'
                t['closed_at'] = datetime.utcnow().isoformat()
                t['exit_reason'] = 'TP2_AUTO'
                pnl_tp2 = POSITION_SIZE * TP2_SELL_PCT / 100 * (gains_pct / 100)
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
💰 Balance: {get_balance()} SOL
💰 Total PnL so far: {t['pnl_sol']:.4f} SOL

💵 Remaining {100 - TP1_SELL_PCT - TP2_SELL_PCT}% still riding
🔗 https://dexscreener.com/solana/{ca}
🥧 https://pump.fun/{ca}

📊 Next Target:
📈 TP3: +{TP3_PERCENT}% → Sell remaining {TP3_SELL_PCT}%
📊 Trailing: {TRAILING_STOP_PCT}% from peak"""
                send_alert(msg, "TP2")
                print(f"✅ {sym} TP2 HIT @ ${mcap:,.0f} (+{gains_pct:.0f}%)")
                continue

        # === TP3 HIT (+200%) ===
        if tp2_sold and not tp3_sold:
            if gains_pct >= TP3_PERCENT:
                t['tp3_sold'] = True
                t['partial_exit'] = True
                t['status'] = 'open_partial'
                t['closed_at'] = datetime.utcnow().isoformat()
                t['exit_reason'] = 'TP3_AUTO'
                pnl_tp3 = POSITION_SIZE * TP3_SELL_PCT / 100 * (gains_pct / 100)
                prev_pnl = t.get('pnl_sol', 0)
                t['pnl_sol'] = prev_pnl + pnl_tp3
                cache['peak_mcap'] = mcap
                save_peak_cache(peak_cache)
                updated = True
                remaining = 100 - TP1_SELL_PCT - TP2_SELL_PCT - TP3_SELL_PCT
                msg = f"""🏆🏆🏆 TP3 HIT (+{TP3_PERCENT}%) | {datetime.utcnow().strftime('%H:%M UTC')}
━━━━━━━━━━━━━━━
💰 {sym}
📍 Entry MC: ${int(entry):,}
📊 Current MC: ${int(mcap):,} (+{gains_pct:.0f}%)
💵 Sold {TP3_SELL_PCT}% @ MC ${int(mcap):,}
💰 Balance: {get_balance()} SOL
💰 Total PnL so far: {t['pnl_sol']:.4f} SOL

💵 Remaining {remaining}% still riding
🔗 https://dexscreener.com/solana/{ca}
🥧 https://pump.fun/{ca}

📊 Next Targets:
📈 TP4: +{TP4_PERCENT}% → Sell {TP4_SELL_PCT}% more
📈 TP5: +{TP5_PERCENT}% → Sell remaining {TP5_SELL_PCT}%
📊 Trailing: {TRAILING_STOP_PCT}% from peak"""
                send_alert(msg, "TP3")
                print(f"✅ {sym} TP3 HIT @ ${mcap:,.0f} (+{gains_pct:.0f}%)")
                continue

        # === TP4 HIT (+300%) ===
        if tp3_sold and not tp4_sold:
            if gains_pct >= TP4_PERCENT:
                t['tp4_sold'] = True
                t['partial_exit'] = True
                t['status'] = 'open_partial'
                t['closed_at'] = datetime.utcnow().isoformat()
                t['exit_reason'] = 'TP4_AUTO'
                pnl_tp4 = POSITION_SIZE * TP4_SELL_PCT / 100 * (gains_pct / 100)
                prev_pnl = t.get('pnl_sol', 0)
                t['pnl_sol'] = prev_pnl + pnl_tp4
                cache['peak_mcap'] = mcap
                save_peak_cache(peak_cache)
                updated = True
                remaining = 100 - TP1_SELL_PCT - TP2_SELL_PCT - TP3_SELL_PCT - TP4_SELL_PCT
                msg = f"""🏆🏆🏆🏆 TP4 HIT (+{TP4_PERCENT}%) | {datetime.utcnow().strftime('%H:%M UTC')}
━━━━━━━━━━━━━━━
💰 {sym}
📍 Entry MC: ${int(entry):,}
📊 Current MC: ${int(mcap):,} (+{gains_pct:.0f}%)
💵 Sold {TP4_SELL_PCT}% @ MC ${int(mcap):,}
💰 Balance: {get_balance()} SOL
💰 Total PnL so far: {t['pnl_sol']:.4f} SOL

💵 Remaining {remaining}% still riding
🔗 https://dexscreener.com/solana/{ca}
🥧 https://pump.fun/{ca}

📊 Next Target:
📈 TP5: +{TP5_PERCENT}% → Sell remaining {TP5_SELL_PCT}%
📊 Trailing: {TRAILING_STOP_PCT}% from peak"""
                send_alert(msg, "TP4")
                print(f"✅ {sym} TP4 HIT @ ${mcap:,.0f} (+{gains_pct:.0f}%)")
                continue

        # === TP5 HIT (+1000%) - FULL EXIT ===
        if tp4_sold and not tp5_sold:
            if gains_pct >= TP5_PERCENT:
                t['tp5_sold'] = True
                t['partial_exit'] = True
                t['status'] = 'open_partial'
                t['closed_at'] = datetime.utcnow().isoformat()
                t['exit_reason'] = 'TP5_AUTO'
                pnl_tp5 = POSITION_SIZE * TP5_SELL_PCT / 100 * (gains_pct / 100)
                prev_pnl = t.get('pnl_sol', 0)
                t['pnl_sol'] = prev_pnl + pnl_tp5
                cache['peak_mcap'] = mcap
                save_peak_cache(peak_cache)
                updated = True
                msg = f"""🏆🏆🏆🏆🏆 TP5 HIT (+{TP5_PERCENT}%) | {datetime.utcnow().strftime('%H:%M UTC')}
━━━━━━━━━━━━━━━
💰 {sym}
📍 Entry MC: ${int(entry):,}
📊 Current MC: ${int(mcap):,} (+{gains_pct:.0f}%)
💵 Sold final {TP5_SELL_PCT}% @ MC ${int(mcap):,}
💰 Balance: {get_balance()} SOL
💰 TOTAL PNL: {t['pnl_sol']:.4f} SOL 🚀🚀🚀

🔗 https://dexscreener.com/solana/{ca}
🥧 https://pump.fun/{ca}

✅ FULL EXIT COMPLETE"""
                send_alert(msg, "TP5")
                print(f"✅ {sym} TP5 HIT @ ${mcap:,.0f} (+{gains_pct:.0f}%) - FULL EXIT")
                continue

        # === TRAILING STOP (remaining position after TP1) ===
        if tp1_sold and not trailing_stopped:
            if peak > entry:
                drawdown_pct = ((peak - mcap) / peak) * 100
                if drawdown_pct >= TRAILING_STOP_PCT:
                    t['trailing_stopped'] = True
                    t['fully_exited'] = True
                    t['status'] = 'closed'
                    t['exit_reason'] = 'TRAILING_STOP'
                    t['closed_at'] = datetime.utcnow().isoformat()
                    remaining_pct = 100 - TP1_SELL_PCT - TP2_SELL_PCT - TP3_SELL_PCT - TP4_SELL_PCT - TP5_SELL_PCT
                    remaining_pnl = POSITION_SIZE * remaining_pct / 100 * (gains_pct / 100)
                    prev_pnl = t.get('pnl_sol', 0)
                    t['pnl_sol'] = prev_pnl + remaining_pnl
                    updated = True
                    del peak_cache[ca_key]
                    msg = f"""🛑 TRAILING STOP | {datetime.utcnow().strftime('%H:%M UTC')}
━━━━━━━━━━━━━━━
💰 {sym}
📍 Entry MC: ${int(entry):,}
📊 Exit MC: ${int(mcap):,} (+{gains_pct:.1f}%)
💰 Balance: {get_balance()} SOL
💰 Total PnL: {t['pnl_sol']:.4f} SOL

🔗 https://dexscreener.com/solana/{ca}
🥧 https://pump.fun/{ca}

📋 Trailing {TRAILING_STOP_PCT}% drop from peak ${int(peak):,}"""
                    send_alert(msg, "TRAILING_STOP")
                    print(f"✅ {sym} TRAILING STOP @ ${mcap:,.0f} ({drawdown_pct:.0f}% drop from peak)")
                    continue

        # === LIVE PEAK MONITOR ===
        if entry > 0:
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
    print(f"Position Monitor v3 starting...")
    print(f"Exit Plan: TP1 +{TP1_PERCENT}% (sell {TP1_SELL_PCT}%) | TP2 +{TP2_PERCENT}% | TP3 +{TP3_PERCENT}% | Trailing {TRAILING_STOP_PCT}% | Stop {STOP_LOSS_PERCENT}%")
    print(f"Peak cache: {PEAK_CACHE_FILE}")
    print(f"Checking every {CHECK_INTERVAL}s")
    send_alert(f"Position Monitor v3 online | TP1 +{TP1_PERCENT}% | Stop {STOP_LOSS_PERCENT}%", "STARTUP")

    check_count = 0
    last_status_time = time.time()

    while True:
        try:
            check_positions()
            check_count += 1

            # Heartbeat every 60 seconds
            elapsed = time.time() - last_status_time
            if elapsed >= 60:
                open_count = 0
                try:
                    with open(TRADES_FILE) as f:
                        trades = [json.loads(l) for l in f]
                    reset = SIM_RESET_TIMESTAMP
                    open_count = len([t for t in trades if t.get('opened_at','') > reset and not t.get('closed_at') and t.get('status') != 'closed'])
                except:
                    pass
                print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Monitor alive | {check_count} checks | {open_count} open | next in {CHECK_INTERVAL}s")
                last_status_time = time.time()
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    main()

def get_balance():
    """Calculate current balance from trades"""
    from trading_constants import CHRIS_STARTING_BALANCE as BAL, SIM_RESET_TIMESTAMP as RESET
    try:
        with open(TRADES_FILE) as f:
            lines = f.readlines()
        rt = [json.loads(l) for l in lines if json.loads(l).get('opened_at','') > RESET]
        has_pnl = [t for t in rt if t.get('pnl_sol') is not None]
        total_pnl = sum(t.get('pnl_sol',0) for t in has_pnl)
        return round(BAL + total_pnl, 4)
    except:
        return 0.0
