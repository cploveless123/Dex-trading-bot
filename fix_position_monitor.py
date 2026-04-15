#!/usr/bin/env python3
"""Fix position_monitor.py to use TP5 exit plan"""

with open('/root/Dex-trading-bot/position_monitor.py', 'r') as f:
    code = f.read()

# Fix TP1 section - HOLD only, 40% trailing
old_tp1 = """        # Check TP1 (+35%): Sell 25%
        if not tp_status['tp1_hit'] and pnl_pct >= TP1_PCT:
            tp_status['tp1_hit'] = True
            sell_pct = TP1_SELL
            sell_quantity = position_size * sell_pct
            sell_token(addr, token_name, sell_quantity, current_price, "TP1")
            tp_status['tp1_sold'] = True
            peak_price = current_price
            msg = (f"🎯 TP1 HIT | {token_name}\\n"
                   f"━━━━━━━━━━━━━━━\\n"
                   f"+{pnl_pct:.1f}% | Sold {int(sell_pct*100)}%\\n"
                   f"Remaining: {int((1-sell_pct)*100)}% | Trail 20%")
            alert_sender_webhook(msg)
        
        # Trail stop after TP1 (20% from peak)
        if tp_status['tp1_hit'] and not tp_status['tp1_sold']:
            if current_price < peak_price * (1 - TP1_TRAIL/100):
                sell_quantity = position_size * (1 - TP1_SELL)
                sell_token(addr, token_name, sell_quantity, current_price, "TP1_TRAIL_STOP")
                to_remove.append(addr)
                continue"""

new_tp1 = """        # Check TP1 (+50%): HOLD only - 40% trailing stop
        if not tp_status['tp1_hit'] and pnl_pct >= TP1_PCT:
            tp_status['tp1_hit'] = True
            peak_price = current_price
            msg = (f"🎯 TP1 HIT | {token_name}\\n"
                   f"━━━━━━━━━━━━━━━\\n"
                   f"+{pnl_pct:.1f}% | HOLDING\\n"
                   f"Trailing stop: 40%")
            alert_sender_webhook(msg)
        
        # TP1 trailing stop (40% from peak)
        if tp_status['tp1_hit'] and not tp_status.get('tp1_trail_hit'):
            if current_price < peak_price * (1 - TP1_TRAIL/100):
                sell_quantity = position_size * (tp_status.get('tp1_sold_pct', 0) if tp_status.get('tp1_sold_pct', 0) > 0 else 1.0)
                sell_token(addr, token_name, sell_quantity, current_price, "TP1_TRAIL_STOP")
                tp_status['tp1_trail_hit'] = True
                to_remove.append(addr)
                continue"""

code = code.replace(old_tp1, new_tp1)

# Fix TP2 - 100%, sell 40%, 30% trail
old_tp2 = """        # Check TP2 (+95%): Sell 25%
        if not tp_status['tp2_hit'] and pnl_pct >= TP2_PCT:
            tp_status['tp2_hit'] = True
            sell_pct = TP2_SELL
            sell_quantity = position_size * sell_pct
            sell_token(addr, token_name, sell_quantity, current_price, "TP2")
            tp_status['tp2_sold'] = True
            peak_price = current_price
            msg = (f"💰 TP2 HIT | {token_name}\\n"
                   f"━━━━━━━━━━━━━━━\\n"
                   f"+{pnl_pct:.1f}% | Sold {int(sell_pct*100)}%\\n"
                   f"Remaining: {int((1-sell_pct)*100)}% | Trail 20%")
            alert_sender_webhook(msg)
        
        # Trail stop after TP2 (20% from peak)
        if tp_status['tp2_hit'] and not tp_status['tp2_sold']:
            if current_price < peak_price * (1 - TP2_TRAIL/100):
                remaining = position_size * (1 - TP1_SELL - TP2_SELL)
                sell_token(addr, token_name, remaining, current_price, "TP2_TRAIL_STOP")
                to_remove.append(addr)
                continue"""

new_tp2 = """        # Check TP2 (+100%): Sell 40% - 30% trailing stop
        if not tp_status['tp2_hit'] and pnl_pct >= TP2_PCT:
            tp_status['tp2_hit'] = True
            peak_price = current_price
            sell_pct = 0.40
            sell_quantity = position_size * sell_pct
            sell_token(addr, token_name, sell_quantity, current_price, "TP2")
            tp_status['tp2_sold_pct'] = sell_pct
            msg = (f"💰 TP2 HIT | {token_name}\\n"
                   f"━━━━━━━━━━━━━━━\\n"
                   f"+{pnl_pct:.1f}% | Sold 40%\\n"
                   f"Remaining: 60% | Trail 30%")
            alert_sender_webhook(msg)
        
        # TP2 trailing stop (30% from peak)
        if tp_status['tp2_hit'] and not tp_status.get('tp2_trail_hit'):
            if current_price < peak_price * (1 - TP2_TRAIL/100):
                remaining = position_size * (1 - tp_status.get('tp1_sold_pct', 0) - tp_status.get('tp2_sold_pct', 0))
                sell_token(addr, token_name, remaining, current_price, "TP2_TRAIL_STOP")
                tp_status['tp2_trail_hit'] = True
                to_remove.append(addr)
                continue"""

code = code.replace(old_tp2, new_tp2)

# Fix TP3 - 200%, sell 30%, 30% trail
old_tp3 = """        # Check TP3 (+200%): Sell 25%
        if not tp_status['tp3_hit'] and pnl_pct >= TP3_PCT:
            tp_status['tp3_hit'] = True
            sell_pct = TP3_SELL
            sell_quantity = position_size * sell_pct
            sell_token(addr, token_name, sell_quantity, current_price, "TP3")
            tp_status['tp3_sold'] = True
            peak_price = current_price
            msg = (f"💰 TP3 HIT | {token_name}\\n"
                   f"━━━━━━━━━━━━━━━\\n"
                   f"+{pnl_pct:.1f}% | Sold {int(sell_pct*100)}%\\n"
                   f"Remaining: {int((1-sell_pct)*100)}% | Trail 20%")
            alert_sender_webhook(msg)
        
        # Trail stop after TP3 (20% from peak)
        if tp_status['tp3_hit'] and not tp_status['tp3_sold']:
            if current_price < peak_price * (1 - TP3_TRAIL/100):
                remaining = position_size * (1 - TP1_SELL - TP2_SELL - TP3_SELL)
                sell_token(addr, token_name, remaining, current_price, "TP3_TRAIL_STOP")
                to_remove.append(addr)
                continue"""

new_tp3 = """        # Check TP3 (+200%): Sell 30% - 30% trailing stop
        if not tp_status['tp3_hit'] and pnl_pct >= TP3_PCT:
            tp_status['tp3_hit'] = True
            peak_price = current_price
            sell_pct = 0.30
            sell_quantity = position_size * sell_pct
            sell_token(addr, token_name, sell_quantity, current_price, "TP3")
            tp_status['tp3_sold_pct'] = sell_pct
            msg = (f"💰 TP3 HIT | {token_name}\\n"
                   f"━━━━━━━━━━━━━━━\\n"
                   f"+{pnl_pct:.1f}% | Sold 30%\\n"
                   f"Remaining: 70% | Trail 30%")
            alert_sender_webhook(msg)
        
        # TP3 trailing stop (30% from peak)
        if tp_status['tp3_hit'] and not tp_status.get('tp3_trail_hit'):
            if current_price < peak_price * (1 - TP3_TRAIL/100):
                remaining = position_size * (1 - tp_status.get('tp1_sold_pct', 0) - tp_status.get('tp2_sold_pct', 0) - tp_status.get('tp3_sold_pct', 0))
                sell_token(addr, token_name, remaining, current_price, "TP3_TRAIL_STOP")
                tp_status['tp3_trail_hit'] = True
                to_remove.append(addr)
                continue"""

code = code.replace(old_tp3, new_tp3)

# Fix TP4 - 300%, sell 20%, 30% trail
old_tp4 = """        # Check TP4 (+300%): Sell 25%
        if not tp_status['tp4_hit'] and pnl_pct >= TP4_PCT:
            tp_status['tp4_hit'] = True
            sell_pct = TP4_SELL
            sell_quantity = position_size * sell_pct
            sell_token(addr, token_name, sell_quantity, current_price, "TP4")
            tp_status['tp4_sold'] = True
            peak_price = current_price
            msg = (f"💰 TP4 HIT | {token_name}\\n"
                   f"━━━━━━━━━━━━━━━\\n"
                   f"+{pnl_pct:.1f}% | Sold {int(sell_pct*100)}%\\n"
                   f"Remaining: {int((1-sell_pct)*100)}% | Trail 20%")
            alert_sender_webhook(msg)
        
        # Trail stop after TP4 (20% from peak)
        if tp_status['tp4_hit'] and not tp_status['tp4_sold']:
            if current_price < peak_price * (1 - TP4_TRAIL/100):
                remaining = position_size * (1 - TP1_SELL - TP2_SELL - TP3_SELL - TP4_SELL)
                sell_token(addr, token_name, remaining, current_price, "TP4_TRAIL_STOP")
                to_remove.append(addr)
                continue"""

new_tp4 = """        # Check TP4 (+300%): Sell 20% - 30% trailing stop
        if not tp_status['tp4_hit'] and pnl_pct >= TP4_PCT:
            tp_status['tp4_hit'] = True
            peak_price = current_price
            sell_pct = 0.20
            sell_quantity = position_size * sell_pct
            sell_token(addr, token_name, sell_quantity, current_price, "TP4")
            tp_status['tp4_sold_pct'] = sell_pct
            msg = (f"💰 TP4 HIT | {token_name}\\n"
                   f"━━━━━━━━━━━━━━━\\n"
                   f"+{pnl_pct:.1f}% | Sold 20%\\n"
                   f"Remaining: 80% | Trail 30%")
            alert_sender_webhook(msg)
        
        # TP4 trailing stop (30% from peak)
        if tp_status['tp4_hit'] and not tp_status.get('tp4_trail_hit'):
            if current_price < peak_price * (1 - TP4_TRAIL/100):
                remaining = position_size * (1 - tp_status.get('tp1_sold_pct', 0) - tp_status.get('tp2_sold_pct', 0) - tp_status.get('tp3_sold_pct', 0) - tp_status.get('tp4_sold_pct', 0))
                sell_token(addr, token_name, remaining, current_price, "TP4_TRAIL_STOP")
                tp_status['tp4_trail_hit'] = True
                to_remove.append(addr)
                continue"""

code = code.replace(old_tp4, new_tp4)

# Fix TP5 - 1000%, sell ALL, 20% trail
old_tp5 = """        # Check TP5 (+1000%): Sell 25%
        if not tp_status['tp5_hit'] and pnl_pct >= TP5_PCT:
            tp_status['tp5_hit'] = True
            sell_pct = TP5_SELL
            sell_quantity = position_size * sell_pct
            sell_token(addr, token_name, sell_quantity, current_price, "TP5")
            tp_status['tp5_sold'] = True
            peak_price = current_price
            msg = (f"🚀🚀🚀 TP5 HIT | {token_name}\\n"
                   f"━━━━━━━━━━━━━━━\\n"
                   f"+{pnl_pct:.1f}% | Sold {int(sell_pct*100)}%\\n"
                   f"Target reached!")
            alert_sender_webhook(msg)
        
        # Trail stop after TP5 (20% from peak)
        if tp_status['tp5_hit'] and not tp_status['tp5_sold']:
            if current_price < peak_price * (1 - TP5_TRAIL/100):
                remaining = position_size * (1 - TP1_SELL - TP2_SELL - TP3_SELL - TP4_SELL - TP5_SELL)
                sell_token(addr, token_name, remaining, current_price, "TP5_TRAIL_STOP")
                to_remove.append(addr)
                continue"""

new_tp5 = """        # Check TP5 (+1000%): Sell ALL - 20% trailing stop
        if not tp_status['tp5_hit'] and pnl_pct >= TP5_PCT:
            tp_status['tp5_hit'] = True
            peak_price = current_price
            # Sell all remaining
            sold_so_far = sum([tp_status.get(f'tp{tp}_sold_pct', 0) for tp in ['1','2','3','4']])
            remaining_pct = 1.0 - sold_so_far
            remaining = position_size * remaining_pct
            sell_token(addr, token_name, remaining, current_price, "TP5")
            msg = (f"🚀🚀🚀 TP5 HIT | {token_name}\\n"
                   f"━━━━━━━━━━━━━━━\\n"
                   f"+{pnl_pct:.1f}% | SOLD ALL\\n"
                   f"Target reached!")
            alert_sender_webhook(msg)
            tp_status['tp5_trail_hit'] = True  # Mark as done
            to_remove.append(addr)
            continue
        
        # TP5 trailing stop (20% from peak)
        if tp_status.get('tp5_hit') and not tp_status.get('tp5_trail_hit'):
            if current_price < peak_price * (1 - TP5_TRAIL/100):
                tp_status['tp5_trail_hit'] = True
                to_remove.append(addr)
                continue"""

code = code.replace(old_tp5, new_tp5)

# Fix stop loss - was -25%, now -30%
old_stop = """        # Stop loss (-25%)
        if pnl_pct <= -STOP_LOSS_PCT:
            sell_quantity = position_size * (1 - TP1_SELL - TP2_SELL - TP3_SELL - TP4_SELL - TP5_SELL)
            sell_token(addr, token_name, sell_quantity, current_price, "STOP_LOSS")
            msg = (f"🛑 STOP LOSS | {token_name}\\n"
                   f"━━━━━━━━━━━━━━━\\n"
                   f"{pnl_pct:.1f}% | Exited")
            alert_sender_webhook(msg)
            to_remove.append(addr)
            continue"""

new_stop = """        # Stop loss (-30%): Exit all
        if pnl_pct <= -STOP_LOSS_PCT:
            sold_so_far = sum([tp_status.get(f'tp{tp}_sold_pct', 0) for tp in ['1','2','3','4','5']])
            remaining_pct = 1.0 - sold_so_far
            remaining = position_size * remaining_pct
            if remaining > 0:
                sell_token(addr, token_name, remaining, current_price, "STOP_LOSS")
            msg = (f"🛑 STOP LOSS | {token_name}\\n"
                   f"━━━━━━━━━━━━━━━\\n"
                   f"{pnl_pct:.1f}% | Exited all")
            alert_sender_webhook(msg)
            to_remove.append(addr)
            continue"""

code = code.replace(old_stop, new_stop)

with open('/root/Dex-trading-bot/position_monitor.py', 'w') as f:
    f.write(code)

print("Done - compile with: cd /root/Dex-trading-bot && /root/Dex-trading-bot/venv/bin/python -m py_compile position_monitor.py")
