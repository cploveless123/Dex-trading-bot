# Wilson Recovery Guide

## If Wilson (OpenClaw bot) is lost, follow these steps to fully restore:

---

## 1. Prerequisites

```bash
# Install required packages
pip install telethon requests solana pathlib python-dotenv
```

---

## 2. Clone Repositories

```bash
# Clone trading bot
git clone https://github.com/cploveless123/Dex-trading-bot.git
cd Dex-trading-bot

# Clone workspace (contains memory/wallets/skills)
git clone <your-workspace-repo>
```

---

## 3. Environment Setup

Create `.env` file with:
```
TELEGRAM_API_ID=30571469
TELEGRAM_API_HASH=85d1c3567f4182f4e4a88334ec04b935
GMGN_API_KEY=
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
```

---

## 4. Start Services

```bash
cd /path/to/Dex-trading-bot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start all services
nohup python -u combined_monitor.py > combined.log 2>&1 &
nohup python -u gmgn_listener.py > gmgn.log 2>&1 &
nohup python -u sim_trader.py > sim_trader.log 2>&1 &
```

---

## 5. Verify Running

```bash
# Check processes
ps aux | grep -E "combined|gmgn|sim_trader"

# Check logs
tail -20 combined.log
tail -20 gmgn.log
tail -20 sim_trader.log
```

---

## 6. Restore Memory

- `memory/wilson-skills.md` - Skills progress
- `memory/wallets/watchlist.json` - 28 tracked KOL wallets
- `memory/trading-patterns.md` - Pattern learnings
- `memory/2026-04-*.md` - Daily logs

---

## 7. Configuration

**Trading Filters:**
- Min Market Cap: $9K
- Min Liquidity: $9K  
- Min 1hr Volume: $5K
- Chain: SOL only

**Exit Strategy:**
- +20% → Sell 50% (take initial)
- +100% → Sell 90% (DCA out), keep 10% moon bag
- -20% → Stop loss

---

## 8. Telegram Alerts

Bot token: `8650620888:AAHMOK5S6mRx5eZR_Kr0APe_NiMCXAg0Vys`
Chat ID: `6402511249`

---

## Quick Start Command

```bash
cd Dex-trading-bot
source venv/bin/activate
python -u combined_monitor.py & python -u gmgn_listener.py & python -u sim_trader.py
```

---

*Last updated: 2026-04-06*