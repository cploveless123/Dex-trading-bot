"""
Trading Constants - SINGLE SOURCE OF TRUTH
All trading rules, exit plans, and configuration defined here.
Do NOT hardcode these values elsewhere - import from this file.
"""
from pathlib import Path

# Exit Plan
TP1_PERCENT = 45          # First take profit level (%)
TP1_SELL_PCT = 100        # % of position to sell at TP1 (full exit at TP1)
TP2_PERCENT = 45          # Trailing stop trigger (% above TP1 peak)
TP2_SELL_PCT = 100        # Sell remaining % at trailing stop
STOP_LOSS_PERCENT = -30   # Stop loss percentage
TRAILING_STOP_PCT = 20   # % drop from peak to trigger trailing stop on remaining position

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
+{TP1_PERCENT}% → Sell full position
📊 Trailing stop: active after TP1 (not applicable if TP1=full exit)
⚠️ Stop: {STOP_LOSS_PERCENT}%"""

def get_exit_plan():
    return EXIT_PLAN_TEXT

SIM_RESET_TIMESTAMP = '2026-04-08T04:34:00'  # Only count PnL from trades after this time
