#!/usr/bin/env python3
"""
Trading Constants - Shared configuration for all trading scripts

NEW STRATEGY: Based on 16-whale synthesis (55% avg WR)
Goal: Turn 1 SOL to 100 SOL via compounding 2-5x wins
"""

# Position sizing
POSITION_SIZE = 0.05      # Normal position size
KOL_BUY_POSITION_SIZE = 0.10  # KOL_BUY signals: double down
MAX_OPEN_POSITIONS = 5     # Max concurrent positions - aggressive deployment

# Entry Filters - AGGRESSIVE for 100x growth
MIN_MCAP = 15000           # $15K floor - captures early momentum plays
MAX_MCAP = 75000           # $75K ceiling
MIN_VOLUME = 5000          # Minimum 24h volume ($)
MIN_5MIN_VOLUME = 1000     # Minimum 5min volume ($)
MIN_BS_RATIO = 1.5        # BS ratio 1.5+ - momentum only
MIN_HOLDERS = 30           # Holders 30+ - decent distribution
TOP10_HOLDER_MAX = 45     # Max top 10 holder % - prevents honeypots

# GMGN Scoring
MIN_GMGN_SCORE = 55       # Minimum GMGN API score to buy

# Entry criteria
MIN_ENTRY_MCAP = 3000     # Absolute minimum entry mcap ($)
PUMP_FUN_ONLY = False     # Trade pump.fun AND pumpswap tokens

# Exit Plan - HOLD FOR BIGGER WINS
# TP1 at +100%: sell 50% to secure gains
# TP2 at +200%: sell 25% more
# TP3 at +500%: sell remaining 25%
# Trailing: 30% from peak - ride the big ones
TP1_PERCENT = 100         # First target: +100% (was +45%)
TP1_SELL_PCT = 50         # Sell 50% at TP1 (was 74%)
TP2_PERCENT = 200         # Second target: +200%
TP2_SELL_PCT = 25         # Sell 25% more at TP2
TP3_PERCENT = 500         # Third target: +500%
TP3_SELL_PCT = 25         # Sell remaining 25% at TP3
STOP_LOSS_PERCENT = -20   # Stop loss: -20%
TRAILING_STOP_PCT = 30    # Trailing stop: 30% from peak

# Slippage & Tax Correction
SLIPPAGE_TAX_COST = 0.025   # ~2.5% per round trip

# Real net exit percentages (after tax)
REAL_TP1_PCT = round(TP1_PERCENT * (1 - SLIPPAGE_TAX_COST), 1)
REAL_TP2_PCT = round(TP2_PERCENT * (1 - SLIPPAGE_TAX_COST), 1)
REAL_TP3_PCT = round(TP3_PERCENT * (1 - SLIPPAGE_TAX_COST), 1)
REAL_STOP_PCT = round(STOP_LOSS_PERCENT * (1 + SLIPPAGE_TAX_COST), 1)

EXIT_PLAN_TEXT = f"""🎯 Exit Plan:
+{TP1_PERCENT}% → Sell {TP1_SELL_PCT}% of position
+{TP2_PERCENT}% → Sell {TP2_SELL_PCT}% more
+{TP3_PERCENT}% → Sell remaining {TP3_SELL_PCT}%
📊 Trailing: {TRAILING_STOP_PCT}% from peak
⚠️ Stop: {STOP_LOSS_PERCENT}% (net: {REAL_STOP_PCT}% after tax)"""

# Re-entry lockout after close
REENTRY_LOCKOUT_MINUTES = 30
REENTRY_BS_THRESHOLD = 3.0
REENTRY_CHG_THRESHOLD = 60

# Ticker blacklist
TICKER_BLACKLIST = {'NODES', 'nodes', 'Nodes'}

# GMGN Signal Settings
GMGN_SCORE_THRESHOLD = 50
GMGN_VOL_MCAP_MIN = 2.0    # 2x vol/mcap - captures more setups
GMGN_VOL_MCAP_MAX = 15.0

# Simulation reset timestamp
SIM_RESET_TIMESTAMP = '2026-04-08T20:45:00'
CHRIS_STARTING_BALANCE = 1.0   # Reset to 1.0 SOL for fresh tracking

# API Rate Limiting
DEXSCREENER_INTERVAL = 30
SCAN_INTERVAL = 300
GMGN_INTERVAL = 60
MAX_RETRIES = 3
CIRCUIT_BREAKER_THRESHOLD = 5
CIRCUIT_BREAKER_WAIT = 300
