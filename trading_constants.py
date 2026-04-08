#!/usr/bin/env python3
"""
Trading Constants - Shared configuration for all trading scripts
"""

# Position sizing
POSITION_SIZE = 0.05      # Normal position size
KOL_BUY_POSITION_SIZE = 0.10  # KOL_BUY signals: 100% WR - double down      # SOL per trade
MIN_MCAP = 15000           # Minimum market cap ($)
MAX_MCAP = 75000         # Maximum market cap ($) - raised from $100K based on GYAN (+322%)
MIN_VOLUME = 5000         # Minimum 24h volume ($)
MIN_5MIN_VOLUME = 1000    # Minimum 5min volume ($)
MIN_BS_RATIO = 1.5        # Minimum buy/sell ratio
MIN_HOLDERS = 15           # Minimum holder count

# GMGN Scoring
MIN_GMGN_SCORE = 55       # Minimum GMGN API score to buy

# Entry criteria
MIN_ENTRY_MCAP = 3000     # Absolute minimum entry mcap ($)
PUMP_FUN_ONLY = False     # Trade pump.fun AND pumpswap tokens (GYAN was on pumpswap)

# Exit Plan
# TP1: sell % of position to recoup initial investment
# Remaining % trails with trailing stop
TP1_PERCENT = 45          # First take profit level (%)
TP1_SELL_PCT = 74         # % of position to sell at TP1 (recovers initial investment)
TP2_PERCENT = 45          # Trailing stop trigger (% above TP1 peak)
TP2_SELL_PCT = 100        # Sell remaining % at trailing stop
STOP_LOSS_PERCENT = -20   # Stop loss percentage
TRAILING_STOP_PCT = 30    # % drop from peak to trigger trailing stop on remaining position

# Slippage & Tax Correction
# Pump.fun: ~1% buy tax + ~1% sell tax + ~0.5% slippage = ~2.5% total cost per trade
# Real TP1 = TP1_PERCENT - SLIPPAGE_TAX_COST (we capture less profit)
# Real Stop = STOP_LOSS_PERCENT + SLIPPAGE_TAX_COST (stop exits ~2.5% worse)
SLIPPAGE_TAX_COST = 0.025   # 2.5% effective cost per round trip (buy + sell)

# Real net exit percentages (after ~2.5% tax/slippage)
REAL_TP1_PCT = round(TP1_PERCENT * (1 - SLIPPAGE_TAX_COST), 1)
REAL_STOP_PCT = round(STOP_LOSS_PERCENT * (1 + SLIPPAGE_TAX_COST), 1)

EXIT_PLAN_TEXT = f"""🎯 Exit Plan:
+{TP1_PERCENT}% → Sell initial investment (~{TP1_SELL_PCT}% of position)
📊 Trailing stop: sell remaining if {TRAILING_STOP_PCT}% drop from peak
⚠️ Stop: {STOP_LOSS_PERCENT}% (net: {REAL_STOP_PCT}% after tax)"""

# Re-entry lockout after close
REENTRY_LOCKOUT_MINUTES = 30  # Minutes to wait before re-entering after close
REENTRY_BS_THRESHOLD = 3.0    # BS ratio needed to override lockout
REENTRY_CHG_THRESHOLD = 60   # % change needed to override lockout

# Ticker blacklist - tokens that have chased too many times
TICKER_BLACKLIST = {'NODES', 'nodes', 'Nodes'}

# GMGN Signal Settings
GMGN_SCORE_THRESHOLD = 50     # Minimum GMGN score to act on signal
GMGN_VOL_MCAP_MIN = 1.5       # Minimum vol/mcap ratio
GMGN_VOL_MCAP_MAX = 15.0       # Maximum vol/mcap ratio (no upper limit - higher = more momentum)

# Simulation reset timestamp - all trades before this are from old session
SIM_RESET_TIMESTAMP = '2026-04-08T04:34:00'

# API Rate Limiting (prevents bans)
DEXSCREENER_INTERVAL = 30    # Min seconds between DexScreener calls per CA
SCAN_INTERVAL = 300            # Full scan interval (5 min)
GMGN_INTERVAL = 60              # Min seconds between GMGN CLI calls
MAX_RETRIES = 3                # Retries before circuit breaker
CIRCUIT_BREAKER_THRESHOLD = 5  # Failures before extended wait
CIRCUIT_BREAKER_WAIT = 300     # Seconds to wait when tripped
