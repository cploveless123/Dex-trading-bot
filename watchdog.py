#!/usr/bin/env python3
import subprocess
import time

SCRIPT_DIR = "/root/.openclaw/workspace/trading-bot/scripts"
VENV = "/root/.openclaw/workspace/venv/bin/python"
LOG_DIR = "/root/.openclaw/workspace/trading-bot"

PROCESSES = [
    ("combined_monitor", "combined_monitor.py", "dex.log"),
    ("gmgn_poll_monitor", "gmgn_poll_monitor.py", "gmgn.log"),
    ("sim_trader", "sim_trader.py", "sim.log"),
]

def is_running(name):
    result = subprocess.run(["pgrep", "-f", name], capture_output=True)
    return result.returncode == 0

def start_process(name, script, log):
    cmd = f"cd {SCRIPT_DIR} && {VENV} {SCRIPT_DIR}/{script} >> {LOG_DIR}/{log} 2>&1 &"
    subprocess.run(cmd, shell=True)
    print(f"Started {name}")

def git_backup():
    try:
        subprocess.run(["git", "add", "-A"], cwd="/root/.openclaw/workspace", capture_output=True)
        subprocess.run(["git", "commit", "-m", f"Auto-backup {time.strftime('%H:%M')}"], cwd="/root/.openclaw/workspace", capture_output=True)
        subprocess.run(["git", "push", "origin", "master"], cwd="/root/.openclaw/workspace", capture_output=True, timeout=30)
        print("Git backup done")
    except Exception as e:
        print(f"Git error: {e}")

def main():
    print("WATCHDOG STARTED")
    while True:
        for name, script, log in PROCESSES:
            if not is_running(name):
                print(f"Restarting {name}...")
                start_process(name, script, log)
        
        running = sum(1 for n, _, _ in PROCESSES if is_running(n))
        print(f"[{time.strftime('%H:%M')}] {running}/{len(PROCESSES)} running")
        
        if int(time.time()) % 300 == 0:
            git_backup()
        
        time.sleep(30)

if __name__ == "__main__":
    main()
