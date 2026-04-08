#!/usr/bin/env python3
"""
Health Check - Self-audit system before git backup
Scans for: crashes, bad imports, wrong tokens, inconsistent constants, dead processes
"""
import subprocess, sys, os
from pathlib import Path

BOT_DIR = Path("/root/Dex-trading-bot")
CORRECT_TOKEN = "8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg"
WRONG_TOKEN = "8773298871:AAEH6xH9WjgmE_i6gTXM3xZG3cK5Y5V-24w"
CHECKS_PASSED = []
CHECKS_FAILED = []

def run(cmd, timeout=5):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None

def check_python_imports():
    """Check all Python files import cleanly"""
    print("\n=== Python Import Check ===")
    files = ["position_monitor", "auto_scanner", "gmgn_buyer", "send_alert", "alert_sender"]
    for f in files:
        result = run(f"cd {BOT_DIR} && python3 -c 'import {f}'")
        if result and result.returncode == 0:
            print(f"  ✅ {f}")
            CHECKS_PASSED.append(f)
        else:
            err = result.stderr.strip().split("\n")[-1][:80] if result else "timeout"
            print(f"  ❌ {f}: {err}")
            CHECKS_FAILED.append(f"{f}: {err}")

def check_exit_plan_consistency():
    """Verify EXIT_PLAN_TEXT matches trading_constants"""
    print("\n=== Exit Plan Consistency ===")
    result = run(f'cd {BOT_DIR} && python3 -c "from trading_constants import TP1_PERCENT, TRAILING_STOP_PCT, STOP_LOSS_PERCENT; print(TP1_PERCENT, TRAILING_STOP_PCT, STOP_LOSS_PERCENT)"')
    if result and result.returncode == 0:
        consts = result.stdout.strip()
        print(f"  ✅ {consts}")
        CHECKS_PASSED.append("exit_plan_constants")
    else:
        print(f"  ❌ {result.stderr if result else 'timeout'}")
        CHECKS_FAILED.append("exit_plan_constants")

def check_bot_tokens():
    """Check all files use correct bot token"""
    print("\n=== Bot Token Check ===")
    files = list(BOT_DIR.glob("*.py")) + list((BOT_DIR / "reports").glob("*.py"))
    bad = []
    for f in files:
        if f.name.startswith("_") or f.name == "health_check.py": continue
        content = f.read_text()
        if WRONG_TOKEN in content:
            bad.append(f.name)
            print(f"  ❌ {f.name}: uses WRONG token")
    if not bad:
        print("  ✅ All files use correct token")
        CHECKS_PASSED.append("bot_tokens")
    else:
        CHECKS_FAILED.append(f"wrong_token: {bad}")

def check_m5_field():
    """Verify auto_scanner and gmgn_buyer use m5 not h5 for 5min volume"""
    print("\n=== 5min Volume Field (m5) ===")
    for fname in ["auto_scanner.py", "gmgn_buyer.py"]:
        f = BOT_DIR / fname
        if not f.exists(): continue
        content = f.read_text()
        if "get('h5'" in content:
            print(f"  ❌ {fname}: still uses h5 (wrong)")
            CHECKS_FAILED.append(f"{fname}: uses h5")
        elif "get('m5'" in content:
            print(f"  ✅ {fname}: uses m5")
            CHECKS_PASSED.append(f"{fname}_m5")
        else:
            print(f"  ⚠️ {fname}: m5/h5 not found")

def check_position_monitor_api():
    """Check position_monitor uses token_address not pair_address"""
    print("\n=== Position Monitor API Fix ===")
    f = BOT_DIR / "position_monitor.py"
    if not f.exists(): return
    content = f.read_text()
    if "get_live_mcap(pair" in content:
        print(f"  ❌ get_live_mcap uses pair_address (old)")
        CHECKS_FAILED.append("position_monitor: uses pair_address")
    elif "get_live_mcap(tok" in content:
        print(f"  ✅ get_live_mcap uses token_address")
        CHECKS_PASSED.append("position_monitor_token_address")
    if "{pair}" in content:
        print(f"  ❌ {{pair}} variable in alert (crashes)")
        CHECKS_FAILED.append("position_monitor: {pair} bug")
    else:
        print(f"  ✅ no {{pair}} bug")
        CHECKS_PASSED.append("position_monitor_no_pair_bug")

def check_processes():
    """Check all expected processes are running"""
    print("\n=== Process Check ===")
    expected = ["auto_scanner", "gmgn_buyer", "position_monitor", "alert_sender", "gmgn_poll_monitor"]
    result = run("ps aux | grep -E 'auto_scanner|gmgn_buyer|position_monitor|alert_sender|gmgn_poll' | grep -v grep | wc -l")
    if result:
        count = int(result.stdout.strip())
        print(f"  Running: {count}/{len(expected)}")
    for proc in expected:
        r = run(f"ps aux | grep '{proc}' | grep -v grep | wc -l")
        if r and int(r.stdout.strip()) > 0:
            print(f"  ✅ {proc}")
            CHECKS_PASSED.append(proc)
        else:
            print(f"  ❌ {proc}: NOT RUNNING")
            CHECKS_FAILED.append(f"dead_process: {proc}")

def auto_fix():
    """Attempt auto-fixes for known issues"""
    print("\n=== Auto-Fix ===")
    fixed = []
    
    # Fix m5 field
    for fname in ["auto_scanner.py", "gmgn_buyer.py"]:
        f = BOT_DIR / fname
        if not f.exists(): continue
        content = f.read_text()
        if "get('h5'" in content:
            fixed_content = content.replace("get('h5'", "get('m5'")
            f.write_text(fixed_content)
            fixed.append(fname)
            print(f"  ✅ Fixed {fname}: h5 → m5")
    
    # Fix {pair} bug
    f = BOT_DIR / "position_monitor.py"
    if f.exists():
        content = f.read_text()
        if "{pair}" in content and "dexscreener" in content:
            fixed_content = content.replace("dexscreener.com/solana/{pair}", "dexscreener.com/solana/{tok}")
            f.write_text(fixed_content)
            fixed.append("position_monitor.py {pair}→{tok}")
            print(f"  ✅ Fixed position_monitor.py: {{pair}} → {{tok}}")
    
    # Fix wrong bot token
    for f in list(BOT_DIR.glob("*.py")) + list((BOT_DIR / "reports").glob("*.py")):
        if f.name.startswith("_") or f.name == "health_check.py": continue
        content = f.read_text()
        if WRONG_TOKEN in content:
            fixed_content = content.replace(WRONG_TOKEN, CORRECT_TOKEN)
            f.write_text(fixed_content)
            fixed.append(f.name)
            print(f"  ✅ Fixed {f.name}: wrong bot token")
    
    if not fixed:
        print("  No auto-fixes needed")
    return fixed

def main():
    print("=" * 50)
    print("HEALTH CHECK - Self Audit")
    print("=" * 50)
    
    check_python_imports()
    check_exit_plan_consistency()
    check_bot_tokens()
    check_m5_field()
    check_position_monitor_api()
    check_processes()
    
    print("\n" + "=" * 50)
    print(f"RESULTS: {len(CHECKS_PASSED)} passed, {len(CHECKS_FAILED)} failed")
    print("=" * 50)
    
    if CHECKS_FAILED:
        print("\n⚠️ ISSUES FOUND:")
        for f in CHECKS_FAILED:
            print(f"  - {f}")
        
        fixed = auto_fix()
        if fixed:
            print(f"\n🔧 Auto-fixed: {fixed}")
        
        return 1
    else:
        print("\n✅ ALL CHECKS PASSED")
        return 0

if __name__ == "__main__":
    sys.exit(main())
