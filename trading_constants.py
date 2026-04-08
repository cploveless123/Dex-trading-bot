"""
Trading Constants - SINGLE SOURCE OF TRUTH
All trading rules, exit plans, and configuration defined here.
Do NOT hardcode these values elsewhere - import from this file.
"""
from pathlib import Path

# Exit Plan
TP1_PERCENT = 35          # First take profit level (%)
TP1_SELL_PCT = 70         # % of position to sell at TP1
TP2_PERCENT = 95          # Second take profit level (%)
TP2_SELL_PCT = 30         # % of remaining to sell at TP2
STOP_LOSS_PERCENT = -25   # Stop loss percentage

# Position
POSITION_SIZE_SOL = 0.05  # SOL per trade
POSITION_SIZE = POSITION_SIZE_SOL

# Scanner Criteria
MIN_MCAP = 5000           # Minimum market cap ($)
MAX_MCAP = 100000         # Maximum market cap ($)
MIN_VOLUME = 5000         # Minimum 24h volume ($)
MIN_24H_CHANGE = 20       # Minimum 24h price change (%)

# Files
TRADES_FILE = Path("/root/Dex-trading-bot/trades/sim_trades.jsonl")
WALLETS_FILE = Path("/root/Dex-trading-bot/wallet_analysis/whale_wallets.jsonl")
ALERTS_FILE = Path("/root/Dex-trading-bot/wallet_analysis/whale_activity.jsonl")

EXIT_PLAN_TEXT = f"""🎯 Exit Plan:
+{TP1_PERCENT}% → Sell {TP1_SELL_PCT}%
+{TP2_PERCENT}% → Sell {TP2_SELL_PCT}%
⚠️ Stop: {STOP_LOSS_PERCENT}%"""

def get_exit_plan():
    return EXIT_PLAN_TEXT
