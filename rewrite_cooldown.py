#!/usr/bin/env python3
"""Rewrite cooldown logic - handles chg1 < -5% with 15s rechecks until recovery"""
import re

with open('/root/Dex-trading-bot/gmgn_scanner.py', 'r') as f:
    code = f.read()

# First, add new state constants after the existing ones
old_states = """STATE_RECOVERY_WAIT = 'RECOVERY_WAIT'  # 15s rechecks for deterioration
STATE_POST_COOLDOWN = 'POST_COOLDOWN'  # 15s after cooldown ends"""

new_states = """STATE_RECOVERY_WAIT = 'RECOVERY_WAIT'  # 15s rechecks for deterioration
STATE_POST_COOLDOWN = 'POST_COOLDOWN'  # 15s after cooldown ends
# New cooldown states per Chris's spec:
STATE_YOUNG_COOLDOWN = 'YOUNG_COOLDOWN'     # 45s for young (<15min) + h1>+5% + chg5>-5%
STATE_OLDER_COOLDOWN = 'OLDER_COOLDOWN'     # 45s for older (>15min) + h1>+5% + chg5>-5%
STATE_CHG1_RECHECK = 'CHG1_RECHECK'          # chg1 < -5%, 15s rechecks until chg1 > +5% from lowest_mcap
STATE_CHG1_VERIFY = 'CHG1_VERIFY'            # chg1 recovered, 15s verify before buy
STATE_BASE_COOLDOWN = 'BASE_COOLDOWN'       # 30s base for normal entries
STATE_BASE_CHG1_CHECK = 'BASE_CHG1_CHECK'    # chg1 check before buy in base path"""

code = code.replace(old_states, new_states)

# Add lowest_mcap to COOLDOWN_WATCH initialization in add_to_cooldown
old_init = """        'lowest_chg5': chg5,  # Track lowest chg5 for recovery
    }"""

new_init = """        'lowest_chg5': chg5,  # Track lowest chg5 for recovery
        'lowest_mcap': result.get('mcap', 0),  # Track lowest mcap for chg1 recovery
    }"""

code = code.replace(old_init, new_init)

# Now rewrite the cooldown state machine - first find and replace the entire 
# cooldown state section (from PUMP_VERIFY continue through all the cooldown paths)

# Find the section we need to replace
old_section = """        # === DETERIORATION CHECK (all states) ===
        chg5_drop = chg5_prev - chg5 if chg5_prev else 0
        h1_change_ratio = abs(h1 / h1_prev) if h1_prev else 1
        
        # H1 instability: >3x change → reject immediately
        if h1_prev > 0 and h1_change_ratio > H1_INSTABILITY_MULTIPLIER * 3:
            print(f"   [REJECT_H1_INSTABLE] {result['token']}: h1 {h1_prev:.0f}% → {h1:.0f}% (>{H1_INSTABILITY_MULTIPLIER}x change)")
            REJECTED_TEMP[addr] = {'ts': now, 'reason': 'h1 instability'}
            to_remove.append(addr)
            continue
        
        # Deterioration: chg5 dropped > CHG5_DROP_THRESHOLD from previous
        if chg5_drop > CHG5_DROP_THRESHOLD:
            lowest_chg5 = min(lowest_chg5, chg5)
            data['lowest_chg5'] = lowest_chg5
            data['chg5_prev'] = chg5
            data['h1_prev'] = h1
            data['recheck_count'] += 1
            # Transition to recovery state
            data['state'] = STATE_RECOVERY_WAIT
            data['cooldown_end'] = now + STATE_RECOVERY_WAIT
            print(f"   [DETERIORATING] {result['token']}: chg5 {chg5_prev:+.1f}% → {chg5:+.1f}% (drop {chg5_drop:.1f}%) | recovery mode")
            continue
        
        # === YOUNG COOLDOWN PATH (<15min + h1>5% + chg5>-5%) ===
        if state == STATE_BASE_WAIT and age_sec < YOUNG_AGE_THRESHOLD and h1 > H1_MOMENTUM_MIN and chg5 > -5:
            if chg5 < MIN_CHG5_FOR_BUY:
                # Not ready - wait in base
                data['cooldown_end'] = now + STATE_BASE_WAIT
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                print(f"   [YOUNG_WAIT] {result['token']}: chg5={chg5:+.1f}% < +{MIN_CHG5_FOR_BUY}% | wait {STATE_BASE_WAIT}s")
            else:
                # Ready - start young cooldown
                data['state'] = STATE_POST_COOLDOWN
                data['cooldown_end'] = now + YOUNG_COOLDOWN
                data['lowest_chg5'] = chg5
                print(f"   [YOUNG_COOLDOWN] {result['token']}: chg5={chg5:+.1f}% | wait {YOUNG_COOLDOWN}s")
            data['chg5_prev'] = chg5
            data['h1_prev'] = h1
            continue
        
        # === OLDER COOLDOWN PATH (>15min + h1>5% + chg5>-5%) ===
        if state == STATE_BASE_WAIT and age_sec >= YOUNG_AGE_THRESHOLD and h1 > H1_MOMENTUM_MIN and chg5 > -5:
            if chg5 < MIN_CHG5_FOR_BUY:
                # Not ready - wait in base
                data['cooldown_end'] = now + STATE_BASE_WAIT
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                print(f"   [OLDER_WAIT] {result['token']}: chg5={chg5:+.1f}% < +{MIN_CHG5_FOR_BUY}% | wait {STATE_BASE_WAIT}s")
            else:
                data['state'] = STATE_POST_COOLDOWN
                data['cooldown_end'] = now + OLDER_COOLDOWN
                data['lowest_chg5'] = chg5
                print(f"   [OLDER_COOLDOWN] {result['token']}: chg5={chg5:+.1f}% | wait {OLDER_COOLDOWN}s")
            data['chg5_prev'] = chg5
            data['h1_prev'] = h1
            continue
        
        # === BASE PATH (chg5 > +2% but not young/older momentum) ===
        if state == STATE_BASE_WAIT:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                continue
            # Timer expired - buy if chg5 still good
            if chg5 >= MIN_CHG5_FOR_BUY:
                final_result, fail_reason = scan_token(data['token_data'])
                if final_result:
                    print(f"   [BUY_NORMAL] {result['token']}: chg5={chg5:+.1f}% | BUY!")
                    buy_token(addr, final_result)
                    to_remove.append(addr)
                    continue
                else:
                    REJECTED_TEMP[addr] = {'ts': now, 'reason': fail_reason}
                    to_remove.append(addr)
                    continue
            else:
                data['cooldown_end'] = now + STATE_BASE_WAIT
                print(f"   [BASE_RECHECK] {result['token']}: chg5={chg5:+.1f}% < +{MIN_CHG5_FOR_BUY}% | wait {STATE_BASE_WAIT}s")
            data['chg5_prev'] = chg5
            data['h1_prev'] = h1
            continue
        
        # === RECOVERY PATH (from deterioration, chg5 dropped but now recovering) ===
        if state == STATE_RECOVERY_WAIT:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                continue
            recovery_target = data['lowest_chg5'] + CHG5_RECOVERY_CHECK
            if chg5 >= max(recovery_target, MIN_CHG5_FOR_BUY):
                data['state'] = STATE_POST_COOLDOWN
                data['cooldown_end'] = now + STATE_POST_COOLDOWN
                print(f"   [RECOVERED] {result['token']}: chg5={chg5:+.1f}% >= {recovery_target:+.1f}% | verify {STATE_POST_COOLDOWN}s")
            else:
                data['lowest_chg5'] = min(data['lowest_chg5'], chg5)
                data['cooldown_end'] = now + STATE_RECOVERY_WAIT
                print(f"   [STILL_RECOVERING] {result['token']}: chg5={chg5:+.1f}% < {recovery_target:+.1f}% | wait {STATE_RECOVERY_WAIT}s")
            data['chg5_prev'] = chg5
            data['h1_prev'] = h1
            continue
        
        # === POST-COOLDOWN: Verify then BUY ===
        if state == STATE_POST_COOLDOWN:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                continue
            # Verify chg5 still > +2%
            if chg5 >= MIN_CHG5_FOR_BUY:
                # Final filter check
                final_result, fail_reason = scan_token(data['token_data'])
                if final_result:
                    print(f"   [BUY_READY] {result['token']}: verified | BUY!")
                    buy_token(addr, final_result)
                    to_remove.append(addr)
                    continue
                else:
                    print(f"   [REJECT_V73] {result['token']}: {fail_reason}")
                    REJECTED_TEMP[addr] = {'ts': now, 'reason': fail_reason}
                    to_remove.append(addr)
                    continue
            else:
                # chg5 dropped - back to base
                data['state'] = STATE_BASE_WAIT
                data['cooldown_end'] = now + STATE_BASE_WAIT
                data['lowest_chg5'] = min(data['lowest_chg5'], chg5)
                print(f"   [POST_COOLDOWN_DROP] {result['token']}: chg5={chg5:+.1f}% < +{MIN_CHG5_FOR_BUY}% | base wait")
            data['chg5_prev'] = chg5
            data['h1_prev'] = h1
            continue
        
        # === RECOVERY WAIT: Deterioration happened, waiting for chg5 to recover ===
        if state == STATE_RECOVERY_WAIT:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                continue
            # Check if recovered
            recovery_target = data['lowest_chg5'] + CHG5_RECOVERY_CHECK
            if chg5 >= max(recovery_target, MIN_CHG5_FOR_BUY):
                # Recovered! Go back to cooldown
                data['state'] = STATE_POST_COOLDOWN
                data['cooldown_end'] = now + STATE_POST_COOLDOWN
                print(f"   [RECOVERED] {result['token']}: chg5={chg5:+.1f}% >= {recovery_target:+.1f}% | verify {STATE_POST_COOLDOWN}s")
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                continue
            else:
                # Still low - keep waiting in recovery
                data['lowest_chg5'] = min(data['lowest_chg5'], chg5)
                data['cooldown_end'] = now + STATE_RECOVERY_WAIT
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                print(f"   [STILL_RECOVERING] {result['token']}: chg5={chg5:+.1f}% < {recovery_target:+.1f}% | wait {STATE_RECOVERY_WAIT}s")
                continue"""

new_section = """        # === NEW COOLDOWN SYSTEM (Chris's spec) ===
        # Fresh data available: chg5, h1, chg1, mcap all from fresh GMGN call
        
        # === FALLEN GIANT CHECK (all states) ===
        if h1 > 350 and mcap < 25000:
            print(f"   [REJECT_FALLEN] {result['token']}: h1={h1:.0f}% + mcap=${mcap:,.0f} < $25K | Fallen Giant")
            REJECTED_TEMP[addr] = {'ts': now, 'reason': f'Fallen Giant h1={h1:.0f}%'}
            to_remove.append(addr)
            continue
        
        # === CHG1 < -5% FALLBACK PATH (all states) ===
        # If chg1 < -5%, track lowest_mcap and go to recovery rechecks
        if chg1 < -5:
            if state not in [STATE_CHG1_RECHECK, STATE_CHG1_VERIFY, STATE_BASE_CHG1_CHECK]:
                # First time seeing chg1 < -5% - start tracking
                data['lowest_mcap'] = min(data.get('lowest_mcap', mcap), mcap)
                data['state'] = STATE_CHG1_RECHECK
                data['cooldown_end'] = now + 15  # 15s recheck
                data['recheck_count'] = data.get('recheck_count', 0) + 1
                print(f"   [CHG1_FALL] {result['token']}: chg1={chg1:+.1f}% < -5% | recheck path | lowest_mcap=${data['lowest_mcap']:,.0f}")
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                continue
            elif state == STATE_CHG1_RECHECK:
                # Update lowest_mcap
                data['lowest_mcap'] = min(data.get('lowest_mcap', mcap), mcap)
                # Check if chg1 recovered: > +5% from lowest_mcap
                recovery_target = data['lowest_mcap'] * 1.05  # chg1 > +5% from lowest
                remaining = data['cooldown_end'] - now
                if remaining <= 0:
                    if mcap >= recovery_target:
                        # Recovered! Go to verify
                        data['state'] = STATE_CHG1_VERIFY
                        data['cooldown_end'] = now + 15  # 15s verify
                        print(f"   [CHG1_RECOVERED] {result['token']}: mcap=${mcap:,.0f} >= {recovery_target:,.0f} | verify 15s")
                    else:
                        # Still low - keep rechecking
                        data['cooldown_end'] = now + 15
                        data['recheck_count'] = data.get('recheck_count', 0) + 1
                        print(f"   [CHG1_RECHECK] {result['token']}: mcap=${mcap:,.0f} < {recovery_target:,.0f} | wait 15s more")
                    data['chg5_prev'] = chg5
                    data['h1_prev'] = h1
                    continue
            elif state == STATE_CHG1_VERIFY:
                remaining = data['cooldown_end'] - now
                if remaining <= 0:
                    # Verify complete - buy!
                    final_result, fail_reason = scan_token(data['token_data'])
                    if final_result:
                        print(f"   [BUY_CHG1_OK] {result['token']}: chg1 recovered + verify complete | BUY!")
                        buy_token(addr, final_result)
                        to_remove.append(addr)
                        continue
                    else:
                        REJECTED_TEMP[addr] = {'ts': now, 'reason': fail_reason}
                        to_remove.append(addr)
                        continue
        
        # === NORMAL PATHS (chg1 >= -5%) ===
        if state == STATE_CHG1_RECHECK or state == STATE_CHG1_VERIFY:
            # chg1 recovered above -5% - continue with normal path
            recovery_target = data.get('lowest_mcap', mcap) * 1.05
            print(f"   [CHG1_OK] {result['token']}: chg1={chg1:+.1f}% >= -5% | exit recovery, continue normal path")
            data['state'] = STATE_BASE_WAIT  # Fall through to base/cooldown logic
        
        if state == STATE_YOUNG_COOLDOWN:
            # Young (<15min) + h1>+5% + chg5>-5% → 45s cooldown
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                continue
            # Cooldown done - verify chg5 and buy
            if chg5 >= MIN_CHG5_FOR_BUY:
                final_result, fail_reason = scan_token(data['token_data'])
                if final_result:
                    print(f"   [BUY_YOUNG] {result['token']}: chg5={chg5:+.1f}% | BUY after {YOUNG_COOLDOWN}s!")
                    buy_token(addr, final_result)
                    to_remove.append(addr)
                    continue
                else:
                    REJECTED_TEMP[addr] = {'ts': now, 'reason': fail_reason}
                    to_remove.append(addr)
                    continue
            else:
                # chg5 dropped below +2% - go to base rechecks
                data['state'] = STATE_BASE_WAIT
                data['cooldown_end'] = now + STATE_BASE_WAIT
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                print(f"   [YOUNG_DROP] {result['token']}: chg5={chg5:+.1f}% < +{MIN_CHG5_FOR_BUY}% | base recheck")
                continue
        
        if state == STATE_OLDER_COOLDOWN:
            # Older (>15min) + h1>+5% + chg5>-5% → 45s cooldown
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                continue
            # Cooldown done - verify chg5 and buy
            if chg5 >= MIN_CHG5_FOR_BUY:
                final_result, fail_reason = scan_token(data['token_data'])
                if final_result:
                    print(f"   [BUY_OLDER] {result['token']}: chg5={chg5:+.1f}% | BUY after {OLDER_COOLDOWN}s!")
                    buy_token(addr, final_result)
                    to_remove.append(addr)
                    continue
                else:
                    REJECTED_TEMP[addr] = {'ts': now, 'reason': fail_reason}
                    to_remove.append(addr)
                    continue
            else:
                data['state'] = STATE_BASE_WAIT
                data['cooldown_end'] = now + STATE_BASE_WAIT
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                print(f"   [OLDER_DROP] {result['token']}: chg5={chg5:+.1f}% < +{MIN_CHG5_FOR_BUY}% | base recheck")
                continue
        
        if state == STATE_BASE_WAIT:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                continue
            # Timer done - check chg1 vs last check for buy
            chg1_threshold = data.get('chg5_prev', 0) + 3  # chg1 should be > +3% from last chg5
            if chg1 >= chg1_threshold:
                final_result, fail_reason = scan_token(data['token_data'])
                if final_result:
                    print(f"   [BUY_BASE] {result['token']}: chg1={chg1:+.1f}% >= {chg1_threshold:+.1f}% from last | BUY!")
                    buy_token(addr, final_result)
                    to_remove.append(addr)
                    continue
                else:
                    REJECTED_TEMP[addr] = {'ts': now, 'reason': fail_reason}
                    to_remove.append(addr)
                    continue
            else:
                data['cooldown_end'] = now + STATE_BASE_WAIT
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                print(f"   [BASE_RECHECK] {result['token']}: chg1={chg1:+.1f}% < {chg1_threshold:+.1f}% from last | recheck {STATE_BASE_WAIT}s")
                continue
        
        # === STATE_BASE_CHG1_CHECK ===
        if state == STATE_BASE_CHG1_CHECK:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                continue
            chg1_threshold = data.get('chg5_prev', 0) + 3
            if chg1 >= chg1_threshold:
                final_result, fail_reason = scan_token(data['token_data'])
                if final_result:
                    print(f"   [BUY_BASE_CHG1] {result['token']}: chg1={chg1:+.1f}% >= {chg1_threshold:+.1f}% | BUY!")
                    buy_token(addr, final_result)
                    to_remove.append(addr)
                    continue
                else:
                    REJECTED_TEMP[addr] = {'ts': now, 'reason': fail_reason}
                    to_remove.append(addr)
                    continue
            else:
                data['cooldown_end'] = now + STATE_BASE_WAIT
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                print(f"   [BASE_CHG1_RECHECK] {result['token']}: chg1={chg1:+.1f}% < {chg1_threshold:+.1f}% | recheck")
                continue

        # === FALLBACK: no state match - reset to base wait ===
        data['state'] = STATE_BASE_WAIT
        data['cooldown_end'] = now + STATE_BASE_WAIT
        data['chg5_prev'] = chg5
        data['h1_prev'] = h1
        print(f"   [RESET_BASE] {result['token']}: unknown state={state} | reset to base")
        continue"""

code = code.replace(old_section, new_section)

# Now update add_to_cooldown to use the new states
old_add = """    # Determine initial state
    if pump_triggered:
        state = STATE_PUMP_WAIT_1
        cooldown_end = time.time() + STATE_PUMP_WAIT_1
    elif age_sec < YOUNG_AGE_THRESHOLD and h1 > H1_MOMENTUM_MIN and chg5 > -5:
        state = STATE_PUMP_WAIT_1  # Use pump wait as base for young+momentum
        cooldown_end = time.time() + YOUNG_COOLDOWN
    elif age_sec >= YOUNG_AGE_THRESHOLD and h1 > H1_MOMENTUM_MIN and chg5 > -5:
        state = STATE_PUMP_WAIT_1  # Use pump wait as base for older+momentum
        cooldown_end = time.time() + OLDER_COOLDOWN
    else:
        state = STATE_BASE_WAIT
        cooldown_end = time.time() + NORMAL_COOLDOWN"""

new_add = """    # Determine initial state per Chris's spec
    age_sec = result.get('age_sec', 0)
    h1 = result.get('h1', 0)
    chg5 = result.get('chg5', 0)
    pump_triggered = result.get('pump_rule_triggered', False)
    
    if pump_triggered:
        state = STATE_PUMP_WAIT_1
        cooldown_end = time.time() + PUMP_WAIT_1
    elif age_sec < YOUNG_AGE_THRESHOLD and h1 > H1_MOMENTUM_MIN and chg5 > -5:
        # Young (<15min) + h1>+5% + chg5>-5% → 45s cooldown
        state = STATE_YOUNG_COOLDOWN
        cooldown_end = time.time() + 45
    elif age_sec >= YOUNG_AGE_THRESHOLD and h1 > H1_MOMENTUM_MIN and chg5 > -5:
        # Older (>15min) + h1>+5% + chg5>-5% → 45s cooldown
        state = STATE_OLDER_COOLDOWN
        cooldown_end = time.time() + 45
    else:
        # Otherwise → 30s base recheck
        state = STATE_BASE_WAIT
        cooldown_end = time.time() + 30"""

code = code.replace(old_add, new_add)

# Write modified code
with open('/root/Dex-trading-bot/gmgn_scanner.py', 'w') as f:
    f.write(code)

print("Done - check syntax with: cd /root/Dex-trading-bot && python -m py_compile gmgn_scanner.py")