"""
Trading Constants - Wilson v7 Strategy
Goal: Turn 1.0 SOL → 100 SOL via compound TP5 winners
"""

# Position sizing
POSITION_SIZE = 0.10
MAX_OPEN_POSITIONS = 9

# === ENTRY FILTERS ===
MIN_MCAP = 6000      # $6K floor (raised from $3K)
MAX_MCAP = 60000     # $60K ceiling
MIN_AGE_SECONDS = 120  # 2 minutes minimum
MAX_AGE_SECONDS = 5400  # 90 minutes maximum
MIN_5MIN_VOLUME = 1000  # 5min vol > $1K
MIN_VOLUME = 6000    # Min volume $6K
MIN_HOLDERS = 15
TOP10_HOLDER_MAX = 50  # Top10% < 50%

# Vol/Mcap ratio > 1.0x
VOL_MCAP_RATIO_MIN = 1.0

# BS Ratio
BS_RATIO_NEW = 0.1   # >0.1 for <15min old
BS_RATIO_OLD = 0.8   # >0.8 for older
BS_PUMP_FUN_OK = True  # pump.fun BS=0 is OK if no data

# === MOMENTUM ===
H1_MOMENTUM_MIN = 5   # h1 must be > +5%
H24_MOMENTUM_MIN = 5  # OR 24h must be > +5%

# === PUMP RULE ===
PUMP_CHG5_THRESHOLD = 20.0  # chg5 > +20% triggers pump rule
PUMP_WAIT_1 = 45            # First wait
PUMP_WAIT_2 = 30            # Second wait
PUMP_VERIFY_DELAY = 15      # Final verify

# === DIP/PULLBACK ===
DIP_MIN = 5          # 5% minimum pullback from local peak
DIP_MAX = 45         # 45% max pullback from local peak
ATH_DIVERGENCE_MAX = 55  # Max 55% below ATH

# === CHG5 RULES ===
MIN_CHG5_FOR_BUY = 2.0   # chg5 must be > +2% to buy from local bottom
CHG5_REJECT_DROP = 5.0   # chg5 drops >5% from prev = continue watching
CHG5_RECOVERY_THRESHOLD = 5.0  # chg5 must recover > +5% from lowest mcap

# === COOLDOWN RULES ===
BASE_COOLDOWN = 45        # Default base cooldown
YOUNG_COOLDOWN = 45       # Young (<15min) + chg5 > -5% + h1 > +5%
OLDER_COOLDOWN = 45       # Older (>15min) + chg5 > -5% + h1 > +5%
NORMAL_COOLDOWN = 30      # Otherwise

# Cooldown states
STATE_BASE_WAIT = 'BASE_WAIT'
STATE_RECOVERY_WAIT = 'RECOVERY_WAIT'
STATE_RECOVERY_RECHECK = 'RECOVERY_RECHECK'
STATE_POST_COOLDOWN = 'POST_COOLDOWN'
STATE_VERIFY = 'VERIFY'
STATE_PUMP_WAIT_1 = 'PUMP_WAIT_1'
STATE_PUMP_WAIT_2 = 'PUMP_WAIT_2'
STATE_PUMP_VERIFY = 'PUMP_VERIFY'
STATE_M5_BACKUP = 'M5_BACKUP'

# Timing
CHG1_RECHECK_DELAY = 15    # 15s between rechecks
CHG1_VERIFY_DELAY = 15     # 15s verify
CHG1_RECOVERY_WAIT = 15    # Extra 15s when chg5 < -5%

# Consecutive rechecks before buy
CONSECUTIVE_RECHECKS_REQUIRED = 2

# Max rechecks
MAX_RECHECKS = 15          # 15 × 15s = ~3.75 min max
REJECTED_REVISIT_DELAY = 120  # 2 minutes

# === INSTABILITY ===
H1_INSTABILITY_MULTIPLIER = 3  # h1 changes by >3x = reject

# === LIQUIDITY ===
LIQUIDITY_MCAP_THRESHOLD = 70000  # $70K — mcap above this triggers liq check
LIQUIDITY_MIN = 1000             # $1K — mcap > $70K + liq < $1K = sell
LIQUIDITY_EMERGENCY_THRESHOLD = 1000  # $1K — mcap > $70K + liq < $1K = sell

# === EXIT PLAN ===
TP1_PERCENT = 50
TP1_TRAILING_PCT = 40
TP1_SELL_PCT = 0           # HOLD

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
STOP_LOSS_PERCENT = -25     # -25% stop loss (raised from -20%)

# Low volume exit
LOW_VOLUME_THRESHOLD = 600  # 5min vol < $600 + mcap > $60K = exit

# === EXCHANGE VALIDATION ===
ALLOWED_EXCHANGES = {'pumpfun', 'pumpswap', 'raydium'}
REJECTED_EXCHANGES = {'meteora', 'orinoco', 'lifinity', 'saber'}
PUMP_REQUIREMENTS = {'pumpfun', 'pumpswap'}  # Must end in "pump"

# === SCAN INTERVALS ===
SCAN_INTERVAL = 15
MONITOR_INTERVAL = 5
ALERT_INTERVAL = 30

# === API ===
MAX_RETRIES = 3

# === SIMULATION RESET ===
SIM_RESET_TIMESTAMP = '2026-04-14T21:10:00.000000+00:00'
CHRIS_STARTING_BALANCE = 1.0

EXIT_PLAN_TEXT = f"""TP1 +50%: HOLD (trail 40%)
TP2 +100%: Sell 40% (trail 35%)
TP3 +200%: Sell 30% (trail 35%)
TP4 +300%: Sell 20% (trail 35%)
TP5 +1000%: Sell 10% (trail 30%)
Stop: -25% (trail 40%)"""