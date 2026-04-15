## === ENTRY FILTERS ===
MIN_MCAP = 6000
MAX_MCAP = 55000
MIN_AGE_SECONDS = 180      # 3 min
MAX_AGE_SECONDS = 5400     # 90 min
MIN_HOLDERS = 15
TOP10_HOLDER_MAX = 50
VOL_MCAP_RATIO_MIN = 1.0

# Momentum
H1_MOMENTUM_MIN = 5.0     # h1 must be > +5% OR h24 must be > +5%
H24_MOMENTUM_MIN = 5.0
CHG1_MIN = -5.0            # No falling knife - chg1 must be > -5%

# Pump rule - chg5 > +20% triggers pump path
PUMP_CHG5_THRESHOLD = 20.0  # chg5 must be > +20% to trigger pump rule
PUMP_WAIT_1 = 45           # Wait 45s then recheck
PUMP_WAIT_2 = 30           # Wait 30s more
PUMP_VERIFY_DELAY = 15     # Final 15s verification

# Dip / Pullback
DIP_MIN = 5                # 5% minimum dip from local peak
DIP_MAX = 45               # 45% maximum dip
ATH_DIVERGENCE_MAX = 65    # Max 65% from ATH

# chg5 rules
MIN_CHG5_FOR_BUY = 2.0     # chg5 must be > +2% to buy from local bottom
CHG5_DROP_THRESHOLD = 5.0  # If chg5 drops by >5% from previous → deterioration
CHG5_RECOVERY_CHECK = 5.0  # Watch for chg5 > +5% recovery
CHG5_RECHECK_DELAY = 15     # 15s intervals during deterioration

# Cooldowns
YOUNG_COOLDOWN = 45         # Young (<15min) + momentum + chg5 > -5%
YOUNG_AGE_THRESHOLD = 900  # 15 min in seconds
OLDER_COOLDOWN = 45        # Older (>15min) + momentum + chg5 > -5%
NORMAL_COOLDOWN = 30       # Otherwise baseline wait

# State machine wait times
STATE_PUMP_WAIT_1 = 45     # Pump path: 45s wait
STATE_PUMP_WAIT_2 = 30    # Pump path: 30s wait
STATE_PUMP_VERIFY = 15     # Pump path: 15s final verify
STATE_RECOVERY_WAIT = 15   # Deterioration: 15s rechecks
STATE_POST_COOLDOWN = 15    # Post-cooldown: 15s verify
STATE_BASE_WAIT = 30       # Normal: 30s rechecks

# H1 instability
H1_INSTABILITY_MULTIPLIER = 3.0  # If h1 changes by >3x between rechecks → reject

# Liquidity emergency
LIQUIDITY_EMERGENCY_THRESHOLD = 1000  # If mcap > $70K and liq < $1K → emergency sell
LIQUIDITY_MCAP_THRESHOLD = 70000

# === EXIT PLAN ===
TP1_PERCENT = 50
TP1_TRAILING_PCT = 40
TP1_SELL_PCT = 0           # HOLD - watch only, let ride

TP2_PERCENT = 100
TP2_TRAILING_PCT = 30
TP2_SELL_PCT = 35

TP3_PERCENT = 200
TP3_TRAILING_PCT = 30
TP3_SELL_PCT = 35

TP4_PERCENT = 300
TP4_TRAILING_PCT = 30
TP4_SELL_PCT = 20

TP5_PERCENT = 1000
TP5_TRAILING_PCT = 20
TP5_SELL_PCT = 10

TRAILING_STOP_PCT = 40     # 40% trailing stop from peak
STOP_LOSS_PERCENT = -30    # -30% stop loss

# Volume
MIN_5MIN_VOLUME = 1000
MIN_VOLUME = 6000

# Buy/Sell Ratio
BS_RATIO_NEW = 0.1         # <15 min old
BS_RATIO_OLD = 0.8         # >15 min old
BS_PUMP_FUN_OK = True      # pump.fun BS=0 is OK

# Exchange
ALLOWED_EXCHANGES = ['pump', 'raydium', 'pumpswap']
PUMP_REQUIREMENTS = {'pump': 'pump', 'pumpswap': 'pump', 'raydium': None}

# Re-entry lockout
REENTRY_LOCKOUT = 1800     # 30 min in seconds

# System
SIM_RESET_TIMESTAMP = "2026-04-15T13:01:59.845959+00:00"
CHRIS_STARTING_BALANCE = 1.0
POSITION_SIZE = 0.1
MAX_OPEN_POSITIONS = 5
TRADES_FILE = "trades/sim_trades.jsonl"
PERM_BLACKLIST_FILE = "permanent_blacklist.json"
LOW_VOLUME_THRESHOLD = 600  # 5min vol < $600 + mcap > $60K → exit
LIQUIDITY_MIN = 1000             # $1K — mcap > $70K + liq < $1K = sell
EXIT_PLAN_TEXT = f"""TP1 +50%: HOLD (trail 40%)"""
