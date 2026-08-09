"""Crypto market data service for Professor Pepe."""

import time
import logging
from typing import Optional

import httpx

from core.config import COINGECKO_API_KEY

logger = logging.getLogger(__name__)

# Simple in-memory cache: {"data": "...", "time": timestamp}
_cache: dict[str, float | str] = {}

async def get_pepe_market_data(http_client: httpx.AsyncClient) -> str:
    """
    Fetch live PEP market data from CoinGecko with a 60-second cache.
    Returns a formatted context string to be injected into the LLM prompt.
    """
    now = time.time()
    
    # Return cached data if valid (< 60s old)
    cache_time = _cache.get("time")
    cache_data = _cache.get("data")
    if isinstance(cache_time, float) and isinstance(cache_data, str):
        if now - cache_time < 60:
            return cache_data

    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "pepecoin-network",
        "vs_currencies": "usd",
        "include_market_cap": "true",
        "include_24hr_vol": "true",
        "include_24hr_change": "true"
    }
    
    headers = {}
    if COINGECKO_API_KEY:
        # According to CoinGecko docs, demo keys use this header
        headers["x-cg-demo-api-key"] = COINGECKO_API_KEY

    try:
        r = await http_client.get(url, params=params, headers=headers)
        r.raise_for_status()
        data = r.json().get("pepecoin-network", {})
        
        context_str = ""
        if data:
            price = data.get("usd", 0)
            mc = data.get("usd_market_cap", 0)
            change = data.get("usd_24h_change", 0)
            vol = data.get("usd_24h_vol", 0)
            
            context_str += (
                "CURRENT $PEP (Pepecoin) MARKET DATA (from CoinGecko):\n"
                f"- Price: ${price}\n"
                f"- Market Cap: ${mc:,.0f}\n"
                f"- 24h Volume: ${vol:,.0f}\n"
                f"- 24h Change: {change:+.2f}%\n"
            )
            
        # Fetch on-chain data from Pepeblocks
        try:
            r_blocks = await http_client.get("https://pepeblocks.com/ext/getsummary")
            if r_blocks.status_code == 200:
                block_data = r_blocks.json()
                hashrate = block_data.get("hashrate", 0)
                difficulty = block_data.get("difficulty", 0)
                blocks = block_data.get("blockcount", 0)
                supply = block_data.get("supply", 0)
                
                # Convert hashrate to TH/s or PH/s
                hr_ths = hashrate / 1e12
                
                context_str += (
                    "\nCURRENT ON-CHAIN DATA (from Pepeblocks Explorer):\n"
                    f"- Current Block: {blocks:,}\n"
                    f"- Difficulty: {difficulty:,.0f}\n"
                    f"- Hashrate: {hr_ths:,.2f} TH/s\n"
                    f"- Circulating Supply: {supply:,.0f} PEP\n"
                )
        except Exception as e:
            logger.error(f"Failed to fetch pepeblocks data: {e}")

        if context_str:
            context_str += "\nUse this real-time data to answer questions about the current network statistics."
            _cache["data"] = context_str
            _cache["time"] = now
            return context_str
            
    except Exception as e:
        logger.error(f"Failed to fetch coingecko data: {e}")
        
    return ""
