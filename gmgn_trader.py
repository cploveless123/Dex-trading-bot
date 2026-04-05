#!/usr/bin/env python3
"""
GMGN Solana Trading API Integration
No API key required - free to use
"""
import asyncio
import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict

import aiohttp


# Configuration
API_BASE = "https://gmgn.ai/defi/router/v1/sol/tx"

# Token addresses
SOL_ADDRESS = "So11111111111111111111111111111111111111112"

TRADES_DIR = Path(__file__).parent.parent / "trades"
SIGNALS_DIR = Path(__file__).parent.parent / "signals"


class GMGNTrader:
    def __init__(self, wallet_address: str = ""):
        self.wallet_address = wallet_address
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    async def get_swap_route(
        self,
        token_in: str,
        token_out: str,
        amount_lamports: int,
        slippage: float = 1.0
    ) -> Optional[Dict]:
        """
        Get swap route from GMGN
        amount_lamports: 100000000 = 0.1 SOL
        """
        url = f"{API_BASE}/get_swap_route"
        params = {
            "token_in_address": token_in,
            "token_out_address": token_out,
            "in_amount": str(amount_lamports),
            "from_address": self.wallet_address,
            "slippage": slippage,
            "swap_mode": "ExactIn"
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json"
        }
        
        try:
            async with self.session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(30)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('code') == 0:
                        return data.get('data')
                    else:
                        print(f"Error: {data.get('msg')}")
                else:
                    print(f"HTTP {resp.status}")
        except Exception as e:
            print(f"Request error: {e}")
        
        return None
    
    async def submit_transaction(self, signed_tx_base64: str) -> Optional[Dict]:
        """Submit signed transaction to GMGN"""
        url = f"{API_BASE}/submit_signed_transaction"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/json"
        }
        
        body = {"signed_tx": signed_tx_base64}
        
        try:
            async with self.session.post(url, json=body, headers=headers, timeout=aiohttp.ClientTimeout(30)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('code') == 0:
                        return data.get('data')
        except Exception as e:
            print(f"Submit error: {e}")
        
        return None
    
    async def get_transaction_status(self, tx_hash: str, last_valid_height: int) -> Optional[Dict]:
        """Check transaction status"""
        url = f"{API_BASE}/get_transaction_status"
        params = {
            "hash": tx_hash,
            "last_valid_height": last_valid_height
        }
        
        try:
            async with self.session.get(url, params=params, timeout=aiohttp.ClientTimeout(30)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get('data')
        except Exception as e:
            print(f"Status check error: {e}")
        
        return None
    
    async def wait_for_confirmation(self, tx_hash: str, last_valid_height: int, timeout: int = 60) -> bool:
        """Wait for transaction confirmation"""
        import time
        start = time.time()
        
        while time.time() - start < timeout:
            status = await self.get_transaction_status(tx_hash, last_valid_height)
            
            if status:
                if status.get('success'):
                    print(f"✅ Transaction confirmed: {tx_hash[:20]}...")
                    return True
                elif status.get('expired'):
                    print(f"⏰ Transaction expired")
                    return False
            
            await asyncio.sleep(2)
        
        print(f"⏱️ Timeout waiting for confirmation")
        return False


async def test_route():
    """Test the swap route endpoint"""
    # Test with a dummy wallet (won't work for real trades but tests the endpoint)
    test_wallet = "2kpJ5QRh16aRQ4oLZ5LnucHFDAZtEFz6omqWWMzDSNrx"
    
    async with GMGNTrader(test_wallet) as trader:
        # Try to get a quote (0.1 SOL = 100000000 lamports)
        result = await trader.get_swap_route(
            token_in=SOL_ADDRESS,
            token_out="EPjFWdd5AufqSSCwMqb11zHhN1K4EwUatA6wDXkW5B",  # USDC
            amount_lamports=100000000,  # 0.1 SOL
            slippage=1.0
        )
        
        if result:
            print("✅ GMGN API working!")
            print(f"Quote: {json.dumps(result.get('quote', {}), indent=2)}")
        else:
            print("❌ GMGN API not responding")


if __name__ == "__main__":
    asyncio.run(test_route())