#!/bin/bash
cd /root/Dex-trading-bot
export PYTHONUNBUFFERED=1
exec python3 -u auto_scanner.py >> auto_scanner.log 2>&1