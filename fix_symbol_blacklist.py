#!/usr/bin/env python3
with open('gmgn_scanner.py') as f:
    content = f.read()

old = """    if addr in PERM_BLACKLIST: return None, "blacklisted\""""

new = """    # Symbol blacklist: block re-buy of same symbol (pump.fun allows duplicate names)
    symbol_blacklist = set()
    try:
        with open(TRADES_FILE) as sf:
            for sline in sf:
                t = json.loads(sline)
                if t.get('action') == 'BUY' and t.get('token_name'):
                    symbol_blacklist.add(t['token_name'].lower())
        if symbol.lower() in symbol_blacklist:
            return None, f"symbol {symbol} already traded"
    except: pass
    
    if addr in PERM_BLACKLIST: return None, "blacklisted\""""

if old in content:
    content = content.replace(old, new)
    with open('gmgn_scanner.py', 'w') as f:
        f.write(content)
    print("Symbol blacklist applied!")
else:
    print("Target string not found")
