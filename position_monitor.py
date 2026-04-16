#!/usr/bin/env python3
"""
Position Monitor - Tracks open positions and executes TP5 exit strategy

TP5 Progressive Selling Strategy:
- TP1 (+50%): HOLD - watch only, 40% trailing stop
- TP2 (+100%): Sell 40%, 30% trailing stop  
- TP3 (+200%): Sell 30%, 30% trailing stop
- TP4 (+300%): Sell 20%, 30% trailing stop
- TP5 (+1000%): Sell ALL, target reached
- Stop: -30% from entry
"""

import subprocess, json, time, urllib.request, urllib.parse
from datetime import datetime, timezone
from trading_constants import (
    TP1_PCT, TP1_TRAIL,
    TP2_PCT, TP2_SELL_PCT, TP2_TRAIL,
    TP3_PCT, TP3_SELL_PCT, TP3_TRAIL,
    TP4_PCT, TP4_SELL_PCT, TP4_TRAIL,
    TP5_PCT, TP5_SELL_PCT, TP5_TRAIL,
    STOP_LOSS_PCT,
    POSITION_SIZE,
    TRADES_FILE, BOT_TOKEN, CHAT_ID,
    CHRIS_STARTING_BALANCE
)

MONITOR_LOG = '/root/Dex-trading-bot/position_monitor.log'

def log(msg):
    ts = datetime.utcnow().strftime('%H:%M:%S')
    print(f"[{ts}] {msg}")

def alert_sender_webhook(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
        req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode())
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        log(f"Alert error: {e}")

def get_token_price(addr):
    """Get current price from GMGN"""
    try:
        r = subprocess.run(['gmgn-cli', 'token', 'info', '--chain', 'sol', '--address', addr],
                         capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            data = json.loads(r.stdout)
            return float(data.get('price', 0))
    except:
        pass
    return 0

def get_positions():
    positions = []
    try:
        with open(TRADES_FILE) as f:
            for line in f:
                if not line.strip():
                    continue
                trade = json.loads(line)
                if trade.get('action') == 'BUY' and trade.get('status') == 'open':
                    positions.append(trade)
    except:
        pass
    return positions

def sell_token(addr, token_name, quantity, price, reason):
    """Record a sell - prevents duplicate sells"""
    # Check if we already sold this token recently (within last 60s)
    recent_sells = []
    try:
        with open(TRADES_FILE) as f:
            for line in f:
                if not line.strip():
                    continue
                t = json.loads(line)
                if t.get('token_address') == addr and t.get('action') == 'SELL':
                    recent_sells.append(t)
    except:
        pass
    
    # If we have a recent sell for this token, skip
    now = datetime.now(timezone.utc)
    for t in recent_sells:
        try:
            sold_at = datetime.fromisoformat(t.get('sold_at', '2000-01-01').replace('+00:00', '+00:00'))
            if (now - sold_at).total_seconds() < 60:
                log(f"SKIP SELL: {token_name} already sold {t.get('sold_at')}")
                return
        except:
            pass
    
    # Find corresponding BUY entry for PnL calculation
    entry_price = None
    entry_mcap = None
    try:
        with open(TRADES_FILE) as f:
            for line in f:
                if not line.strip():
                    continue
                t = json.loads(line)
                if t.get('token_address') == addr and t.get('action') == 'BUY':
                    entry_price = float(t.get('entry_price', 0))
                    entry_mcap = int(t.get('entry_mcap', 0))
                    break
    except:
        pass
    
    # Calculate PnL
    pnl_sol = 0.0
    if entry_price and entry_price > 0:
        pnl_sol = (float(price) - entry_price) * quantity / entry_price
    
    # Calculate exit mcap
    exit_mcap = 0
    if entry_price > 0 and entry_mcap:
        exit_mcap = int(float(price) / entry_price * entry_mcap)
    
    trade = {
        'action': 'SELL',
        'token_address': addr,
        'token_name': token_name,
        'sell_price': price,
        'sell_quantity': quantity,
        'pnl_sol': round(pnl_sol, 6),
        'pnl_pct': round((float(price) / entry_price - 1) * 100, 2) if entry_price > 0 else 0,
        'exit_mcap': exit_mcap,
        'reason': reason,
        'sold_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00'),
    }
    with open(TRADES_FILE, 'a') as f:
        f.write(json.dumps(trade) + '\n')
    log(f"SOLD {quantity:.4f} SOL of {token_name} @ {price} ({reason}) | pnl={pnl_sol:.4f} SOL")

def update_position_sold(addr, sell_quantity, reason):
    """Update the open position with sell info"""
    trades = []
    with open(TRADES_FILE) as f:
        for line in f:
            if not line.strip():
                continue
            trade = json.loads(line)
            if trade.get('token_address') == addr and trade.get('action') == 'BUY' and trade.get('status') == 'open':
                trade['partial_exit'] = True
                trade['reason'] = reason
            trades.append(trade)
    with open(TRADES_FILE, 'w') as f:
        for t in trades:
            f.write(json.dumps(t) + '\n')

def close_position(addr, reason):
    """Close an open position - only call ONCE per exit"""
    trades = []
    found = False
    with open(TRADES_FILE) as f:
        for line in f:
            if not line.strip():
                continue
            trade = json.loads(line)
            if trade.get('token_address') == addr and trade.get('action') == 'BUY' and trade.get('status') == 'open' and not found:
                trade['status'] = 'closed'
                trade['closed_at'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00')
                trade['exit_reason'] = reason
                found = True  # Only close once
            trades.append(trade)
    with open(TRADES_FILE, 'w') as f:
        for t in trades:
            f.write(json.dumps(t) + '\n')

def monitor_cycle():
    positions = get_positions()
    if not positions:
        return
    
    log(f"Monitoring {len(positions)} positions")
    
    for trade in positions:
        addr = trade['token_address']
        token_name = trade['token_name']
        entry_price = float(trade['entry_price'])
        entry_mcap = int(trade['entry_mcap'])
        position_size = float(trade.get('entry_sol', POSITION_SIZE))
        
        current_price = get_token_price(addr)
        if current_price == 0:
            log(f"No price for {token_name}")
            continue
        
        pnl_pct = ((current_price - entry_price) / entry_price) * 100
        pnl_sol = (current_price - entry_price) * position_size / entry_price
        mcap = int(current_price / entry_price * entry_mcap) if entry_price > 0 else 0
        
        # Calculate current balance
        total_pnl = 0.0
        with open(TRADES_FILE) as f:
            for tline in f:
                if not tline.strip():
                    continue
                t = json.loads(tline)
                if t.get('action') == 'SELL' and t.get('pnl_sol') is not None:
                    try:
                        total_pnl += float(t['pnl_sol'])
                    except (ValueError, TypeError):
                        pass
        current_balance = CHRIS_STARTING_BALANCE + total_pnl
        
        tp_status = trade.get('tp_status', {'tp1_hit': False, 'tp2_hit': False, 'tp3_hit': False, 'tp4_hit': False, 'tp5_hit': False})
        
        # Initialize sold tracking
        for tp in ['tp1', 'tp2', 'tp3', 'tp4', 'tp5']:
            key = f'{tp}_sold_pct'
            if key not in tp_status:
                tp_status[key] = 0
        
        peak_price = float(trade.get('peak_price', entry_price))
        if current_price > peak_price:
            peak_price = current_price
        
        to_remove = False
        
        # TP1 (+50%): HOLD - watch only, 40% trailing stop
        if not tp_status['tp1_hit'] and pnl_pct >= TP1_PCT:
            tp_status['tp1_hit'] = True
            peak_price = current_price  # CRITICAL: update peak to actual TP1 price
            msg = (f"💰 TP1 HIT | {token_name}\n"
                   f"━━━━━━━━━━━━━━━\n"
                   f"+{pnl_pct:.1f}% (+{pnl_sol:.4f} SOL) | HOLDING\n"
                   f"Balance: ${current_balance:.4f} SOL\n"
                   f"Entry mcap: ${entry_mcap:,}\n"
                   f"Current: ${mcap:,.0f}\n"
                   f"Trailing: 40% from peak\n"
                   f"🔗 https://dexscreener.com/solana/{addr}\n"
                   f"🥧 https://pump.fun/{addr}")
            alert_sender_webhook(msg)
        
        # TP1 trailing stop (40% from peak)
        if tp_status['tp1_hit'] and not tp_status.get('tp1_trail_hit'):
            if current_price < peak_price * (1 - TP1_TRAIL/100):
                msg = (f"🛑 TP1 TRAIL STOP | {token_name}\n"
                       f"━━━━━━━━━━━━━━━\n"
                       f"{pnl_pct:.1f}% ({pnl_sol:.4f} SOL) | Exited\n"
                       f"Balance: ${current_balance:.4f} SOL\n"
                       f"Entry: ${entry_mcap:,}\n"
                       f"Peak: ${peak_price * entry_mcap / entry_price:,.0f}\n"
                       f"Exit: ${mcap:,.0f}\n"
                       f"🔗 https://dexscreener.com/solana/{addr}")
                alert_sender_webhook(msg)
                close_position(addr, "TP1_TRAIL_STOP")
                to_remove = True
        
        # TP2 (+100%): Sell 40%, 30% trailing stop
        if not tp_status['tp2_hit'] and pnl_pct >= TP2_PCT:
            tp_status['tp2_hit'] = True
            tp_status['tp2_sold_pct'] = TP2_SELL_PCT
            peak_price = current_price  # CRITICAL: update peak to actual TP2 price
            sell_token(addr, token_name, position_size * TP2_SELL_PCT, current_price, "TP2")
            msg = (f"💰 TP2 HIT | {token_name}\n"
                   f"━━━━━━━━━━━━━━━\n"
                   f"+{pnl_pct:.1f}% (+{pnl_sol:.4f} SOL) | Sold 40%\n"
                   f"Balance: ${current_balance:.4f} SOL\n"
                   f"Entry mcap: ${entry_mcap:,}\n"
                   f"Current mcap: ${mcap:,.0f}\n"
                   f"Remaining: 60% | Trail 30%\n"
                   f"🔗 https://dexscreener.com/solana/{addr}\n"
                   f"🥧 https://pump.fun/{addr}")
            alert_sender_webhook(msg)
        
        # TP2 trailing stop (30% from peak)
        if tp_status['tp2_hit'] and not tp_status.get('tp2_trail_hit'):
            if current_price < peak_price * (1 - TP2_TRAIL/100):
                remaining_pct = 1 - tp_status['tp2_sold_pct']
                sell_token(addr, token_name, position_size * remaining_pct, current_price, "TP2_TRAIL_STOP")
                msg = (f"🛑 TP2 TRAIL STOP | {token_name}\n"
                       f"━━━━━━━━━━━━━━━\n"
                       f"{pnl_pct:.1f}% ({pnl_sol:.4f} SOL) | Exited\n"
                       f"Balance: ${current_balance:.4f} SOL\n"
                       f"Entry: ${entry_mcap:,}\n"
                       f"Peak: ${peak_price * entry_mcap / entry_price:,.0f}\n"
                       f"Exit: ${mcap:,.0f}\n"
                       f"🔗 https://dexscreener.com/solana/{addr}")
                alert_sender_webhook(msg)
                close_position(addr, "TP2_TRAIL_STOP")
                to_remove = True
        
        # TP3 (+200%): Sell 30%, 30% trailing stop
        if not tp_status['tp3_hit'] and pnl_pct >= TP3_PCT:
            tp_status['tp3_hit'] = True
            tp_status['tp3_sold_pct'] = TP3_SELL_PCT
            peak_price = current_price  # CRITICAL: update peak to actual TP3 price
            sell_token(addr, token_name, position_size * TP3_SELL_PCT, current_price, "TP3")
            msg = (f"💰 TP3 HIT | {token_name}\n"
                   f"━━━━━━━━━━━━━━━\n"
                   f"+{pnl_pct:.1f}% (+{pnl_sol:.4f} SOL) | Sold 30%\n"
                   f"Balance: ${current_balance:.4f} SOL\n"
                   f"Entry mcap: ${entry_mcap:,}\n"
                   f"Current mcap: ${mcap:,.0f}\n"
                   f"Remaining: 70% | Trail 30%\n"
                   f"🔗 https://dexscreener.com/solana/{addr}\n"
                   f"🥧 https://pump.fun/{addr}")
            alert_sender_webhook(msg)
        
        # TP3 trailing stop (30% from peak)
        if tp_status['tp3_hit'] and not tp_status.get('tp3_trail_hit'):
            if current_price < peak_price * (1 - TP3_TRAIL/100):
                sold_pct = tp_status.get('tp2_sold_pct', 0) + tp_status.get('tp3_sold_pct', 0)
                remaining_pct = 1 - sold_pct
                sell_token(addr, token_name, position_size * remaining_pct, current_price, "TP3_TRAIL_STOP")
                msg = (f"🛑 TP3 TRAIL STOP | {token_name}\n"
                       f"━━━━━━━━━━━━━━━\n"
                       f"{pnl_pct:.1f}% ({pnl_sol:.4f} SOL) | Exited\n"
                       f"Balance: ${current_balance:.4f} SOL\n"
                       f"Entry: ${entry_mcap:,}\n"
                       f"Peak: ${peak_price * entry_mcap / entry_price:,.0f}\n"
                       f"Exit: ${mcap:,.0f}\n"
                       f"🔗 https://dexscreener.com/solana/{addr}")
                alert_sender_webhook(msg)
                close_position(addr, "TP3_TRAIL_STOP")
                to_remove = True
        
        # TP4 (+300%): Sell 20%, 30% trailing stop
        if not tp_status['tp4_hit'] and pnl_pct >= TP4_PCT:
            tp_status['tp4_hit'] = True
            tp_status['tp4_sold_pct'] = TP4_SELL_PCT
            peak_price = current_price  # CRITICAL: update peak to actual TP4 price
            sell_token(addr, token_name, position_size * TP4_SELL_PCT, current_price, "TP4")
            msg = (f"💰 TP4 HIT | {token_name}\n"
                   f"━━━━━━━━━━━━━━━\n"
                   f"+{pnl_pct:.1f}% (+{pnl_sol:.4f} SOL) | Sold 20%\n"
                   f"Balance: ${current_balance:.4f} SOL\n"
                   f"Entry mcap: ${entry_mcap:,}\n"
                   f"Current mcap: ${mcap:,.0f}\n"
                   f"Remaining: 80% | Trail 30%\n"
                   f"🔗 https://dexscreener.com/solana/{addr}\n"
                   f"🥧 https://pump.fun/{addr}")
            alert_sender_webhook(msg)
        
        # TP4 trailing stop (30% from peak)
        if tp_status['tp4_hit'] and not tp_status.get('tp4_trail_hit'):
            if current_price < peak_price * (1 - TP4_TRAIL/100):
                sold_pct = sum([tp_status.get(f'tp{tp}_sold_pct', 0) for tp in [2, 3, 4]])
                remaining_pct = 1 - sold_pct
                sell_token(addr, token_name, position_size * remaining_pct, current_price, "TP4_TRAIL_STOP")
                msg = (f"🛑 TP4 TRAIL STOP | {token_name}\n"
                       f"━━━━━━━━━━━━━━━\n"
                       f"{pnl_pct:.1f}% ({pnl_sol:.4f} SOL) | Exited\n"
                       f"Balance: ${current_balance:.4f} SOL\n"
                       f"Entry: ${entry_mcap:,}\n"
                       f"Peak: ${peak_price * entry_mcap / entry_price:,.0f}\n"
                       f"Exit: ${mcap:,.0f}\n"
                       f"🔗 https://dexscreener.com/solana/{addr}")
                alert_sender_webhook(msg)
                close_position(addr, "TP4_TRAIL_STOP")
                to_remove = True
        
        # TP5 (+1000%): Sell ALL
        if not tp_status['tp5_hit'] and pnl_pct >= TP5_PCT:
            tp_status['tp5_hit'] = True
            peak_price = current_price  # CRITICAL: update peak to actual TP5 price
            sold_pct = sum([tp_status.get(f'tp{tp}_sold_pct', 0) for tp in [2, 3, 4]])
            remaining_pct = 1 - sold_pct
            sell_token(addr, token_name, position_size * remaining_pct, current_price, "TP5")
            msg = (f"🚀🚀🚀 TP5 HIT | {token_name}\n"
                   f"━━━━━━━━━━━━━━━\n"
                   f"+{pnl_pct:.1f}% (+{pnl_sol:.4f} SOL) | SOLD ALL\n"
                   f"Balance: ${current_balance:.4f} SOL\n"
                   f"Entry: ${entry_mcap:,}\n"
                   f"Exit: ${mcap:,.0f}\n"
                   f"TARGET REACHED!\n"
                   f"🔗 https://dexscreener.com/solana/{addr}")
            alert_sender_webhook(msg)
            close_position(addr, "TP5_COMPLETE")
            to_remove = True
        
        # Stop loss (-30%)
        if pnl_pct <= -STOP_LOSS_PCT:
            sold_pct = sum([tp_status.get(f'tp{tp}_sold_pct', 0) for tp in [2, 3, 4, 5]])
            remaining_pct = 1 - sold_pct
            if remaining_pct > 0:
                sell_token(addr, token_name, position_size * remaining_pct, current_price, "STOP_LOSS")
            msg = (f"🛑 STOP LOSS | {token_name}\n"
                   f"━━━━━━━━━━━━━━━\n"
                   f"{pnl_pct:.1f}% ({pnl_sol:.4f} SOL) | Exited all\n"
                   f"Balance: ${current_balance:.4f} SOL\n"
                   f"Entry: ${entry_mcap:,}\n"
                   f"Exit: ${mcap:,.0f}\n"
                   f"🔗 https://dexscreener.com/solana/{addr}")
            alert_sender_webhook(msg)
            close_position(addr, "STOP_LOSS")
            to_remove = True
        
        # Update peak price in trade
        if not to_remove:
            trades = []
            with open(TRADES_FILE) as f:
                for line in f:
                    if not line.strip():
                        continue
                    t = json.loads(line)
                    if t.get('token_address') == addr and t.get('action') == 'BUY' and t.get('status') == 'open':
                        t['peak_price'] = peak_price
                        t['tp_status'] = tp_status
                    trades.append(t)
            with open(TRADES_FILE, 'w') as f:
                for t in trades:
                    f.write(json.dumps(t) + '\n')

def main():
    log("Position Monitor Started - TP5 Progressive Selling")
    log(f"TP1: +{TP1_PCT}% HOLD, Trail {TP1_TRAIL}%")
    log(f"TP2: +{TP2_PCT}% sell {int(TP2_SELL_PCT*100)}%, Trail {TP2_TRAIL}%")
    log(f"TP3: +{TP3_PCT}% sell {int(TP3_SELL_PCT*100)}%, Trail {TP3_TRAIL}%")
    log(f"TP4: +{TP4_PCT}% sell {int(TP4_SELL_PCT*100)}%, Trail {TP4_TRAIL}%")
    log(f"TP5: +{TP5_PCT}% sell ALL, Trail {TP5_TRAIL}%")
    log(f"Stop: -{STOP_LOSS_PCT}%")
    
    while True:
        try:
            monitor_cycle()
        except Exception as e:
            log(f"Monitor error: {e}")
        time.sleep(7)  # Check positions every 7 seconds

if __name__ == '__main__':
    main()
