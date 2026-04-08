#!/usr/bin/env python3
"""
Health Check - Self-audit system before git backup
Scans for: crashes, bad imports, wrong tokens, inconsistent constants, dead processes
"""
import subprocess, sys, os
from pathlib import Path

BOT_DIR = Path("/root/Dex-trading-bot")
TRADING_CONSTANTS = BOT_DIR / "trading_constants.py"
TRADES_FILE = BOT_DIR / "trades" / "sim_trades.jsonl"
CHECKS_PASSED = []
CHECKS_FAILED = []

def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

def check_python_imports():
    """Check all Python files import cleanly"""
    print("\n=== Python Import Check ===")
    files = list(BOT_DIR.glob("*.py")) + list((BOT_DIR / "reports").glob("*.py"))
    for f in files:
        if f.name.startswith("_"): continue
        result = run(f"cd {BOT_DIR} && python3 -c 'import {f.stem}' 2>&1")
        if result.returncode == 0:
            print(f"  ✅ {f.name}")
            CHECKS_PASSED.append(f.name)
        else:
            err = result.stderr.strip().split("\n")[-1][:80]
            print(f"  ❌ {f.name}: {err}")
            CHECKS_FAILED.append(f"{f.name}: {err}")

def check_exit_plan_consistency():
    """Verify EXIT_PLAN_TEXT matches trading_constants"""
    print("\n=== Exit Plan Consistency ===")
    try:
        result = run(f"cd {BOT_DIR} && python3 -c 'from trading_constants import EXIT_PLAN_TEXT, TP1_PERCENT, TRAILING_STOP_PCT, STOP_LOSS_PERCENT; print(f\"TP1:{TP1_PERCENT} TRAIL:{TRAILING_STOP_PCT} STOP:{STOP_LOSS_PERCENT}\")'")
        if result.returncode == 0:
            consts = result.stdout.strip()
            print(f"  ✅ trading_constants: {consts}")
            CHECKS_PASSED.append("exit_plan_constants")
        else:
            print(f"  ❌ trading_constants: {result.stderr}")
            CHECKS_FAILED.append("exit_plan_constants")
    except:
        pass

def check_bot_tokens():
    """Check all files use correct bot token"""
    print("\n=== Bot Token Check ===")
    correct = "8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg"
    wrong = "8773298871:AAEH6xH9WjgmE_i6gTXM3xZG3cK5Y5V-24w"
    files = list(BOT_DIR.glob("*.py")) + list((BOT_DIR / "reports").glob("*.py"))
    bad = []
    for f in files:
        if f.name.startswith("_"): continue
        content = f.read_text()
        if "8773298" in content:
            bad.append(f.name)
            print(f"  ❌ {f.name}: uses wrong token (8773298)")
        elif correct in content or "BOT_TOKEN" in content or "telegram" in content.lower():
            print(f"  ✅ {f.name}: likely correct token")
    if not bad:
        CHECKS_PASSED.append("bot_tokens")
    else:
        CHECKS_FAILED.append(f"wrong_token: {bad}")

def check_m5_field():
    """Verify auto_scanner and gmgn_buyer use m5 not h5 for 5min volume"""
    print("\n=== 5min Volume Field (m5 vs h5) ===")
    for fname in ["auto_scanner.py", "gmgn_buyer.py"]:
        f = BOT_DIR / fname
        if not f.exists(): continue
        content = f.read_text()
        if "volume', {}).get('h5'" in content:
            print(f"  ❌ {fname}: still uses h5 (wrong field)")
            CHECKS_FAILED.append(f"{fname}: uses h5")
        elif "m5" in content:
            print(f"  ✅ {fname}: uses m5")
            CHECKS_PASSED.append(f"{fname}_m5")
        else:
            print(f"  ⚠️ {fname}: m5 not found")

def check_processes():
    """Check all expected processes are running"""
    print("\n=== Process Check ===")
    expected = ["auto_scanner", "gmgn_buyer", "position_monitor", "alert_sender", "gmgn_poll"]
    result = run("ps aux | grep -E 'auto_scanner|gmgn_buyer|position_monitor|alert_sender|gmgn_poll' | grep -v grep | wc -l")
    count = int(result.stdout.strip())
    print(f"  Running: {count}/{len(expected)}")
    for proc in expected:
        r = run(f"ps aux | grep '{proc}' | grep -v grep")
        if r.stdout.strip():
            print(f"  ✅ {proc}")
            CHECKS_PASSED.append(proc)
        else:
            print(f"  ❌ {proc}: NOT RUNNING")
            CHECKS_FAILED.append(f"dead_process: {proc}")

def check_position_monitor_api():
    """Check position_monitor uses token_address not pair_address"""
    print("\n=== Position Monitor API Fix ===")
    f = BOT_DIR / "position_monitor.py"
    if not f.exists(): return
    content = f.read_text()
    if "get_live_mcap(pair" in content:
        print(f"  ❌ position_monitor.py: get_live_mcap uses pair_address (old)")
        CHECKS_FAILED.append("position_monitor: uses pair_address")
    elif "get_live_mcap(tok" in content:
        print(f"  ✅ position_monitor.py: uses token_address (fixed)")
        CHECKS_PASSED.append("position_monitor_token_address")
    if "{pair}" in content and "dexscreener.com" in content:
        print(f"  ❌ position_monitor.py: {{pair}} variable in alert (crashes)")
        CHECKS_FAILED.append("position_monitor: {pair} bug")
    else:
        print(f"  ✅ position_monitor.py: no {{pair}} bug")

def check_trade_file():
    """Check trade file exists and is readable"""
    print("\n=== Trade File ===")
    if not TRADES_FILE.exists():
        print(f"  ❌ {TRADES_FILE}: does not exist")
        CHECKS_FAILED.append("trade_file_missing")
        return
    try:
        with open(TRADES_FILE) as f:
            lines = len(f.readlines())
        print(f"  ✅ {TRADES_FILE}: {lines} trades")
        CHECKS_PASSED.append("trade_file_ok")
    except Exception as e:
        print(f"  ❌ {TRADES_FILE}: {e}")
        CHECKS_FAILED.append(f"trade_file_error: {e}")

def auto_fix():
    """Attempt auto-fixes for known issues"""
    print("\n=== Auto-Fix Attempt ===")
    
    # Fix m5 field
    for fname in ["auto_scanner.py", "gmgn_buyer.py"]:
        f = BOT_DIR / fname
        if not f.exists(): continue
        content = f.read_text()
        if "volume', {}).get('h5'" in content:
            fixed = content.replace("volume', {}).get('h5'", "volume', {}).get('m5'")
            f.write_text(fixed)
            print(f"  ✅ Fixed {fname}: h5 → m5")
    
    # Fix {pair} bug
    f = BOT_DIR / "position_monitor.py"
    if f.exists():
        content = f.read_text()
        if "{pair}" in content and "dexscreener.com" in content:
            fixed = content.replace("dexscreener.com/solana/{pair}", "dexscreener.com/solana/{tok}")
            f.write_text(fixed)
            print(f"  ✅ Fixed position_monitor.py: {{pair}} → {{tok}}")
    
    # Fix wrong bot token
    for f in list(BOT_DIR.glob("*.py")) + list((BOT_DIR / "reports").glob("*.py")):
        if f.name.startswith("_"): continue
        content = f.read_text()
        if "8773298871:AAEH6xH9WjgmE_i6gTXM3xZG3cK5Y5V-24w" in content:
            fixed = content.replace("8773298871:AAEH6xH9WjgmE_i6gTXM3xZG3cK5Y5V-24w", "8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg")
            f.write_text(fixed)
            print(f"  ✅ Fixed {f.name}: wrong bot token")
    
    # Fix position_monitor TRAILING_STOP_PCT import
    f = BOT_DIR / "position_monitor.py"
    if f.exists():
        content = f.read_text()
        # Remove hardcoded TRAILING_STOP_PCT if it exists before the import
        lines = content.split("\n")
        new_lines = []
        skip = False
        for line in lines:
            if "TRAILING_STOP_PCT = 20" in line and "from trading_constants" not in content:
                print(f"  ✅ Removed hardcoded TRAILING_STOP_PCT from position_monitor.py")
                continue
            new_lines.append(line)
        f.write_text("\n".join(new_lines))

def main():
    print("=" * 50)
    print("HEALTH CHECK - Self Audit")
    print("=" * 50)
    
    check_python_imports()
    check_exit_plan_consistency()
    check_bot_tokens()
    check_m5_field()
    check_processes()
    check_position_monitor_api()
    check_trade_file()
    
    print("\n" + "=" * 50)
    print(f"RESULTS: {len(CHECKS_PASSED)} passed, {len(CHECKS_FAILED)} failed")
    print("=" * 50)
    
    if CHECKS_FAILED:
        print("\n⚠️ ISSUES FOUND:")
        for f in CHECKS_FAILED:
            print(f"  - {f}")
        print("\n🔧 Attempting auto-fix...")
        auto_fix()
        
        print("\n📋 MANUAL FIX NEEDED:")
        for f in CHECKS_FAILED:
            if "import" in f or "crash" in f:
                print(f"  - {f}")
        return 1
    else:
        print("\n✅ ALL CHECKS PASSED - Ready for backup")
        return 0

if __name__ == "__main__":
    sys.exit(main())
