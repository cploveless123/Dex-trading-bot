#!/usr/bin/env python3
"""
Trading Simulator — Full GMGN-style reporting
"""
import json
import random
import time
from datetime import datetime
from pathlib import Path

SIGNALS_DIR = Path("/root/Dex-trading-bot/signals")
TRADES_DIR = Path("/root/Dex-trading-bot/trades")
SIM_TRADES_FILE = TRADES_DIR / "sim_trades.jsonl"

# Config
POSITION_SIZE = 0.1
INITIAL_BALANCE = 1.0
TP1_PCT = 0.50
TP2_PCT = 1.00
STOP_LOSS = -0.30

# Costs
SLIPPAGE = 0.02  # 2% slippage
TAX_FEE = 0.03   # 3% trading fees/taxes (simulated)

# State
balance = INITIAL_BALANCE
positions = []
closed_trades = []
stats = {'total_trades': 0, 'wins': 0, 'losses': 0, 'best': 0, 'worst': 0}

def format_signal(sig):
    """Format signal in GMGN style"""
    symbol = sig.get('symbol', sig.get('token_address', 'UNKNOWN')[:8])
    action = sig.get('action', 'BUY')
    source = sig.get('source', sig.get('_source', 'GMGN'))
    
    # Action emoji
    if action == 'KOL_BUY':
        emoji = '🏐'
        action_text = f'{source.upper()} BUY'
    elif action == 'PUMP':
        emoji = '💊'
        action_text = f'{source.upper()} PUMP'
    elif action == 'KOTH':
        emoji = '👑'
        action_text = f'{source.upper()} KOTH'
    else:
        emoji = '📡'
        action_text = f'{source.upper()} SIGNAL'
    
    # Metrics
    change = sig.get('change_pct', 0)
    liquidity = sig.get('liquidity', 0)
    mcap = sig.get('mcap', 0)
    price = sig.get('price', sig.get('current_price', '—'))
    
    # Format liquidity
    if liquidity >= 1000000:
        liq_str = f"${liquidity/1000000:.1f}M"
    elif liquidity >= 1000:
        liq_str = f"${liquidity/1000:.0f}K"
    else:
        liq_str = f"${liquidity:.0f}"
    
    # Format mcap
    if mcap >= 1000000:
        mcap_str = f"${mcap/1000000:.1f}M"
    elif mcap >= 1000:
        mcap_str = f"${mcap/1000:.0f}K"
    else:
        mcap_str = f"${mcap:.0f}"
    
    # Volume multiple
    if change > 0:
        vol_str = f"+{change:.1f}%"
    else:
        vol_str = f"{change:.1f}%"
    
    # DexScreener link
    token_addr = sig.get('token_address', sig.get('pair_address', ''))
    dex_link = f"https://dexscreener.com/solana/{token_addr}" if token_addr else ""
    
    # Format price
    try:
        price_float = float(price) if price != '—' else 0
        if price_float < 0.0001:
            price_str = f"${price_float:.8f}"
        elif price_float < 0.01:
            price_str = f"${price_float:.6f}"
        else:
            price_str = f"${price_float:.4f}"
    except:
        price_str = str(price)[:10]
    
    output = f"""{emoji} {action_text}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 {symbol}
📊 VOL {vol_str}
💎 FDV: {mcap_str} | Liq: {liq_str}
📈 Price: {price_str}
🎯 TP1: +50% | TP2: +100% | Stop: -30%
🔗 {dex_link}"""
    
    return output

def format_trade(trade):
    """Format completed trade in Chris's exact style"""
    symbol = trade.get('token', 'UNKNOWN')
    source = trade.get('source', 'GMGN')
    pnl = trade.get('pnl_sol', 0)
    action = trade.get('action', 'BUY')
    reason = trade.get('exit_reason', 'UNKNOWN')
    token_addr = trade.get('token_address', '')
    dex_link = f"https://dexscreener.com/solana/{token_addr}" if token_addr else ""
    
    # Action emoji
    if action == 'KOL_BUY':
        emoji = '🏐'
        action_text = 'KOL BUY'
    elif action == 'PUMP':
        emoji = '💊'
        action_text = 'PUMP'
    elif action == 'KOTH':
        emoji = '👑'
        action_text = 'KOTH'
    else:
        emoji = '📡'
        action_text = 'SIGNAL'
    
    # Result
    if pnl > 0:
        result = f"✅ WIN +{pnl:.4f} SOL"
    else:
        result = f"❌ LOSS {pnl:.4f} SOL"
    
    # Exit reason
    if reason == 'TP2':
        exit_text = "🎯 TP2 HIT"
    elif reason == 'TP1':
        exit_text = "🎯 TP1 HIT"
    elif reason == 'STOP_LOSS':
        exit_text = "🛑 STOP LOSS"
    elif reason == 'TIME_EXIT':
        exit_text = "⏰ TIME EXIT"
    else:
        exit_text = f"📤 {reason}"
    
    # Buy command
    buy_cmd = f"/buy {token_addr} 0.1 on GMGN bot" if token_addr else ""
    
    output = f"""📊 TRADE COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{emoji} {symbol} ({action_text})
{result} | {exit_text}
🔗 {dex_link}

⚙️ Or: {buy_cmd}"""
    
    return output

def load_history():
    global balance, stats, closed_trades
    if SIM_TRADES_FILE.exists():
        with open(SIM_TRADES_FILE, 'r') as f:
            for line in f:
                if line.strip():
                    t = json.loads(line)
                    closed_trades.append(t)
                    balance += t.get('amount_sol', POSITION_SIZE) + t.get('pnl_sol', 0)
        stats['total_trades'] = len(closed_trades)
        stats['wins'] = sum(1 for t in closed_trades if t.get('pnl_sol', 0) > 0)
        stats['losses'] = sum(1 for t in closed_trades if t.get('pnl_sol', 0) <= 0)
        if closed_trades:
            pnls = [t.get('pnl_sol', 0) for t in closed_trades]
            stats['best'] = max(pnls)
            stats['worst'] = min(pnls)

def save_trade(trade):
    with open(SIM_TRADES_FILE, 'a') as f:
        f.write(json.dumps(trade) + '\n')

def get_recent_signals():
    signals = []
    try:
        for f in sorted(SIGNALS_DIR.glob("gmgn_*.json"), key=lambda x: -x.stat().st_mtime)[:5]:
            try:
                with open(f) as fp:
                    data = json.load(fp)
                    data['_source'] = 'gmgn'
                    signals.append(data)
            except: pass
        for f in sorted(SIGNALS_DIR.glob("dexs_*.json"), key=lambda x: -x.stat().st_mtime)[:5]:
            try:
                with open(f) as fp:
                    data = json.load(fp)
                    data['_source'] = 'dexscreener'
                    signals.append(data)
            except: pass
    except: pass
    return signals

def score_signal(sig):
    """
    Score signal with safety checks
    Returns (score, should_trade)
    """
    score = 0
    src = sig.get('_source', 'dex')
    action = sig.get('action', '')
    change = sig.get('change_pct', 0)
    liquidity = sig.get('liquidity', 0)
    mcap = sig.get('mcap', 0)
    
    # === SAFETY CHECKS (must pass) ===
    safety_issues = []
    
    # Check rug probability
    rug_prob = sig.get('rug_probability', 0)
    if rug_prob > 30:
        safety_issues.append(f"Rug Prob: {rug_prob}%")
    
    # Check top holder %
    top10 = sig.get('top_10_pct', 0)
    if top10 > 50:
        safety_issues.append(f"Top10: {top10}%")
    
    # Check holder count
    holders = sig.get('holders', 999)
    if holders < 10:
        safety_issues.append(f"Holders: {holders}")
    
    # Check dev balance (high = risky)
    dev_bal = sig.get('dev_balance_sol', 0)
    if dev_bal > 5:
        safety_issues.append(f"Dev Balance: {dev_bal} SOL")
    
    # Check age (very new = risky) - only flag if we can confirm it's < 1 min
    age_min = sig.get('age_minutes', 0)
    if age_min > 0 and age_min < 1:  # Less than 1 minute old AND we have valid age data
        safety_issues.append(f"Age: {age_min:.1f}m (too new)")
    
    # If any safety issues, skip or heavily penalize
    if safety_issues:
        print(f"  ⚠️ SAFETY FLAGS: {', '.join(safety_issues)}")
        return 0, False
    
    # === POSITIVE SCORING ===
    # Handle both GMGN format and combined_monitor format
    sig_list = sig.get('signals', [])
    
    # Strong buy signals
    if any(s in sig_list for s in ['BUY_MOMENTUM', 'STRONG_BUY', 'KOL_WALLET', 'STRONG_BUY_PRESSURE']):
        score += 5
    # Pump signals  
    if any(s in sig_list for s in ['HIGH_VOLUME_PUMP', 'PUMP']):
        score += 4
    # Rapid movement
    if 'RAPID_MOVE' in sig_list:
        score += 3
    
    # Also check GMGN-style action field
    if action == 'KOL_BUY':
        score += 5
    if action == 'PUMP':
        score += 3
    if change and change > 50:
        score += 3
    elif change and change > 20:
        score += 1
    
    # Liquidity scoring
    if liquidity and liquidity > 50000:
        score += 2
    if liquidity and liquidity > 100000:
        score += 1
        
    # Small cap preference for pumps
    if mcap and mcap < 100000:
        score += 1
    if mcap and mcap < 50000:
        score += 1
    
    return score, score > 0

def simulate_price_movement(action):
    if action == 'KOL_BUY':
        return random.uniform(0.15, 1.30)
    elif action == 'PUMP':
        return random.uniform(0.20, 1.50)
    elif action == 'KOTH':
        return random.uniform(0.10, 1.20)
    elif action == 'RAPID_MOVE':
        return random.uniform(0.30, 1.10)
    else:
        return random.uniform(-0.10, 0.80)

def check_positions():
    global balance, stats
    
    now = datetime.now()
    closed = []
    
    for pos in positions:
        if pos.get('closed'):
            closed.append(pos)
            continue
        
        action = pos.get('action', 'BUY')
        entry_price = pos.get('entry_price', 0.0001)
        change_pct = simulate_price_movement(action)
        
        # Apply costs to the raw change
        net_change = change_pct - SLIPPAGE - TAX_FEE
        
        # Check TP1
        if net_change >= TP1_PCT and not pos.get('tp1_hit'):
            pos['tp1_hit'] = True
            pnl = (POSITION_SIZE / 2) * net_change
            balance += (POSITION_SIZE / 2) + pnl
            pos['tp1_pnl'] = pnl
            print(f"\n🎯 TP1 HIT! {pos['token']} at +{change_pct*100:.1f}% (net: +{net_change*100:.1f}%) — sold 50%")
        
        # Check TP2
        elif net_change >= TP2_PCT and not pos.get('tp2_hit'):
            pos['tp2_hit'] = True
            pnl = (POSITION_SIZE / 2) * net_change
            balance += (POSITION_SIZE / 2) + pnl
            pos['closed'] = True
            pos['pnl_sol'] = pnl + pos.get('tp1_pnl', 0)
            pos['exit_reason'] = 'TP2'
            pos['closed_at'] = now.isoformat()
            pos['gross_pct'] = change_pct
            pos['net_pct'] = net_change
            closed.append(pos)
            stats['wins'] += 1
            stats['best'] = max(stats['best'], pos['pnl_sol'])
            save_trade(pos)
            
            print(f"\n🎯🎯 TP2 HIT! {pos['token']} at +{change_pct*100:.1f}% (net: +{net_change*100:.1f}%) — FULL EXIT")
            print(f"   💰 Profit: +{pos['pnl_sol']:.4f} SOL")
        
        # Check Stop Loss (after costs)
        elif net_change <= STOP_LOSS:
            pnl = POSITION_SIZE * net_change
            balance += POSITION_SIZE + pnl
            pos['closed'] = True
            pos['pnl_sol'] = pnl
            pos['exit_reason'] = 'STOP_LOSS'
            pos['closed_at'] = now.isoformat()
            pos['gross_pct'] = change_pct
            pos['net_pct'] = net_change
            closed.append(pos)
            stats['losses'] += 1
            stats['worst'] = min(stats['worst'], pnl)
            save_trade(pos)
            
            print(f"\n🛑 STOP LOSS! {pos['token']} at {change_pct*100:.1f}%")
            print(f"   💰 Loss: {pnl:.4f} SOL")
        
        # Time exit (2h, profitable)
        elif pos.get('opened_at'):
            opened = datetime.fromisoformat(pos['opened_at'])
            age_min = (now - opened).total_seconds() / 60
            net_change_for_time = change_pct - SLIPPAGE - TAX_FEE
            if age_min > 120 and net_change_for_time > 0.20:
                pnl = POSITION_SIZE * net_change_for_time
                balance += POSITION_SIZE + pnl
                pos['closed'] = True
                pos['pnl_sol'] = pnl
                pos['exit_reason'] = 'TIME_EXIT'
                pos['closed_at'] = now.isoformat()
                pos['gross_pct'] = change_pct
                pos['net_pct'] = net_change_for_time
                closed.append(pos)
                stats['wins'] += 1
                stats['best'] = max(stats['best'], pnl)
                save_trade(pos)
                
                print(f"\n⏰ TIME EXIT! {pos['token']} at +{change_pct*100:.1f}% (net: +{net_change_for_time*100:.1f}%) after {age_min:.0f}m")
                print(f"   💰 Profit: +{pnl:.4f} SOL")
    
    for pos in closed:
        if pos in positions:
            positions.remove(pos)
    
    stats['total_trades'] = len(closed_trades)

def open_position(signal):
    global balance
    
    if len(positions) >= 3:
        return None
    
    token = signal.get('symbol', signal.get('token_address', 'UNK')[:8])
    
    if any(p.get('token') == token for p in positions):
        return None
    
    entry_price = 0.0001
    pos = {
        'token': token,
        'token_address': signal.get('token_address', ''),
        'amount_sol': POSITION_SIZE,
        'entry_price': entry_price,
        'action': signal.get('action', 'BUY'),
        'source': signal.get('source', signal.get('_source', 'unknown')),
        'opened_at': datetime.now().isoformat(),
        'closed': False,
        'pnl_sol': 0
    }
    
    positions.append(pos)
    balance -= POSITION_SIZE
    
    # Print signal in GMGN format
    print(f"\n{'='*50}")
    print(format_signal(signal))
    print(f"{'='*50}")
    print(f"🟢 BUY {POSITION_SIZE} SOL of {token}")
    print(f"   Entry simulated at ${entry_price:.6f}")
    
    return pos

def print_status():
    total_pnl = sum(t.get('pnl_sol', 0) for t in closed_trades)
    win_rate = (stats['wins'] / max(stats['total_trades'], 1)) * 100
    
    print(f"\n{'='*50}")
    print(f"📊 SIM WALLET STATUS")
    print(f"{'='*50}")
    print(f"💰 Balance: {balance:.4f} SOL")
    print(f"📈 Open: {len(positions)} | Closed: {stats['total_trades']}")
    print(f"✅ Wins: {stats['wins']} | ❌ Losses: {stats['losses']}")
    print(f"📈 Win Rate: {win_rate:.1f}%")
    print(f"💵 Total P&L: {total_pnl:+.4f} SOL")
    print(f"📊 Return: {((balance - INITIAL_BALANCE) / INITIAL_BALANCE * 100):+.2f}%")
    print(f"{'='*50}")

def main():
    global balance, stats
    
    load_history()
    
    print("🎮 TRADING SIMULATOR STARTED")
    print(f"💰 Starting: {balance:.4f} SOL | Target: Beat initial")
    print(f"📊 Rules: TP1 +50% | TP2 +100% | SL -30%")
    print(f"📝 History: {stats['total_trades']} trades ({stats['wins']}W/{stats['losses']}L)")
    
    iteration = 0
    last_status = time.time()
    
    while True:
        iteration += 1
        
        check_positions()
        
        # Try to open new position every 90 seconds
        if iteration % 3 == 0 and len(positions) < 3:
            signals = get_recent_signals()
            
            if signals:
                scored = []
                for s in signals:
                    score, should_trade = score_signal(s)
                    if should_trade:
                        scored.append((score, s))
                scored.sort(key=lambda x: -x[0])
                
                if scored:
                    score, best = scored[0]
                    pos = open_position(best)
        
        # Print status every 5 minutes
        if time.time() - last_status > 300:
            print_status()
            last_status = time.time()
        
        time.sleep(30)

if __name__ == "__main__":
    main()