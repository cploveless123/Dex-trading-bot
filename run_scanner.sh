#!/bin/bash
cd /root/Dex-trading-bot
export PYTHONUNBUFFERED=1
exec python3 -u whale_momentum_scanner.py >> whale_momentum.log 2>&1