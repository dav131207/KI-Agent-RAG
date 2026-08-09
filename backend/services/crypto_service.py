"""Crypto market data service for Professor Pepe."""

import os
import time
import logging
from typing import Any, Optional

import httpx

from core.config import COINGECKO_API_KEY

logger = logging.getLogger(__name__)

# Simple in-memory cache: {"data": "...", "time": timestamp}
_cache: dict[str, float | str] = {}

# Structured chain/market snapshot, cached alongside the formatted string so
# callers that need numbers do not have to parse the prompt text back apart.
_chain_cache: dict[str, Any] = {}

# Every known Pepecoin explorer sits behind Cloudflare, which rejects requests
# from datacenter IPs on some sites but not others. One host being blocked from
# a given deployment says nothing about the next, so they are tried in order.
# Override with PEPE_EXPLORERS (comma-separated) to add or reorder mirrors.
DEFAULT_EXPLORERS = "https://pepeblocks.com,https://pepeplorer.com"
EXPLORER_BASES = [
    host.strip().rstrip("/")
    for host in os.getenv("PEPE_EXPLORERS", DEFAULT_EXPLORERS).split(",")
    if host.strip()
]

# Identify the caller instead of sending httpx's default agent.
EXPLORER_HEADERS = {
    "User-Agent": "ProfessorPepe/1.0 (+https://github.com/dav131207/KI-Agent-RAG)",
    "Accept": "application/json",
}


def _normalise_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """
    Map an explorer's getsummary payload onto our field names.

    Iquidus forks disagree on key names: pepeblocks uses last_price_usd and
    exposes peers on a separate endpoint, pepeplorer uses lastUSDPrice and
    inlines connections. Both spellings are accepted.
    """
    hashrate_hs = _as_float(summary.get("hashrate"))
    price = summary.get("last_price_usd")
    if price is None:
        price = summary.get("lastUSDPrice", summary.get("lastPrice"))

    return {
        "block_height": _as_int(summary.get("blockcount")),
        "difficulty": _as_float(summary.get("difficulty")),
        "supply": _as_float(summary.get("supply")),
        "hashrate_hs": hashrate_hs,
        "hashrate_ths": hashrate_hs / 1e12 if hashrate_hs is not None else None,
        "price_usd": _as_float(price),
        "connection_count": _as_int(summary.get("connections")),
    }


async def get_pepe_chain_data(http_client: httpx.AsyncClient) -> dict[str, Any]:
    """
    Fetch a structured on-chain snapshot from the first explorer that answers.

    Returns raw numbers (not formatted strings) so chart builders and the prompt
    formatter share one source of truth. Returns {} when every explorer fails.
    """
    now = time.time()
    cached = _chain_cache.get("data")
    cached_at = _chain_cache.get("time")
    if isinstance(cached, dict) and isinstance(cached_at, float) and now - cached_at < 60:
        return cached

    snapshot: dict[str, Any] = {}
    source: Optional[str] = None

    for base in EXPLORER_BASES:
        try:
            r = await http_client.get(
                f"{base}/ext/getsummary", headers=EXPLORER_HEADERS, timeout=10
            )
            r.raise_for_status()
            candidate = _normalise_summary(r.json())
            if candidate.get("hashrate_ths") is None:
                logger.warning(f"Explorer {base} returned no hashrate; trying next")
                continue
            snapshot, source = candidate, base
            break
        except Exception as e:
            # Logged per host so the deployment's logs name the working mirror.
            logger.warning(f"Explorer {base} unavailable: {e}")

    if not snapshot:
        logger.error(f"No explorer reachable (tried: {', '.join(EXPLORER_BASES)})")
        return {}

    # pepeblocks omits peers from getsummary; fetch it separately when missing.
    if snapshot.get("connection_count") is None:
        try:
            r_peers = await http_client.get(
                f"{source}/api/getconnectioncount", headers=EXPLORER_HEADERS, timeout=10
            )
            if r_peers.status_code == 200:
                snapshot["connection_count"] = _as_int(r_peers.text.strip())
        except Exception as e:
            logger.warning(f"Failed to fetch connection count from {source}: {e}")

    snapshot["source"] = source
    logger.info(f"On-chain snapshot from {source}")

    _chain_cache["data"] = snapshot
    _chain_cache["time"] = now
    return snapshot


def _as_float(value: Any) -> Optional[float]:
    """Coerce an explorer value to float, tolerating strings and nulls."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> Optional[int]:
    """Coerce an explorer value to int, tolerating strings and nulls."""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def format_hashrate(hashrate_ths: Optional[float]) -> str:
    """Render a TH/s figure in the largest unit that keeps it readable."""
    if not hashrate_ths:
        return "n/a"
    if hashrate_ths >= 1000:
        return f"{hashrate_ths / 1000:.2f} PH/s"
    return f"{hashrate_ths:.2f} TH/s"

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

    context_str = ""

    # CoinGecko's free tier rate-limits aggressively on shared egress IPs. Its
    # failure must not take the explorer data down with it, so it gets its own
    # try block rather than wrapping the on-chain fetch below.
    try:
        r = await http_client.get(url, params=params, headers=headers)
        r.raise_for_status()
        data = r.json().get("pepecoin-network", {})

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
            
    except Exception as e:
        logger.error(f"Failed to fetch coingecko data: {e}")

    try:
        # Fetch on-chain data from Pepeblocks (structured, shared with charts).
        chain = await get_pepe_chain_data(http_client)
        if chain:
            context_str += "\nCURRENT ON-CHAIN DATA (from Pepeblocks Explorer):\n"
            if chain.get("block_height") is not None:
                context_str += f"- Current Block: {chain['block_height']:,}\n"
            if chain.get("difficulty") is not None:
                context_str += f"- Difficulty: {chain['difficulty']:,.0f}\n"
            if chain.get("hashrate_ths") is not None:
                context_str += f"- Hashrate: {chain['hashrate_ths']:,.2f} TH/s\n"
            if chain.get("connection_count") is not None:
                context_str += f"- Connected Peers (explorer node): {chain['connection_count']}\n"
            if chain.get("supply") is not None:
                context_str += f"- Circulating Supply: {chain['supply']:,.0f} PEP\n"

        if context_str:
            context_str += (
                "\n\nKNOWN ECOSYSTEM EXPLORERS & POOLS:\n"
                "- pepeblocks.com (Primary Explorer)\n"
                "- pepecoinexplorer.com (Explorer)\n"
                "- pepeplorer.com (Explorer)\n"
                "- peppool.space (Mining Pool)\n"
                "- pepecoinservice.org (Services/Explorer)\n"
                "\nUse this real-time data and these resources to answer questions about the current network statistics or point users to verifications."
            )
            _cache["data"] = context_str
            _cache["time"] = now
            return context_str

    except Exception as e:
        logger.error(f"Failed to build on-chain context: {e}")


    return ""
