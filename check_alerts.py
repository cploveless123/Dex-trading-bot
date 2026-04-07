#!/usr/bin/env python3
"""Verify only alert_sender.py sends Telegram alerts"""
import subprocess
result = subprocess.run(['grep', '-r', 'sendMessage', '.'], capture_output=True, text=True)
for line in result.stdout.split('\n'):
    if 'sendMessage' in line and not line.startswith('./venv'):
        print(line)
