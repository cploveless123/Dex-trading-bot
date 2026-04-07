import os
import sys

def send_trade_alert(token, amount_sol, entry_price, fdv, liquidity, dex_link):
    message = f"""🟢 NEW TRADE EXECUTED

{token} | {amount_sol} SOL
Entry: ${entry_price:.4f}
FDV: ${fdv:,} | Liq: ${liquidity:,.0f}
{dex_link}"""
    
    # Use existing Telegram bot
    bot_token = "8767746012:AAEAUg-yCC8uZ-U2y-VBiuKS7qGm58XYQeg"
    chat_id = "6402511249"  # Chris's ID
    
    os.system(f'''curl -s -X POST "https://api.telegram.org/bot{bot_token}/sendMessage" \
    -d "chat_id={chat_id}" \
    -d "text={message}" \
    -d "parse_mode=Markdown" 2>/dev/null''')
    
    print(f"Alert sent for {token}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        send_trade_alert(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), int(sys.argv[4]), float(sys.argv[5]), sys.argv[6])
