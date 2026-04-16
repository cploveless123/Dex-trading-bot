"""
Trading Constants - TP5 COMPOUND STRATEGY

Key insight: Small positions (< 0.2 SOL) need to aim for TP5 (+1000%) to make meaningful gains
Larger positions can use tighter TPs since they already have cushion

TP5 Strategy:
- When a position reaches TP5 (+1000%), the remaining 10% position becomes "compound mode"
- In compound mode, position is monitored with aggressive trailing stop to ride further pumps
- Target: identify winners early and let them run

Exit Strategy (per position, 0.1 SOL each):
- TP1: +50% → Sell 10% (0.01 SOL) | Stop: -25%
- TP2: +100% → Sell 15% (0.015 SOL) | Stop: -25%  
- TP3: +200% → Sell 20% (0.02 SOL) | Stop: -20%
- TP4: +400% → Sell 25% (0.025 SOL) | Stop: -15%
- TP5: +1000% → Sell 30% (0.03 SOL) | REMAINING 10% (0.01 SOL) enters COMPOUND MODE

Compound Mode (for positions hitting TP5):
- Use 20% trailing stop from peak
- Monitor for continued upside
- If price drops 20% from peak → exit remaining 10%
- Target: let winners run 2-5x additional after TP5

Risk Management:
- Max open: 5 positions
- Position size: 0.1 SOL each
- Stop loss: -25% default, -15% for large winners
- Max daily loss: NO LIMIT
"""
CHRIS_STARTING_BALANCE = 1.0   # Chris's starting balance in SOL


# Position sizing
POSITION_SIZE = 0.1          # SOL per trade
MAX_OPEN_POSITIONS = 9       # Max concurrent positions
MAX_DAILY_LOSS = 9999         # Disabled (no limit)

# Entry filters
MIN_MCAP = 5000              # Minimum market cap in USD
MAX_MCAP = 55000             # Maximum market cap in USD
MAX_MCAP = 55000            # Maximum market cap in USD
MIN_HOLDERS = 15             # Minimum holder count
MIN_CHG5_FOR_BUY = 2.0      # Minimum 5m change % for buy signal
PUMP_CHG1_THRESHOLD = 5.001  # 1-min change % to trigger pump path (was 20) (NOT chg5)
H1_MOMENTUM_MIN = 25.0      # Minimum 1h change % (momentum requirement)
H1_MOMENTUM_MAX = 700.0     # Maximum 1h change % (reject meme coins with insane pump)

# Cooldown timing
YOUNG_AGE_THRESHOLD = 900   # Age in seconds (< 15 min = young)
YOUNG_COOLDOWN = 45          # Cooldown for young tokens
OLDER_COOLDOWN = 45          # Cooldown for older tokens
BASE_WAIT = 15               # Base cooldown for normal entries
CHG1_RECHECK_INTERVAL = 6    # Recheck interval when chg1 < -5%
CHG1_VERIFY_DELAY = 6         # Verification delay after chg1 recovery

# Pump path timing
PUMP_WAIT_1 = 45             # First confirmation wait (45s cooldown before checking)
PUMP_WAIT_2 = 10            # Second confirmation wait
PUMP_VERIFY_DELAY = 10         # Final verification wait

# Recovery settings
RECOVERY_WAIT = 6            # Recovery recheck interval
CHG5_RECOVERY_CHECK = 5.0   # chg5 must recover this % from lowest

# EXIT STRATEGY (TP5 Progressive Selling)
TP1_PCT = 50                 # Take profit 1: +50%
TP1_TRAIL = 40               # 40% trailing stop from peak
TP1_HOLD = True              # HOLD at TP1 - no sell
TP1_SELL_PCT = 0             # 0% sell at TP1 (HOLD mode)

TP2_PCT = 100                # Take profit 2: +100%
TP2_SELL_PCT = 0.40         # Sell 40% of position at TP2
TP2_TRAIL = 30              # 30% trailing stop

TP3_PCT = 200               # Take profit 3: +200%
TP3_SELL_PCT = 0.30         # Sell 30% of position at TP3
TP3_TRAIL = 30              # 30% trailing stop

TP4_PCT = 300               # Take profit 4: +300%
TP4_SELL_PCT = 0.20         # Sell 20% of position at TP4
TP4_TRAIL = 30              # 30% trailing stop

TP5_PCT = 1000              # Take profit 5: +1000% (TP5 target!)
TP5_SELL_PCT = 1.00         # Sell remaining at TP5 (exit all)
TP5_TRAIL = 20              # 20% trailing stop

STOP_LOSS_PCT = 30          # Exit all at -30%

# Exchange whitelist
ALLOWED_EXCHANGES = ['raydium']  # Raydium only (no pump.fun/pumpswap for now)
PUMP_EXCHANGES = ['pump', 'pumpswap']  # Pump exchanges need pair_address check

# Fallen Giant filter
FALLEN_GIANT_H1 = 700         # If h1 > this AND mcap < threshold, reject
FALLEN_GIANT_MCAP = 25000    # Mcap threshold for fallen giant

# Buy/Sell ratio
BS_RATIO_NEW = 1.5          # BS ratio required for tokens < 15 min
BS_RATIO_OLD = 1.3          # BS ratio required for tokens >= 15 min
BS_PUMP_FUN_OK = True       # Skip BS check for pump.fun tokens

# Volume requirements
MIN_VOLUME = 5000             # Minimum 24h volume in USD
MIN_5MIN_VOLUME = 500        # Minimum 5min volume in USD

# H1 instability
H1_INSTABILITY_MULTIPLIER = 3  # If h1 changes by >3x, reject

# Dip filter
MIN_DIP_PCT = 5              # Minimum dip % from ATH
MAX_DIP_PCT = 45             # Maximum dip % from ATH (don't buy dumps)

# Scanner timing
SCAN_INTERVAL = 15          # Seconds between scan cycles
TOKEN_RECHECK_INTERVAL = 15   # Only fetch fresh data when timer within this of expiring

# Throttle settings
THROTTLE_BACKOFF_BASE = 30   # Base backoff seconds
THROTTLE_BACKOFF_MAX = 300  # Max backoff seconds
DEXSCREENER_MAX_FAILS = 5   # Stop DexScreener calls after this many failures

# Alert settings
ALERT_DEDUP_SECONDS = 300    # Same alert only once per 5 minutes
THROTTLE_ALERT_ONCE = True   # One throttle alert per event
# === ALERT SENDER / POSITION MONITOR CONSTANTS ===
BOT_TOKEN = "8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg"
CHAT_ID = "6402511249"
TRADES_FILE = "/root/Dex-trading-bot/trades/sim_trades.jsonl"

# === Alert Sender / Exit Plan ===
EXIT_PLAN_TEXT = """📋 TP5 EXIT PLAN:
• TP1: +50% → HOLD (40% trail)
• TP2: +100% → sell 40% (30% trail)
• TP3: +200% → sell 30% (30% trail)
• TP4: +300% → sell 20% (30% trail)
• TP5: +1000% → sell ALL
• STOP: -30%"""

SIM_WALLET_FILE = '/root/Dex-trading-bot/sim_wallet.json'
SIM_RESET_TIMESTAMP = 0  # No reset timestamp
