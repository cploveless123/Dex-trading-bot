#!/usr/bin/env python3
"""
Trading Constants - Wilson v6.4 Strategy
Goal: Turn 1.0 SOL → 100 SOL via compound TP5 winners on pump.fun
"""

# Position sizing
POSITION_SIZE = 0.10      # Per trade
KOL_BUY_POSITION_SIZE = 0.10
MAX_OPEN_POSITIONS = 9     # Max concurrent positions

# === ENTRY FILTERS (v6.4) ===
MIN_MCAP = 1000            # $1K floor
MAX_MCAP = 75000           # $75K ceiling
MIN_AGE_SECONDS = 120      # 2 minutes minimum
MAX_AGE_SECONDS = 5400     # 90 minutes maximum
MIN_5MIN_VOLUME = 1000     # 5min volume > $1K
MIN_24H_VOLUME = 0         # No 24h volume minimum
MIN_HOLDERS = 10           # Holders ≥ 10 (v6.4)
TOP10_HOLDER_MAX = 50      # Top10% < 50%

# BS Ratio: >0.05 for pairs < 15 min old, >0.8 for all others (v6.4)
BS_RATIO_NEW = 0.05         # BS ratio for pairs < 15 min old
BS_RATIO_OLD = 0.8        # BS ratio for pairs ≥ 15 min old
BS_PUMP_FUN_OK = True      # pump.fun BS=0 is OK

# === MOMENTUM (v6.4) ===
# REQUIRED: h1 > +30% OR 24h > +30%
H1_MOMENTUM_MIN = 30      # h1 must be > +30%
H24_MOMENTUM_MIN = 30     # OR 24h must be > +30%

# === CHG1 RULES (v6.4) ===
MIN_CHG1_FOR_BUY = 2.0    # chg1 must be > +2% to buy
CHG1_DROP_THRESHOLD = 3    # if chg1 drops by >3% from previous → continue watching
CHG1_NONE_M5_REJECT = 15  # chg1=None AND m5 > +15% → REJECT immediately
CHG1_COOLDOWN_TRIGGER = 5 # chg1 must reach >+5% during cooldown to proceed

# === DIP/PULLBACK (v6.4) ===
DIP_MIN = 5               # 5% minimum dip from local peak
DIP_MAX = 45              # 45% maximum dip from local peak
ATH_DIVERGENCE_MIN = 5    # Must be >5% below ATH

# === COOLDOWN RULES (v6.4) ===
# Young (<15 min) + chg5 > +25% → 30s cooldown
YOUNG_PUMP_5M_THRESHOLD = 25
YOUNG_COOLDOWN = 30
# Older (>15 min) + chg5 > +5% → 30s cooldown
OLD_PUMP_5M_THRESHOLD = 5
ATH_DIVERGENCE_REJECT = 40       # reject if >40% below ATH (parabolic)
OLD_COOLDOWN = 30
# chg1 must reach >+5% to proceed; if <+5%, wait extra 15s and keep checking
CHG1_COOLDOWN_EXTRA = 15  # extra wait if chg1 < +5%
CHG1_COOLDOWN_VERIFY = 15 # final 15s verification wait
MAX_RECHECKS = 15               # Max 15 rechecks (3 min) before skip
RECHECK_DELAY = 15              # 15s between rechecks

# === PRICE STABILITY CHECK (v6.4) ===
PRICE_DROP_THRESHOLD = 5    # >5% price drop since last check
PRICE_DROP_WAIT_1 = 5       # first wait
PRICE_DROP_WAIT_2 = 10      # second wait
PRICE_DROP_WAIT_3 = 30      # third wait
MCAP_INCREASE_CONFIRM = 5   # mcap must increase >5% from lowest to confirm

# === INSTABILITY REJECTION (v6.4) ===
# If h1 changes by >3x between rechecks → reject
H1_INSTABILITY_MULTIPLIER = 3

# === ANTI-PATTERNS (v6.4) ===
H1_PARABOLIC_REJECT = 833  # h1 >+833% → reject (too parabolic)
FALLING_KNIFE_CONSECUTIVE = 3

# === LIQUIDITY (v6.4) ===
# mcap < $60K: no check (pump.fun building)
# mcap > $70K: DO liquidity checks — if liq <$1K, sell immediately
LIQUIDITY_MCAP_THRESHOLD = 70000  # $70K threshold for liq monitoring
LIQUIDITY_MIN = 1000

# === EXIT PLAN (v6.4) ===
# TP1: +50% → HOLD (no sell), 40% trailing stop activates
# TP2: +100% → Sell 40%, trail 35%
# TP3: +200% → Sell 30%, trail 35%
# TP4: +300% → Sell 20%, trail 35%
# TP5: +1000% → Sell remaining 10%, trail 30%
# Stop: -20%

TP1_PERCENT = 50
TP1_TRAILING_PCT = 40
TP1_SELL_PCT = 0           # HOLD at TP1, no sell

TP2_PERCENT = 100
TP2_TRAILING_PCT = 35
TP2_SELL_PCT = 40

TP3_PERCENT = 200
TP3_TRAILING_PCT = 35
TP3_SELL_PCT = 30

TP4_PERCENT = 300
TP4_TRAILING_PCT = 35
TP4_SELL_PCT = 20

TP5_PERCENT = 1000
TP5_TRAILING_PCT = 30
TP5_SELL_PCT = 10          # remaining 10%

TRAILING_STOP_PCT = 40      # 40% from peak after TP1
STOP_LOSS_PERCENT = -20     # -20% stop (NON-NEGOTIABLE)

# Slippage & Tax Correction
SLIPPAGE_TAX_COST = 0.025   # ~2.5% per round trip

EXIT_PLAN_TEXT = f"""🎯 Exit Plan v6.4 (Wilson Strategy):
+{TP1_PERCENT}% → HOLD, trail {TP1_TRAILING_PCT}%
+{TP2_PERCENT}% → Sell {TP2_SELL_PCT}%, trail {TP2_TRAILING_PCT}%
+{TP3_PERCENT}% → Sell {TP3_SELL_PCT}%, trail {TP3_TRAILING_PCT}%
+{TP4_PERCENT}% → Sell {TP4_SELL_PCT}%, trail {TP4_TRAILING_PCT}%
+{TP5_PERCENT}% → Sell remaining {TP5_SELL_PCT}%, trail {TP5_TRAILING_PCT}%
⚠️ Stop: {STOP_LOSS_PERCENT}%"""

# === LOW VOLUME EXIT ===
LOW_VOLUME_THRESHOLD = 600   # 5min vol <$600 AND mcap >$60K → exit

# === EXCHANGE VALIDATION (v6.4) ===
ALLOWED_EXCHANGES = {'pumpfun', 'pumpswap', 'raydium'}
REJECTED_EXCHANGES = {'meteora', 'orinoco', 'lifinity', 'saber'}

# GMGN Signal Scorer
MIN_GMGN_SCORE = 50
GMGN_VOL_MCAP_MIN = 0.1

# === BLACKLIST ===
TICKER_BLACKLIST = {'NODES', 'nodes', 'Nodes'}

# === SIMULATION RESET ===
SIM_RESET_TIMESTAMP = '2026-04-14T06:22:19.000000+00:00'  # Fresh reset
CHRIS_STARTING_BALANCE = 1.0

# === SCAN INTERVALS ===
SCAN_INTERVAL = 15         # 15 seconds
MONITOR_INTERVAL = 5       # 5 seconds
ALERT_INTERVAL = 30        # 30 seconds

# === API ===
MAX_RETRIES = 3
CIRCUIT_BREAKER_THRESHOLD = 5
CIRCUIT_BREAKER_WAIT = 300
