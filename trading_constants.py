#!/usr/bin/env python3
"""
Trading Constants - Wilson v6.6 Strategy
Goal: Turn 1.0 SOL → 100 SOL via compound TP5 winners on pump.fun
"""

# Position sizing
POSITION_SIZE = 0.10      # Per trade
KOL_BUY_POSITION_SIZE = 0.10
MAX_OPEN_POSITIONS = 9     # Max concurrent positions

# === ENTRY FILTERS (v6.6) ===
MIN_MCAP = 5000            # $5K floor
MAX_MCAP = 60000           # $60K ceiling
MIN_AGE_SECONDS = 0        # No minimum age
MAX_AGE_SECONDS = 5400     # 90 minutes maximum
MIN_5MIN_VOLUME = 1000     # 5min volume > $1K
MIN_24H_VOLUME = 0         # No 24h volume minimum
MIN_VOLUME = 10000         # GMGN filter: 24h volume > $10K
MIN_HOLDERS = 15           # Holders ≥ 15
TOP10_HOLDER_MAX = 50      # Top10% < 50%

# BS Ratio: >0.15 for pairs < 15 min old, >0.8 for all others (v6.6)
BS_RATIO_NEW = 0.15        # BS ratio for pairs < 15 min old
BS_RATIO_OLD = 0.8         # BS ratio for pairs ≥ 15 min old
MIN_BS_RATIO = 1.5         # GMGN buyer filter: BS ratio ≥ 1.5
BS_PUMP_FUN_OK = True      # pump.fun BS=0 is OK

# === MOMENTUM (v6.6) ===
# REQUIRED: h1 > +5% OR 24h > +5%
H1_MOMENTUM_MIN = 5        # h1 must be > +5%
H24_MOMENTUM_MIN = 5       # OR 24h must be > +5%

# === CHG1 RULES (v6.6) ===
MIN_CHG1_FOR_BUY = 2.0      # chg1 must be > +2% to buy (from local bottom)
CHG1_NONE_M5_REJECT = 5    # chg1=None AND m5 > +5% → REJECT immediately

# === DIP/PULLBACK (v6.6) ===
DIP_MIN = 0                # 0% minimum dip
DIP_MAX = 50               # 50% max dip from local peak
ATH_DIVERGENCE_MAX = 45    # No more than 45% below ATH (ath_distance must be < 45%)

# === COOLDOWN RULES (v6.6) ===
# Trigger: m5 > -5% (any age) → 30s cooldown
YOUNG_PUMP_5M_THRESHOLD = -5
OLD_PUMP_5M_THRESHOLD = -5
YOUNG_COOLDOWN = 30        # Initial 30s cooldown
ATH_DIVERGENCE_REJECT = 50 # reject if >50% below ATH
OLD_COOLDOWN = 30

# CHG1 trigger: chg1 must reach >+1% after cooldown
CHG1_TRIGGER_MIN = 1.0     # chg1 must reach >+1% to proceed
CHG1_RECHECK_DELAY = 15    # 15s between rechecks during waiting
CHG1_VERIFY_DELAY = 15    # 15s verification after chg1 trigger

# Deterioration: chg1 drops >3% from prev → reject (during verify/recovery only)
CHG1_DROP_REJECT = 3.0

# Recovery: chg1 must reach >+2% to resume from deterioration
CHG1_RECOVERY_MIN = 2.0

# Max rechecks before temp reject
MAX_RECHECKS = 20          # Allow more rechecks (20 × 15s = 5 min)
REJECTED_REVISIT_DELAY = 300  # 5 minutes before circling back

# === PRICE STABILITY CHECK (v6.6 - BEFORE BUY) ===
PRICE_DROP_REJECT = 3      # >3% price drop → wait
PRICE_DROP_WAIT_1 = 15     # first wait 15s
PRICE_DROP_WAIT_2 = 30     # second wait 30s
PRICE_DROP_WAIT_3 = 90     # third wait 90s
MCAP_INCREASE_CONFIRM = 2  # mcap must increase >2% from lowest to confirm

# === INSTABILITY REJECTION (v6.6) ===
# If h1 changes by >3x between rechecks → reject
H1_INSTABILITY_MULTIPLIER = 3

# === ANTI-PATTERNS (v6.6) ===
H1_PARABOLIC_REJECT = 999999  # No h1 cap — let winners run
FALLING_KNIFE_CONSECUTIVE = 3

# === LIQUIDITY (v6.6) ===
# mcap < $60K: no check (pump.fun building)
# mcap > $60K: DO liquidity checks — if liq <$1K, sell immediately
LIQUIDITY_MCAP_THRESHOLD = 60000  # $60K threshold for liq monitoring
LIQUIDITY_MIN = 1000

# === EXIT PLAN (v6.6) ===
# TP1: +50% → HOLD (no sell), 40% trailing stop activates
# TP2: +100% → Sell 40%, trail 35%
# TP3: +200% → Sell 30%, trail 35%
# TP4: +300% → Sell 20%, trail 35%
# TP5: +1000% → Sell remaining 10%, trail 30%
# Stop: -25%

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
STOP_LOSS_PERCENT = -25     # -25% stop loss

# Slippage & Tax Correction
SLIPPAGE_TAX_COST = 0.025   # ~2.5% per round trip

EXIT_PLAN_TEXT = f"""🎯 Exit Plan v6.6 (Wilson Strategy):
+{TP1_PERCENT}% → HOLD, trail {TP1_TRAILING_PCT}%
+{TP2_PERCENT}% → Sell {TP2_SELL_PCT}%, trail {TP2_TRAILING_PCT}%
+{TP3_PERCENT}% → Sell {TP3_SELL_PCT}%, trail {TP3_TRAILING_PCT}%
+{TP4_PERCENT}% → Sell {TP4_SELL_PCT}%, trail {TP4_TRAILING_PCT}%
+{TP5_PERCENT}% → Sell remaining {TP5_SELL_PCT}%, trail {TP5_TRAILING_PCT}%
⚠️ Stop: {STOP_LOSS_PERCENT}%"""

# === LOW VOLUME EXIT ===
LOW_VOLUME_THRESHOLD = 600   # 5min vol <$600 AND mcap >$60K → exit

# === EXCHANGE VALIDATION (v6.6) ===
ALLOWED_EXCHANGES = {'pumpfun', 'pumpswap', 'raydium'}
REJECTED_EXCHANGES = {'meteora', 'orinoco', 'lifinity', 'saber'}

# GMGN Signal Scorer
MIN_GMGN_SCORE = 50
GMGN_VOL_MCAP_MIN = 0.1

# === BLACKLIST ===
TICKER_BLACKLIST = {'NODES', 'nodes', 'Nodes'}

# === SIMULATION RESET ===
SIM_RESET_TIMESTAMP = '2026-04-14T14:32:46.000000+00:00'  # Fresh reset v6.6
CHRIS_STARTING_BALANCE = 1.0

# === SCAN INTERVALS ===
SCAN_INTERVAL = 15         # 15 seconds
MONITOR_INTERVAL = 5       # 5 seconds
ALERT_INTERVAL = 30         # 30 seconds

# === API ===
MAX_RETRIES = 3
CIRCUIT_BREAKER_THRESHOLD = 5
CIRCUIT_BREAKER_WAIT = 300

# === COOLDOWN STATES ===
STATE_COOLDOWN = 'COOLDOWN'
STATE_WAITING_CHG1 = 'WAITING_CHG1'
STATE_VERIFICATION = 'VERIFICATION'
STATE_RECOVERY = 'RECOVERY'
