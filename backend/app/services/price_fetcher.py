"""Pluggable stock/ETF price fetching service.

Select provider via the PRICE_PROVIDER env var (default: "finnhub").
Each provider requires its own env vars (see provider docstrings).

To add a new provider:
1. Create a class implementing the PriceProvider protocol below.
2. Register it in PROVIDERS at the bottom of this file.
3. Set PRICE_PROVIDER=<name> in the environment.
"""

import os
from decimal import Decimal
from typing import Optional, Protocol, runtime_checkable

import httpx


# ─── Protocol ────────────────────────────────────────────────────────────────

@runtime_checkable
class PriceProvider(Protocol):
    """Interface every price provider must satisfy."""

    async def fetch_prices(self, tickers: list[str]) -> dict[str, Optional[Decimal]]:
        """Return a mapping of ticker → current price (or None if unavailable)."""
        ...


# ─── Finnhub provider ────────────────────────────────────────────────────────

class FinnhubProvider:
    """Fetches prices from the Finnhub free API (https://finnhub.io).

    Requirements:
      - FINNHUB_API_KEY env var set to a valid Finnhub API key.
        Free registration at https://finnhub.io (60 req/min, no credit card).
    """

    BASE_URL = "https://finnhub.io/api/v1/quote"

    def __init__(self) -> None:
        self._api_key = os.environ.get("FINNHUB_API_KEY")
        if not self._api_key:
            raise RuntimeError(
                "FINNHUB_API_KEY is not set. "
                "Register for a free key at https://finnhub.io and set the env var."
            )

    async def fetch_prices(self, tickers: list[str]) -> dict[str, Optional[Decimal]]:
        results: dict[str, Optional[Decimal]] = {}
        async with httpx.AsyncClient(timeout=10.0) as client:
            for ticker in tickers:
                try:
                    resp = await client.get(
                        self.BASE_URL,
                        params={"symbol": ticker, "token": self._api_key},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    # Finnhub returns {"c": current_price, ...}; c=0 means not found
                    price = data.get("c")
                    results[ticker] = Decimal(str(price)) if price else None
                except Exception:
                    results[ticker] = None
        return results


# ─── Stooq provider ──────────────────────────────────────────────────────────

class StooqProvider:
    """Fetches prices from Stooq (https://stooq.com).

    No API key required. Covers US stocks, ETFs, and mutual fund NAVs that
    Finnhub misses (e.g. FDEWX, FDRXX). Appends '.US' suffix for US securities.
    """

    BASE_URL = "https://stooq.com/q/l/"

    async def fetch_prices(self, tickers: list[str]) -> dict[str, Optional[Decimal]]:
        results: dict[str, Optional[Decimal]] = {}
        async with httpx.AsyncClient(timeout=10.0) as client:
            for ticker in tickers:
                try:
                    resp = await client.get(
                        self.BASE_URL,
                        params={"s": f"{ticker}.US", "f": "c", "e": "csv"},
                    )
                    resp.raise_for_status()
                    # Response: "Close\n45.23\n" (header + value)
                    lines = [ln.strip() for ln in resp.text.strip().splitlines() if ln.strip()]
                    if len(lines) >= 2 and lines[1] not in ("N/D", ""):
                        results[ticker] = Decimal(lines[1])
                    else:
                        results[ticker] = None
                except Exception:
                    results[ticker] = None
        return results


# ─── Finnhub + Stooq combined provider ───────────────────────────────────────

class FinnhubWithStooqFallbackProvider:
    """Tries Finnhub first; falls back to Stooq for tickers Finnhub can't price.

    This handles both exchange-listed securities (Finnhub) and US mutual fund
    NAVs (Stooq), with no extra configuration required beyond FINNHUB_API_KEY.
    """

    def __init__(self) -> None:
        self._finnhub = FinnhubProvider()
        self._stooq = StooqProvider()

    async def fetch_prices(self, tickers: list[str]) -> dict[str, Optional[Decimal]]:
        results = await self._finnhub.fetch_prices(tickers)
        missed = [t for t, p in results.items() if p is None]
        if missed:
            fallback = await self._stooq.fetch_prices(missed)
            results.update(fallback)
        return results


# ─── Alpha Vantage provider (stub) ───────────────────────────────────────────

class AlphaVantageProvider:
    """Fetches prices from Alpha Vantage (https://www.alphavantage.co).

    Requirements:
      - ALPHA_VANTAGE_KEY env var set to a valid API key.
        Free tier: 25 requests/day — sufficient for on-demand fetching with few tickers.

    NOTE: This is a stub. Implement fetch_prices() when needed.
    """

    def __init__(self) -> None:
        self._api_key = os.environ.get("ALPHA_VANTAGE_KEY")
        if not self._api_key:
            raise RuntimeError(
                "ALPHA_VANTAGE_KEY is not set. "
                "Get a free key at https://www.alphavantage.co/support/#api-key"
            )

    async def fetch_prices(self, tickers: list[str]) -> dict[str, Optional[Decimal]]:
        raise NotImplementedError(
            "AlphaVantageProvider is a stub — implement fetch_prices() to use it."
        )


# ─── Registry and factory ────────────────────────────────────────────────────

PROVIDERS: dict[str, type] = {
    "finnhub": FinnhubWithStooqFallbackProvider,  # Finnhub + Stooq fallback for mutual funds
    "finnhub-only": FinnhubProvider,              # Finnhub only, no fallback
    "stooq": StooqProvider,                       # Stooq only, no API key needed
    "alphavantage": AlphaVantageProvider,
}


def get_price_provider() -> PriceProvider:
    """Return the configured price provider instance.

    Reads PRICE_PROVIDER env var (default: "finnhub").
    "finnhub" uses Finnhub with automatic Stooq fallback for mutual fund NAVs.
    Raises RuntimeError for unknown provider names or missing env vars.
    """
    name = os.environ.get("PRICE_PROVIDER", "finnhub").lower()
    provider_cls = PROVIDERS.get(name)
    if provider_cls is None:
        raise RuntimeError(
            f"Unknown PRICE_PROVIDER={name!r}. "
            f"Valid options: {list(PROVIDERS.keys())}"
        )
    return provider_cls()
