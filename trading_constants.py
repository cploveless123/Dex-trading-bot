#!/usr/bin/env python3
"""
Trading Constants - v1.5 Strategy
Goal: Turn 1.0 SOL → 100 SOL via compound pump.fun trades
"""

# Position sizing
POSITION_SIZE = 0.10      # Per trade
KOL_BUY_POSITION_SIZE = 0.10
MAX_OPEN_POSITIONS = 9     # Max concurrent positions

# Entry Filters
MIN_MCAP = 3000            # $3K floor (v5.1)
MAX_MCAP = 95000           # $95K ceiling
MIN_VOLUME = 5000          # 24h volume (kept for compatibility)
MIN_5MIN_VOLUME = 1000     # 5min volume > $1K
MIN_HOLDERS = 15           # Holders > 15
TOP10_HOLDER_MAX = 50      # Top10% < 50% (ignore if 0)
MIN_BS_RATIO = 1.5         # BS ratio (kept for compatibility)

# BS ratio
MIN_BS_NEW = 0.2          # Pairs <5 min old
MIN_BS_OLD = 0.9          # Pairs >5 min old

# Exit Plan v5.3 - More room for winners
TP1_PERCENT = 35           # +35% → sell 10%, trail 30%
TP1_TRAILING_PCT = 30
TP1_SELL_PCT = 10
TP2_PERCENT = 100          # +100% → sell 30%, trail 30%
TP2_TRAILING_PCT = 30
TP2_SELL_PCT = 30
TP3_PERCENT = 200          # +200% → sell 30%, trail 30%
TP3_TRAILING_PCT = 30
TP3_SELL_PCT = 30
TP4_PERCENT = 300          # +300% → sell 20%
TP4_TRAILING_PCT = 20
TP4_SELL_PCT = 20
TP5_PERCENT = 1000         # +1000% → sell remaining 10%
TP5_TRAILING_PCT = 20
TP5_SELL_PCT = 10
TRAILING_STOP_PCT = 20    # 20% from peak on remaining
STOP_LOSS_PERCENT = -25    # -25% stop (more room)

# Slippage & Tax Correction
SLIPPAGE_TAX_COST = 0.025   # ~2.5% per round trip

# Real net exit percentages (after tax)
REAL_TP1_PCT = round(TP1_PERCENT * (1 - SLIPPAGE_TAX_COST), 1)
REAL_TP2_PCT = round(TP2_PERCENT * (1 - SLIPPAGE_TAX_COST), 1)
REAL_STOP_PCT = round(STOP_LOSS_PERCENT * (1 + SLIPPAGE_TAX_COST), 1)

EXIT_PLAN_TEXT = f"""🎯 Exit Plan (tax-adjusted):
+{TP1_PERCENT}% → Sell {TP1_SELL_PCT}%, trail {TP1_TRAILING_PCT}%
+{TP2_PERCENT}% → Sell {TP2_SELL_PCT}%, trail {TP2_TRAILING_PCT}%
+{TP3_PERCENT}% → Sell {TP3_SELL_PCT}%, trail {TP3_TRAILING_PCT}%
+{TP4_PERCENT}% → Sell {TP4_SELL_PCT}%, trail {TP4_TRAILING_PCT}%
+{TP5_PERCENT}% → Sell {TP5_SELL_PCT}%, trail {TP5_TRAILING_PCT}%
⚠️ Stop: {STOP_LOSS_PERCENT}% (net: {REAL_STOP_PCT}% after {SLIPPAGE_TAX_COST*100}% tax/slippage)"""

# Dip / Pullback Detection
# New (<5 min): dip 10-50%, h1 >+50%, 5min >-10%
# Older (>5 min): dip 10-50%, 24hr >+25%, h1 >-39%, 5min >-39%
DIP_MIN = 15
DIP_MAX = 35
PEAK_WINDOW_SECONDS = 60   # Peak = highest price in first 60 seconds
PEAK_WINDOW_NEW = 90       # Peak window for new pairs (<10 min) - v5.1
PEAK_WINDOW_OLD = 180      # Peak window for older pairs (>10 min) - v5.1

# Cooldown rules (avoid parabolic tops)
# New (<5 min): h1 >+100% → wait 60s before buying
# Older (>5 min): 5min >+1% → wait 120s before buying
NEW_PUMP_COOLDOWN = 60     # seconds (was 45)
OLD_PUMP_COOLDOWN = 120     # seconds (was 90)
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
SIM_RESET_TIMESTAMP = '2026-04-11T01:50:00.000000'  # Fresh start at 1.0 SOL
CHRIS_STARTING_BALANCE = 1.0

# Scan intervals
SCAN_INTERVAL = 15        # 15 seconds
MONITOR_INTERVAL = 5        # 5 seconds
ALERT_INTERVAL = 30        # 30 seconds

# API Rate Limiting
MAX_RETRIES = 3
CIRCUIT_BREAKER_THRESHOLD = 5
CIRCUIT_BREAKER_WAIT = 300
