#!/usr/bin/env python3
"""Fix gmgn_scanner.py to implement Chris's cooldown spec exactly"""

with open('/root/Dex-trading-bot/gmgn_scanner.py', 'r') as f:
    code = f.read()

# 1. Add CHG1_RECHECK and CHG1_VERIFY to entry conditions in add_to_cooldown
old_add_to_cooldown_entry = """    if pump_triggered:
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

new_add_to_cooldown_entry = """    chg1 = result.get('chg1', 0)
    
    # Check chg1 immediately - if < -5% go to CHG1_RECHECK
    if chg1 < -5:
        state = STATE_CHG1_RECHECK
        cooldown_end = time.time() + 15  # 15s recheck
        result['lowest_mcap'] = result.get('mcap', 0)
    elif pump_triggered:
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
        # Otherwise → 30s base recheck (verify chg1 > +3% from last)
        state = STATE_BASE_WAIT
        cooldown_end = time.time() + 30"""

code = code.replace(old_add_to_cooldown_entry, new_add_to_cooldown_entry)

# 2. Update COOLDOWN_WATCH init to include lowest_mcap
old_watch_init = """        'lowest_mcap': result.get('mcap', 0),  # Track lowest mcap for chg1 recovery
    }"""

new_watch_init = """        'lowest_mcap': result.get('mcap', 0),  # Track lowest mcap for chg1 recovery
        'chg1_prev': result.get('chg1', 0),  # Track chg1 for base path verify
    }"""

code = code.replace(old_watch_init, new_watch_init)

# 3. Add lowest_mcap tracking in scan_cycle (from fresh data)
old_fresh_update = """        # Only update if token_info returned valid data (not 0/None)
        if fresh_h1 > 0:
            chg5 = float(fresh_chg5)
            h1 = float(fresh_h1)
            chg1 = float(fresh_chg1)
            mcap = float(fresh_mcap)
            result['chg5'] = chg5
            result['h1'] = h1
            result['chg1'] = chg1
            result['mcap'] = mcap"""

new_fresh_update = """        # Only update if token_info returned valid data (not 0/None)
        if fresh_h1 > 0:
            chg5 = float(fresh_chg5)
            h1 = float(fresh_h1)
            chg1 = float(fresh_chg1)
            mcap = float(fresh_mcap)
            result['chg5'] = chg5
            result['h1'] = h1
            result['chg1'] = chg1
            result['mcap'] = mcap
            # Update lowest_mcap if in CHG1_RECHECK state
            if state == STATE_CHG1_RECHECK:
                data['lowest_mcap'] = min(data.get('lowest_mcap', mcap), mcap)"""

code = code.replace(old_fresh_update, new_fresh_update)

# 4. Add STATE_CHG1_RECHECK handling BEFORE other state checks
# Find the pump path start and add chg1 check before it
old_pump_start = """        # === PUMP PATH ===
        if state == STATE_PUMP_WAIT_1:
            # Check Fallen Giant BEFORE wasting time in pump cooldown"""

new_pump_start = """        # === CHG1 < -5% PATH: 15s rechecks until mcap > +5% from lowest ===
        if state == STATE_CHG1_RECHECK:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                continue
            # Timer expired - check if mcap recovered > +5% from lowest
            recovery_target = data['lowest_mcap'] * 1.05
            if mcap >= recovery_target:
                # Recovered! Go to verify
                data['state'] = STATE_CHG1_VERIFY
                data['cooldown_end'] = now + 15
                print(f"   [CHG1_OK] {result['token']}: mcap={mcap:,.0f} >= {recovery_target:,.0f} (+5% from low) | verify 15s")
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                continue
            else:
                # Still low - update lowest and recheck
                data['lowest_mcap'] = min(data.get('lowest_mcap', mcap), mcap)
                data['cooldown_end'] = now + 15
                data['recheck_count'] = data.get('recheck_count', 0) + 1
                print(f"   [CHG1_RECHECK] {result['token']}: mcap={mcap:,.0f} < {recovery_target:,.0f} | recheck 15s")
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                continue
        
        # === CHG1_VERIFY: 15s verify then BUY ===
        if state == STATE_CHG1_VERIFY:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                continue
            # Verify complete - BUY!
            final_result, fail_reason = scan_token(data['token_data'])
            if final_result:
                print(f"   [BUY_CHG1] {result['token']}: chg1 recovered | BUY!")
                buy_token(addr, final_result)
                to_remove.append(addr)
                continue
            else:
                REJECTED_TEMP[addr] = {'ts': now, 'reason': fail_reason}
                to_remove.append(addr)
                continue
        
        # === PUMP PATH ===
        if state == STATE_PUMP_WAIT_1:
            # Check Fallen Giant BEFORE wasting time in pump cooldown"""

code = code.replace(old_pump_start, new_pump_start)

# 5. Fix BASE_WAIT to check chg1 > +3% from last (Chris spec)
old_base_wait = """        # === BASE PATH (chg5 > +2% but not young/older momentum) ===
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
            continue"""

new_base_wait = """        # === BASE PATH: 30s → verify chg1 > +3% from last check → BUY ===
        if state == STATE_BASE_WAIT:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                continue
            # Timer expired - check chg1 > +3% from chg5_prev (Chris spec)
            chg1_threshold = data.get('chg5_prev', 0) + 3
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
                data['cooldown_end'] = now + 30
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                print(f"   [BASE_RECHECK] {result['token']}: chg1={chg1:+.1f}% < {chg1_threshold:+.1f}% from last | recheck 30s")
                continue"""

code = code.replace(old_base_wait, new_base_wait)

# 6. Update YOUNG/OLDER cooldown to use proper 45s → BUY (no post-cooldown)
old_young_cooldown = """        # === YOUNG COOLDOWN PATH (<15min + h1>5% + chg5>-5%) ===
        if state == STATE_YOUNG_COOLDOWN:
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
                continue"""

new_young_cooldown = """        # === YOUNG COOLDOWN PATH (<15min + h1>+5% + chg5>-5%) → 45s → BUY if chg5 > +2% ===
        if state == STATE_YOUNG_COOLDOWN:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                continue
            # 45s cooldown done - buy if chg5 still good
            if chg5 >= MIN_CHG5_FOR_BUY:
                final_result, fail_reason = scan_token(data['token_data'])
                if final_result:
                    print(f"   [BUY_YOUNG] {result['token']}: chg5={chg5:+.1f}% | BUY after 45s!")
                    buy_token(addr, final_result)
                    to_remove.append(addr)
                    continue
                else:
                    REJECTED_TEMP[addr] = {'ts': now, 'reason': fail_reason}
                    to_remove.append(addr)
                    continue
            else:
                data['state'] = STATE_BASE_WAIT
                data['cooldown_end'] = now + 30
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                print(f"   [YOUNG_DROP] {result['token']}: chg5={chg5:+.1f}% < +{MIN_CHG5_FOR_BUY}% | base recheck")
                continue"""

code = code.replace(old_young_cooldown, new_young_cooldown)

old_older_cooldown = """        # === OLDER COOLDOWN PATH (>15min + h1>5% + chg5>-5%) ===
        if state == STATE_OLDER_COOLDOWN:
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
                continue"""

new_older_cooldown = """        # === OLDER COOLDOWN PATH (>15min + h1>+5% + chg5>-5%) → 45s → BUY if chg5 > +2% ===
        if state == STATE_OLDER_COOLDOWN:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                continue
            # 45s cooldown done - buy if chg5 still good
            if chg5 >= MIN_CHG5_FOR_BUY:
                final_result, fail_reason = scan_token(data['token_data'])
                if final_result:
                    print(f"   [BUY_OLDER] {result['token']}: chg5={chg5:+.1f}% | BUY after 45s!")
                    buy_token(addr, final_result)
                    to_remove.append(addr)
                    continue
                else:
                    REJECTED_TEMP[addr] = {'ts': now, 'reason': fail_reason}
                    to_remove.append(addr)
                    continue
            else:
                data['state'] = STATE_BASE_WAIT
                data['cooldown_end'] = now + 30
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                print(f"   [OLDER_DROP] {result['token']}: chg5={chg5:+.1f}% < +{MIN_CHG5_FOR_BUY}% | base recheck")
                continue"""

code = code.replace(old_older_cooldown, new_older_cooldown)

with open('/root/Dex-trading-bot/gmgn_scanner.py', 'w') as f:
    f.write(code)

print("Done - compile with: cd /root/Dex-trading-bot && /root/Dex-trading-bot/venv/bin/python -m py_compile gmgn_scanner.py")