#!/usr/bin/env python3
"""
Trading Constants - Wilson v6.8 Strategy
Goal: Turn 1.0 SOL → 100 SOL via compound TP5 winners on pump.fun
"""

# Position sizing
POSITION_SIZE = 0.10      # Per trade
KOL_BUY_POSITION_SIZE = 0.10
MAX_OPEN_POSITIONS = 9     # Max concurrent positions

# === ENTRY FILTERS (v6.8) ===
MIN_MCAP = 8500            # $3.5K floor
MAX_MCAP = 60000           # $60K ceiling
MIN_AGE_SECONDS = 120      # 2 minutes minimum
MAX_AGE_SECONDS = 5400     # 90 minutes maximum
MIN_5MIN_VOLUME = 1000     # 5min volume > $1K
MIN_HOLDERS = 15           # Holders ≥ 15
TOP10_HOLDER_MAX = 50      # Top10% < 50%

# BS Ratio: >0.05 for pairs < 15 min old, >0.8 for all others (v6.8)
BS_RATIO_NEW = 0.05       # BS ratio for pairs < 15 min old
BS_RATIO_OLD = 0.8        # BS ratio for pairs ≥ 15 min old
BS_PUMP_FUN_OK = True      # pump.fun BS=0 is OK if no data

# === MOMENTUM (v6.8) ===
H1_MOMENTUM_MIN = 5        # h1 must be > +5%
H24_MOMENTUM_MIN = 5       # OR 24h must be > +5%

# === CHG1 RULES (v6.8) ===
MIN_CHG1_FOR_BUY = 2.0     # chg1 must be > +2% to buy
CHG1_NONE_M5_REJECT = 5    # chg1=None AND m5 > +5% → REJECT immediately
CHG1_IMPROVEMENT_MIN = 3.0 # chg1 must be > +3% from last check to trigger verify
CHG1_MIN_VALUE = -5.0      # chg1 must be > -5% (no falling knife)

# === DIP/PULLBACK (v6.8) ===
DIP_MIN = 0                # 0% minimum dip
DIP_MAX = 50               # 50% max dip from local peak
ATH_DIVERGENCE_MAX = 55    # 55% max below ATH

# === COOLDOWN RULES (v6.8) ===
# Unified: m5 > -5% → 45s cooldown for ALL tokens (YOUNG and OLD)
PUMP_5M_THRESHOLD = -5     # m5 > -5% triggers cooldown
BASE_COOLDOWN = 45          # 45s base cooldown

# After cooldown:
# - chg1 < -5%: continue watching, need chg1 to reach +3% improvement to enter verify
# - chg1 >= -5%: no deterioration check, enter verify if improving +3%

CHG1_RECHECK_DELAY = 15     # 15s between rechecks
CHG1_VERIFY_DELAY = 15      # 15s verification after trigger

# Deterioration: chg1 drops >3% from last check in verify → reject
CHG1_DROP_REJECT = 3.0

# Consecutive rechecks in verify before buy
VERIFY_CONSECUTIVE_OK = 2  # 2 consecutive rechecks with +3% improvement = BUY

# Max rechecks before temp reject
MAX_RECHECKS = 15          # 15 × 15s = ~3.75 min max
REJECTED_REVISIT_DELAY = 120  # 2 minutes before circling back

# === PRICE STABILITY CHECK (v6.8 - BEFORE BUY) ===
PRICE_DROP_REJECT = 3      # >3% price drop since last check → reject after 3 consecutive
PRICE_DROP_WAIT_1 = 30     # first wait 30s
PRICE_DROP_WAIT_2 = 30     # second wait 30s
PRICE_DROP_WAIT_3 = 90     # third wait 90s
MCAP_INCREASE_CONFIRM = 2  # mcap must increase >2% from lowest to confirm

# === INSTABILITY REJECTION (v6.8) ===
H1_INSTABILITY_MULTIPLIER = 3

# === ANTI-PATTERNS (v6.8) ===
H1_PARABOLIC_REJECT = 999999  # No h1 cap — let winners run

# === LIQUIDITY (v6.8) ===
LIQUIDITY_MCAP_THRESHOLD = 60000  # $60K threshold for liq monitoring
LIQUIDITY_MIN = 1000

# === EXIT PLAN (v6.8) ===
TP1_PERCENT = 50
TP1_TRAILING_PCT = 40
TP1_SELL_PCT = 0           # HOLD at TP1

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
TP5_SELL_PCT = 10

TRAILING_STOP_PCT = 40
STOP_LOSS_PERCENT = -25     # -25% stop loss

EXIT_PLAN_TEXT = f"""🎯 Exit Plan v6.8:
+{TP1_PERCENT}% → HOLD, trail {TP1_TRAILING_PCT}%
+{TP2_PERCENT}% → Sell {TP2_SELL_PCT}%, trail {TP2_TRAILING_PCT}%
+{TP3_PERCENT}% → Sell {TP3_SELL_PCT}%, trail {TP3_TRAILING_PCT}%
+{TP4_PERCENT}% → Sell {TP4_SELL_PCT}%, trail {TP4_TRAILING_PCT}%
+{TP5_PERCENT}% → Sell remaining {TP5_SELL_PCT}%, trail {TP5_TRAILING_PCT}%
⚠️ Stop: {STOP_LOSS_PERCENT}%"""

# === LOW VOLUME EXIT ===
LOW_VOLUME_THRESHOLD = 600

# === EXCHANGE VALIDATION (v6.8) ===
ALLOWED_EXCHANGES = {'pumpfun', 'pumpswap', 'raydium'}
REJECTED_EXCHANGES = {'meteora', 'orinoco', 'lifinity', 'saber'}

# === SIMULATION RESET ===
SIM_RESET_TIMESTAMP = '2026-04-14T17:54:54.000000+00:00'
CHRIS_STARTING_BALANCE = 1.0

# === SCAN INTERVALS ===
SCAN_INTERVAL = 15
MONITOR_INTERVAL = 5
ALERT_INTERVAL = 30

# === API ===
MAX_RETRIES = 3
CIRCUIT_BREAKER_THRESHOLD = 5
CIRCUIT_BREAKER_WAIT = 300

# === COOLDOWN STATES (v6.8) ===
STATE_COOLDOWN = 'COOLDOWN'
STATE_WAITING = 'WAITING'
STATE_VERIFICATION = 'VERIFICATION'
