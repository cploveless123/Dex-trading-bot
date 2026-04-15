#!/usr/bin/env python3
with open('gmgn_scanner.py') as f:
    content = f.read()

old = """    # ATH divergence
    if ath_mcap > 0:
        ath_dist = ((ath_mcap - mcap) / ath_mcap) * 100
        if ath_dist > ATH_DIVERGENCE_MAX: return None, f"ATH dist {ath_dist:.1f}% > {ATH_DIVERGENCE_MAX}%"
    
    # Dip"""

new = """    # ATH divergence
    if ath_mcap > 0:
        ath_dist = ((ath_mcap - mcap) / ath_mcap) * 100
        if ath_dist > ATH_DIVERGENCE_MAX: return None, f"ATH dist {ath_dist:.1f}% > {ATH_DIVERGENCE_MAX}%"
    elif mcap > 20000:
        # No ATH data and mcap > $20K - reject (risk of fallen giant with unknown ATH)
        return None, f"No ATH data for mcap ${mcap:,.0f} > $20K (risk of fallen giant)"
    
    # Fallen Giant Detection: massive h1 + small mcap = already pumped and crashed
    if h1 > 500 and mcap < 30000:
        return None, f"Fallen giant: h1={h1:+.0f}% + mcap=${mcap:,.0f} < $30K (likely already pumped)"
    
    # Dip"""

if old in content:
    content = content.replace(old, new)
    with open('gmgn_scanner.py', 'w') as f:
        f.write(content)
    print("ATH fix applied!")
else:
    print("Target string not found")
    # Find ATH section
    idx = content.find('# ATH divergence')
    if idx >= 0:
        print(f"Found at char {idx}: {repr(content[idx:idx+300])}")
    else:
        print("ATH section not found")
