#!/bin/bash
# Auto-start script for trading bot

cd /root/trading-bot

# Activate venv and run
source venv/bin/activate
python scripts/sim_trader.py >> bot.log 2>&1
