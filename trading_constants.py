#!/usr/bin/env python3
"""
Trading Constants - v1.5 Strategy
Goal: Turn 1.0 SOL → 100 SOL via compound pump.fun trades
"""

# Position sizing
POSITION_SIZE = 0.10      # Per trade
KOL_BUY_POSITION_SIZE = 0.10
MAX_OPEN_POSITIONS = 5     # Max concurrent positions

# Entry Filters
MIN_MCAP = 5000            # $5K floor
MAX_MCAP = 95000           # $95K ceiling
MIN_VOLUME = 5000          # 24h volume (kept for compatibility)
MIN_5MIN_VOLUME = 1000     # 5min volume > $1K
MIN_HOLDERS = 15           # Holders > 15
TOP10_HOLDER_MAX = 50      # Top10% < 50% (ignore if 0)
MIN_BS_RATIO = 1.5         # BS ratio (kept for compatibility)

# BS ratio
MIN_BS_NEW = 0.2          # Pairs <5 min old
MIN_BS_OLD = 0.9          # Pairs >5 min old

# Exit Plan
TP1_PERCENT = 50          # +50% → sell 50%, trail 15%
TP1_TRAILING_PCT = 15
TP1_SELL_PCT = 50
TP2_PERCENT = 150         # +150% → sell 25%
TP2_SELL_PCT = 25
TP3_PERCENT = 0          # +500% removed in v1.7
TP3_SELL_PCT = 0         # removed in v1.7
TRAILING_STOP_PCT = 30    # 30% from peak on remaining
STOP_LOSS_PERCENT = -30    # -30% stop

# Slippage & Tax Correction
SLIPPAGE_TAX_COST = 0.025   # ~2.5% per round trip

# Real net exit percentages (after tax)
REAL_TP1_PCT = round(TP1_PERCENT * (1 - SLIPPAGE_TAX_COST), 1)
REAL_TP2_PCT = round(TP2_PERCENT * (1 - SLIPPAGE_TAX_COST), 1)
REAL_STOP_PCT = round(STOP_LOSS_PERCENT * (1 + SLIPPAGE_TAX_COST), 1)

EXIT_PLAN_TEXT = f"""🎯 Exit Plan (tax-adjusted):
+{TP1_PERCENT}% → Sell {TP1_SELL_PCT}%, trail {TP1_TRAILING_PCT}%
+{TP2_PERCENT}% → Sell {TP2_SELL_PCT}% more
📊 Trailing: {TRAILING_STOP_PCT}% from peak on remaining
⚠️ Stop: {STOP_LOSS_PERCENT}% (net: {REAL_STOP_PCT}% after {SLIPPAGE_TAX_COST*100}% tax/slippage)"""

# Dip / Pullback Detection
# New (<5 min): dip 10-50%, h1 >+50%, 5min >-10%
# Older (>5 min): dip 10-50%, 24hr >+25%, h1 >-39%, 5min >-39%
DIP_MIN = 10
DIP_MAX = 50
PEAK_WINDOW_SECONDS = 60   # Peak = highest price in first 60 seconds

# Cooldown rules (avoid parabolic tops)
# New (<5 min): h1 >+100% → wait 45s before buying
# Older (>5 min): 5min >+1% → wait 90s before buying
NEW_PUMP_COOLDOWN = 45     # seconds
OLD_PUMP_COOLDOWN = 90     # seconds
NEW_PUMP_HS1_THRESHOLD = 100  # h1 >+100% triggers cooldown
OLD_PUMP_5M_THRESHOLD = 1     # 5min >+1% triggers cooldown

# If local peak >40% from ATH → reject (parabolic warning)
ATH_DIVERGENCE_REJECT = 40  # %

# NoMint and Blacklist checks
CHECK_NOMINT = True
CHECK_BLACKLIST = True

# Ticker blacklist
TICKER_BLACKLIST = {'NODES', 'nodes', 'Nodes'}

# Simulation
SIM_RESET_TIMESTAMP = '2026-04-10T19:00:00.000000'  # Fresh start at 1.0 SOL
CHRIS_STARTING_BALANCE = 1.0

# Scan intervals
SCAN_INTERVAL = 15        # 15 seconds
MONITOR_INTERVAL = 5        # 5 seconds
ALERT_INTERVAL = 30        # 30 seconds

# API Rate Limiting
MAX_RETRIES = 3
CIRCUIT_BREAKER_THRESHOLD = 5
CIRCUIT_BREAKER_WAIT = 300
