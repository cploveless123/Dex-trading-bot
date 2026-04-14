#!/usr/bin/env python3
"""
Trading Constants - Wilson v6.0 Strategy (UPDATED)
Goal: Turn 1.0 SOL → 100 SOL via compound TP5 winners on pump.fun
"""

# Position sizing
POSITION_SIZE = 0.10      # Per trade
KOL_BUY_POSITION_SIZE = 0.10
MAX_OPEN_POSITIONS = 9     # Max concurrent positions

# Entry Filters
MIN_MCAP = 4000            # $5K floor
MAX_MCAP = 85000           # $85K ceiling
MIN_AGE_SECONDS = 180      # 3 minutes minimum
MAX_AGE_SECONDS = 10800    # 180 minutes maximum
MIN_5MIN_VOLUME = 1000    # 5min volume > $1K
MIN_VOLUME = 10000         # 24h volume > $10K
MIN_HOLDERS = 15           # Holders ≥ 15
MIN_BS_RATIO = 1.5         # Buy/sell ratio ≥ 1.5
TOP10_HOLDER_MAX = 50      # Top10% < 50%
BS_RATIO_NEW = 0.1        # BS ratio for pairs < 10 min old
BS_RATIO_OLD = 0.8        # BS ratio for pairs > 10 min old
BS_PUMP_FUN_OK = True      # pump.fun BS=0 is OK
ATH_DIVERGENCE_REJECT = 40  # Reject if >40% from ATH
MIN_GMGN_SCORE = 50         # Only buy high quality GMGN signals
GMGN_VOL_MCAP_MIN = 0.1    # Minimum vol/mcap ratio for GMGN signals

# Exit Plan v6.0 - Hold through TP1, let winners run to TP5
TP1_PERCENT = 50           # +50% → Sell 10%, trail 40%
TP1_TRAILING_PCT = 40
TP1_SELL_PCT = 0           # Sell 10% at TP1
TP2_PERCENT = 100          # +100% → Sell 36%, trail 30%
TP2_TRAILING_PCT = 35
TP2_SELL_PCT = 40
TP3_PERCENT = 200          # +200% → Sell 30%, trail 30%
TP3_TRAILING_PCT = 35
TP3_SELL_PCT = 30
TP4_PERCENT = 300          # +300% → Sell 20%, trail 30%
TP4_TRAILING_PCT = 35
TP4_SELL_PCT = 20
TP5_PERCENT = 1000         # +1000% → Sell 8%, trail 15%
TP5_TRAILING_PCT = 30
TP5_SELL_PCT = 10
TRAILING_STOP_PCT = 40      # 40% from peak on remaining after TP1
STOP_LOSS_PERCENT = -25     # -25% stop (NON-NEGOTIABLE)

# Slippage & Tax Correction
SLIPPAGE_TAX_COST = 0.025   # ~2.5% per round trip

# Real net exit percentages (after tax)
REAL_TP1_PCT = round(TP1_PERCENT * (1 - SLIPPAGE_TAX_COST), 1)
REAL_TP2_PCT = round(TP2_PERCENT * (1 - SLIPPAGE_TAX_COST), 1)
REAL_STOP_PCT = round(STOP_LOSS_PERCENT * (1 + SLIPPAGE_TAX_COST), 1)

EXIT_PLAN_TEXT = f"""🎯 Exit Plan v6.2 (Wilson Strategy):
+{TP1_PERCENT}% → HOLD, trail {TP1_TRAILING_PCT}%
+{TP2_PERCENT}% → Sell {TP2_SELL_PCT}%, trail {TP2_TRAILING_PCT}%
+{TP3_PERCENT}% → Sell {TP3_SELL_PCT}%, trail {TP3_TRAILING_PCT}%
+{TP4_PERCENT}% → Sell {TP4_SELL_PCT}%, trail {TP4_TRAILING_PCT}%
+{TP5_PERCENT}% → Sell remaining {TP5_SELL_PCT}%, trail {TP5_TRAILING_PCT}%
⚠️ Stop: {STOP_LOSS_PERCENT}%"""

# Dip / Pullback Detection
DIP_MIN = 10              # 15% minimum dip
DIP_MAX = 45              # v6.0: 45% maximum (from local peak)
PARABOLIC_DIP_EXCEPTION = 5  # h1 >+100% AND age <15min → allow dip as low as 5%
PEAK_WINDOW_SECONDS = 60
PEAK_WINDOW_NEW = 90       # Peak window for new pairs (<15 min)
PEAK_WINDOW_OLD = 180     # Peak window for older pairs (>15 min)

# Cooldown rules (v6.0)
NEW_PUMP_COOLDOWN = 120    # Young (<15 min) + chg5 >+50% → 120s
OLD_PUMP_COOLDOWN = 120    # Older (>15 min) + chg5 >+1% → 120s
NEW_PUMP_5M_THRESHOLD = 50  # chg5 >+50% triggers cooldown for young coins
OLD_PUMP_5M_THRESHOLD = 1   # chg5 >+1% triggers cooldown for older coins
NEW_PUMP_HS1_THRESHOLD = 5  # chg1 >+5% triggers cooldown for young coins
MAX_RECHECKS = 15          # Max 15 rechecks (3 min) before skip
RECHECK_DELAY = 15          # 15s between rechecks

# Anti-momentum: chg5 >+15% AND chg1 <-3% → REJECT
ANTI_MOMENTUM_5M_THRESHOLD = 15  # chg5 >+15%
ANTI_MOMENTUM_CHG1_THRESHOLD = -3  # AND chg1 <-3%

# Chg1 momentum check
MIN_CHG1_FOR_BUY = 5.0  # chg1 must be > +5% to confirm momentum
CHG1_DROP_THRESHOLD = 50  # if chg1 drops by >50% from previous, reject (deterioration)

# Parabolic rejection
H1_PARABOLIC_REJECT = 833  # h1 >+833% → reject (too parabolic)

# Falling knife detection
FALLING_KNIFE_CONSECUTIVE = 3  # 3 consecutive drops + chg1<0 → reject

# Liquidity rule
LIQUIDITY_MCAP_THRESHOLD = 60000  # mcap >$60K requires >$1K liq
LIQUIDITY_MIN = 1000

# Low Volume Exit
LOW_VOLUME_THRESHOLD = 600   # 5min vol <$600 AND mcap >$60K → exit

# Exchange validation
ALLOWED_EXCHANGES = {'pump', 'raydium', 'pumpswap'}
REJECTED_EXCHANGES = {'meteora', 'orinoco', 'lifinity', 'saber'}

# Ticker blacklist
TICKER_BLACKLIST = {'NODES', 'nodes', 'Nodes'}

# Simulation - RESET TO 1.0 SOL
SIM_RESET_TIMESTAMP = '2026-04-14T03:31:06.299431+00:00'  # Fresh start v6.0
CHRIS_STARTING_BALANCE = 1.0

# Scan intervals
SCAN_INTERVAL = 15        # 15 seconds
MONITOR_INTERVAL = 5       # 5 seconds
ALERT_INTERVAL = 30        # 30 seconds

# API Rate Limiting
MAX_RETRIES = 3
CIRCUIT_BREAKER_THRESHOLD = 5
CIRCUIT_BREAKER_WAIT = 300
