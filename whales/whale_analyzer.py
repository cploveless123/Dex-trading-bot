#!/usr/bin/env python3
"""
Whale Strategy Analyzer
Analyzes whale wallets and synthesizes optimal trading strategy
"""
import subprocess
import json
import sys
from datetime import datetime
from collections import defaultdict, Counter

WHALE_DB = "/root/Dex-trading-bot/whales/whale_db.json"

def get_whale_trades(wallet, limit=500):
    """Get whale's trading history via GMGN CLI"""
    r = subprocess.run([
        'gmgn-cli', 'portfolio', 'activity',
        '--chain', 'sol',
        '--wallet', wallet,
        '--limit', str(limit)
    ], capture_output=True, text=True, timeout=30)
    
    if r.returncode != 0:
        return {'error': r.stderr, 'activities': []}
    
    try:
        return json.loads(r.stdout)
    except:
        return {'activities': []}

def get_whale_stats(wallet):
    """Get whale's portfolio stats"""
    r = subprocess.run([
        'gmgn-cli', 'portfolio', 'stats',
        '--chain', 'sol',
        '--wallet', wallet
    ], capture_output=True, text=True, timeout=20)
    
    if r.returncode != 0:
        return {}
    try:
        return json.loads(r.stdout)
    except:
        return {}

def analyze_whale(wallet):
    """Full analysis of a single whale"""
    print(f"🔍 Analyzing {wallet[:8]}...")
    
    data = get_whale_trades(wallet, 500)
    stats = get_whale_stats(wallet)
    activities = data.get('activities', [])
    
    if not activities and 'error' in data:
        return {'error': data['error']}
    
    buys = [a for a in activities if a.get('event_type') == 'buy']
    sells = [a for a in activities if a.get('event_type') == 'sell']
    
    # Basic stats
    total_cost = sum(float(a.get('cost_usd', 0) or 0) for a in activities)
    total_invested = sum(float(a.get('buy_cost_usd', 0) or 0) for a in buys)
    
    # PnL distribution
    pnl_stat = stats.get('pnl_stat', {})
    winrate = pnl_stat.get('winrate', 0)
    avg_hold_hours = float(pnl_stat.get('avg_holding_period', 0)) / 3600
    
    # Mcap buckets
    mcap_buckets = defaultdict(lambda: {'wins':0,'losses':0,'buys':0,'total_cost':0})
    for a in activities:
        mc = float(a.get('market_cap', 0) or 0)
        cost = float(a.get('cost_usd', 0) or 0)
        pnl = float(a.get('pnl_sol', 0) or 0)
        
        if mc < 10000: bucket = "<$10K"
        elif mc < 30000: bucket = "$10K-$30K"
        elif mc < 60000: bucket = "$30K-$60K"
        elif mc < 100000: bucket = "$60K-$100K"
        else: bucket = ">$100K"
        
        mcap_buckets[bucket]['buys'] += 1
        mcap_buckets[bucket]['total_cost'] += cost
        if pnl > 0: mcap_buckets[bucket]['wins'] += 1
        else: mcap_buckets[bucket]['losses'] += 1
    
    # Token frequency
    token_trades = defaultdict(lambda: {'count':0,'buys':0,'sells':0,'symbols':set()})
    for a in activities:
        sym = a.get('token', {}).get('symbol', '?')
        token_trades[sym]['count'] += 1
        token_trades[sym]['symbols'].add(sym)
        if a.get('event_type') == 'buy':
            token_trades[sym]['buys'] += 1
        else:
            token_trades[sym]['sells'] += 1
    
    most_traded = sorted(token_trades.items(), key=lambda x: x[1]['count'], reverse=True)[:20]
    
    # PnL buckets
    pnl_lt5 = pnl_stat.get('pnl_lt_nd5_num', 0)
    pnl_5_0 = pnl_stat.get('pnl_nd5_0x_num', 0)
    pnl_0_2 = pnl_stat.get('pnl_0x_2x_num', 0)
    pnl_2_5 = pnl_stat.get('pnl_2x_5x_num', 0)
    pnl_gt5 = pnl_stat.get('pnl_gt_5x_num', 0)
    
    return {
        'wallet': wallet,
        'analyzed_at': datetime.utcnow().isoformat(),
        'native_balance': float(stats.get('native_balance', 0)),
        'realized_profit': float(stats.get('realized_profit', 0)),
        'buy_count': len(buys),
        'sell_count': len(sells),
        'unique_tokens': len(token_trades),
        'winrate': winrate,
        'avg_hold_hours': avg_hold_hours,
        'total_cost': total_cost,
        'mcap_buckets': dict(mcap_buckets),
        'most_traded': [(sym, d['count'], d['buys'], d['sells']) for sym, d in most_traded],
        'pnl_distribution': {
            '<-50%': pnl_lt5,
            '-50% to 0%': pnl_5_0,
            '0% to 100%': pnl_0_2,
            '100% to 500%': pnl_2_5,
            '>500%': pnl_gt5
        },
        'tags': stats.get('tags', []),
        'created_tokens': stats.get('common', {}).get('created_token_count', 0)
    }

def load_whale_db():
    try:
        with open(WHALE_DB) as f:
            return json.load(f)
    except:
        return {'whales': [], 'synthesis': {}}

def save_whale_db(db):
    with open(WHALE_DB, 'w') as f:
        json.dump(db, f, indent=2)

def synthesize_strategy(whales):
    """Find common patterns and outliers across all whales"""
    if len(whales) < 1:
        return {}
    
    # Aggregate mcap preferences
    total_buys_by_bucket = defaultdict(lambda: {'buys':0,'wins':0,'losses':0})
    for w in whales:
        for bucket, data in w.get('mcap_buckets', {}).items():
            total_buys_by_bucket[bucket]['buys'] += data['buys']
            total_buys_by_bucket[bucket]['wins'] += data['wins']
            total_buys_by_bucket[bucket]['losses'] += data['losses']
    
    # Calculate combined WR by bucket
    mcap_preference = {}
    for bucket, data in total_buys_by_bucket.items():
        total = data['wins'] + data['losses']
        wr = data['wins'] / total if total > 0 else 0
        mcap_preference[bucket] = {
            'buys': data['buys'],
            'winrate': wr,
            'wins': data['wins'],
            'losses': data['losses']
        }
    
    # Find best mcap range (highest combined WR weighted by trades)
    best_buckets = sorted(mcap_preference.items(), key=lambda x: x[1]['winrate'], reverse=True)
    
    # Aggregate PnL distribution
    total_pnl_dist = defaultdict(int)
    total_trades = 0
    for w in whales:
        for label, count in w.get('pnl_distribution', {}).items():
            total_pnl_dist[label] += count
            total_trades += count
    
    # Average win rate
    avg_winrate = sum(w.get('winrate', 0) for w in whales) / len(whales)
    
    # Average hold time
    avg_hold = sum(w.get('avg_hold_hours', 0) for w in whales) / len(whales)
    
    # Style classification
    styles = []
    for w in whales:
        if w.get('avg_hold_hours', 0) < 2:
            styles.append('fast_cycle')
        elif w.get('winrate', 0) > 0.5:
            styles.append('high_wr')
        else:
            styles.append('momentum')
    
    # Common traded tokens
    all_tokens = []
    for w in whales:
        for sym, count, _, _ in w.get('most_traded', [])[:10]:
            all_tokens.append(sym)
    
    token_freq = Counter(all_tokens)
    common_tokens = [t for t, c in token_freq.most_common(15)]
    
    return {
        'synthesized_at': datetime.utcnow().isoformat(),
        'whales_analyzed': len(whales),
        'avg_winrate': avg_winrate,
        'avg_hold_hours': avg_hold,
        'mcap_preference': mcap_preference,
        'best_mcap_range': [b[0] for b in best_buckets[:3]],
        'pnl_distribution': dict(total_pnl_dist),
        'trading_styles': dict(Counter(styles)),
        'common_tokens': common_tokens
    }

def main():
    if len(sys.argv) < 2:
        print("Usage: whale_analyzer.py <wallet_address>")
        print("  Analyzes whale and adds to strategy database")
        sys.exit(1)
    
    wallet = sys.argv[1]
    
    # Analyze whale
    result = analyze_whale(wallet)
    
    if 'error' in result:
        print(f"❌ Error: {result['error']}")
        sys.exit(1)
    
    print(f"\n✅ Analysis complete for {wallet[:8]}...")
    print(f"   Win rate: {result['winrate']*100:.1f}%")
    print(f"   Realized PnL: {result['realized_profit']:+.2f} SOL")
    print(f"   Avg hold: {result['avg_hold_hours']:.1f}h")
    print(f"   Unique tokens: {result['unique_tokens']}")
    
    # Load DB, add whale, synthesize
    db = load_whale_db()
    
    # Check if already exists
    existing = [i for i, w in enumerate(db.get('whales', [])) if w.get('wallet') == wallet]
    if existing:
        db['whales'][existing[0]] = result
        print(f"   Updated existing entry")
    else:
        db['whales'].append(result)
        print(f"   Added to whale DB")
    
    # Re-synthesize strategy
    db['synthesis'] = synthesize_strategy(db['whales'])
    
    save_whale_db(db)
    
    # Print synthesis
    syn = db['synthesis']
    print(f"\n📊 SYNTHESIZED STRATEGY ({syn['whales_analyzed']} whales):")
    print(f"   Avg win rate: {syn['avg_winrate']*100:.1f}%")
    print(f"   Avg hold time: {syn['avg_hold_hours']:.1f}h")
    print(f"   Best mcap range: {syn['best_mcap_range']}")
    print(f"   Common tokens: {syn['common_tokens'][:5]}")
    
    print(f"\n💾 Saved to {WHALE_DB}")

if __name__ == '__main__':
    main()
