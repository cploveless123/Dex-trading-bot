#!/usr/bin/env python3
"""Rewrite YOUNG_COOLDOWN, OLDER_COOLDOWN, BASE_WAIT handling in gmgn_scanner.py"""

with open('/root/Dex-trading-bot/gmgn_scanner.py', 'r') as f:
    code = f.read()

# 1. Replace the OLDER_COOLDOWN transition section (lines ~626-639)
# The problem: it's inside "if state == STATE_BASE_WAIT" but we want standalone YOUNG/OLDER states
old_young_older = """        # === YOUNG COOLDOWN PATH (<15min + h1>5% + chg5>-5%) ===
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
            continue"""

new_young_older = """        # === YOUNG COOLDOWN PATH: 45s wait → check chg1 and chg5 → BUY ===
        if state == STATE_YOUNG_COOLDOWN:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                # Check chg1 during cooldown - if < -5% go to recovery
                if chg1 < -5:
                    data['state'] = STATE_CHG1_RECHECK
                    data['cooldown_end'] = now + 15
                    data['lowest_mcap'] = mcap
                    print(f"   [CHG1_FALL] {result['token']}: chg1={chg1:.1f}% < -5% | recovery 15s")
                continue
            # 45s done - verify chg1 >= -5% AND chg5 >= +2%
            if chg1 >= -5 and chg5 >= MIN_CHG5_FOR_BUY:
                final_result, fail_reason = scan_token(data['token_data'])
                if final_result:
                    print(f"   [BUY_YOUNG] {result['token']}: chg1={chg1:+.1f}% >= -5% + chg5={chg5:+.1f}% >= +2% | BUY!")
                    buy_token(addr, final_result)
                    to_remove.append(addr)
                    continue
                else:
                    REJECTED_TEMP[addr] = {'ts': now, 'reason': fail_reason}
                    to_remove.append(addr)
                    continue
            else:
                # Not ready - go to base rechecks
                data['state'] = STATE_BASE_WAIT
                data['cooldown_end'] = now + 30
                print(f"   [YOUNG_NOT_READY] {result['token']}: chg1={chg1:.1f}% chg5={chg5:.1f}% | base recheck")
            data['chg5_prev'] = chg5
            data['h1_prev'] = h1
            continue
        
        # === OLDER COOLDOWN PATH: 45s wait → check chg1 and chg5 → BUY ===
        if state == STATE_OLDER_COOLDOWN:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                if chg1 < -5:
                    data['state'] = STATE_CHG1_RECHECK
                    data['cooldown_end'] = now + 15
                    data['lowest_mcap'] = mcap
                    print(f"   [CHG1_FALL] {result['token']}: chg1={chg1:.1f}% < -5% | recovery 15s")
                continue
            # 45s done
            if chg1 >= -5 and chg5 >= MIN_CHG5_FOR_BUY:
                final_result, fail_reason = scan_token(data['token_data'])
                if final_result:
                    print(f"   [BUY_OLDER] {result['token']}: chg1={chg1:+.1f}% >= -5% + chg5={chg5:+.1f}% >= +2% | BUY!")
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
                print(f"   [OLDER_NOT_READY] {result['token']}: chg1={chg1:.1f}% chg5={chg5:.1f}% | base recheck")
            data['chg5_prev'] = chg5
            data['h1_prev'] = h1
            continue"""

code = code.replace(old_young_older, new_young_older)

# 2. Fix BASE_WAIT: 30s → verify chg1 > chg1_prev + 3% → BUY
old_base_wait = """        if state == STATE_BASE_WAIT:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                continue
            # Check chg5
            if chg5 >= MIN_CHG5_FOR_BUY:
                # Ready - verify and buy
                final_result, fail_reason = scan_token(data['token_data'])
                if final_result:
                    print(f"   [BUY_NORMAL] {result['token']}: chg5={chg5:+.1f}% | BUY!")
                    buy_token(addr, final_result)
                    to_remove.append(addr)
                    continue
                else:
                    print(f"   [REJECT_V73] {result['token']}: {fail_reason}")
                    REJECTED_TEMP[addr] = {'ts': now, 'reason': fail_reason}
                    to_remove.append(addr)
                    continue
            else:
                data['cooldown_end'] = now + STATE_BASE_WAIT
                print(f"   [BASE_RECHECK] {result['token']}: chg5={chg5:+.1f}% < +{MIN_CHG5_FOR_BUY}% | wait {STATE_BASE_WAIT}s")
            data['chg5_prev'] = chg5
            data['h1_prev'] = h1
            continue"""

new_base_wait = """        if state == STATE_BASE_WAIT:
            remaining = data['cooldown_end'] - now
            if remaining > 0:
                data['chg5_prev'] = chg5
                data['h1_prev'] = h1
                continue
            # 30s done - verify chg1 > chg5_prev + 3% (Chris spec)
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

with open('/root/Dex-trading-bot/gmgn_scanner.py', 'w') as f:
    f.write(code)

print("Done. Compile with: cd /root/Dex-trading-bot && /root/Dex-trading-bot/venv/bin/python -m py_compile gmgn_scanner.py")