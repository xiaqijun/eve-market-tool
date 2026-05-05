"""ESI (EVE Swagger Interface) async client with rate limiting, ETag caching,
and automatic pagination.

Uses httpx for async HTTP, a token-bucket for ESI rate limits,
and ETag/If-None-Match for efficient cache-aware requests.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Token Bucket rate limiter
# ---------------------------------------------------------------------------


class TokenBucket:
    """Async token bucket for ESI rate limiting.

    ESI uses a floating-window token-bucket system. Each successful
    request costs 2 tokens; 304 responses cost 1 token.
    """

    def __init__(self, budget: int = 12000, window_seconds: int = 300) -> None:
        self.budget = float(budget)
        self.window = float(window_seconds)
        self.tokens = self.budget
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        refill_rate = self.budget / self.window
        self.tokens = min(self.budget, self.tokens + elapsed * refill_rate)
        self.last_refill = now

    async def consume(self, tokens: int = 1) -> None:
        """Wait until at least `tokens` are available, then consume them."""
        while True:
            async with self._lock:
                self._refill()
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return
            # Not enough tokens — wait a bit and retry
            await asyncio.sleep(1.0)

    @property
    def available(self) -> float:
        self._refill()
        return self.tokens


# ---------------------------------------------------------------------------
# ETag cache
# ---------------------------------------------------------------------------


@dataclass
class CachedResponse:
    etag: str
    data: list[dict[str, Any]]
    cached_at: float = field(default_factory=time.monotonic)


class ETagCache:
    """In-memory ETag → response body cache.

    Cache entries are used for If-None-Match conditional requests.
    On a 304 response the cached body is returned, saving bandwidth
    and reducing token cost (1 token vs 2).
    """

    def __init__(self, ttl_seconds: float = 600) -> None:
        self._store: dict[str, CachedResponse] = {}
        self.ttl = ttl_seconds

    def get(self, url: str) -> CachedResponse | None:
        entry = self._store.get(url)
        if entry is None:
            return None
        if time.monotonic() - entry.cached_at > self.ttl:
            del self._store[url]
            return None
        return entry

    def set(self, url: str, etag: str, data: list[dict[str, Any]]) -> None:
        self._store[url] = CachedResponse(etag=etag, data=data)


# ---------------------------------------------------------------------------
# ESI client
# ---------------------------------------------------------------------------

ESI_RATE_LIMIT_ERROR = 429
ESI_SERVER_ERROR_MIN = 500


class EsiError(Exception):
    """Base exception for ESI client errors."""


class EsiRateLimitError(EsiError):
    """Raised when ESI returns 420 (error-rate limit) or repeated 429s."""


class EsiServerError(EsiError):
    """Raised when ESI returns a 5xx error after retries."""


def _is_retryable(exc: BaseException) -> bool:
    """Return True for transient errors worth retrying."""
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        # Retry rate-limit (429) and server errors (5xx)
        return code == ESI_RATE_LIMIT_ERROR or code >= ESI_SERVER_ERROR_MIN
    if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException)):
        return True
    return False


class EsiClient:
    """Async ESI API client with built-in rate limiting, ETag caching,
    automatic pagination, and retry logic.

    Usage::

        client = EsiClient()
        orders = await client.get_market_orders(10000002)
    """

    def __init__(
        self,
        base_url: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.base_url = base_url or settings.esi_base_url
        self.user_agent = user_agent or settings.esi_user_agent
        self._client: httpx.AsyncClient | None = None
        self._token_bucket = TokenBucket(budget=12000, window_seconds=300)
        self._etag_cache = ETagCache(ttl_seconds=600)

        # Per-endpoint rate limit grouping (approximate)
        self._route_buckets: dict[str, TokenBucket] = {}

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": self.user_agent},
                timeout=httpx.Timeout(30.0),
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Low-level request
    # ------------------------------------------------------------------

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        after=lambda rs: logger.warning(
            "ESI retry attempt %d for %s", rs.attempt_number, rs.args[0] if rs.args else "?"
        ),
    )
    async def _request(self, path: str) -> list[dict[str, Any]]:
        """Perform a single GET request to the ESI endpoint at *path*.

        Handles:
        - Token-bucket rate limiting (waits before sending)
        - ETag conditional requests (If-None-Match)
        - 304 Not Modified → returns cached data
        - 200 OK → updates ETag cache and returns new data
        """
        url = f"{self.base_url}{path}"

        # Wait for token bucket
        await self._token_bucket.consume(tokens=2)

        client = await self._get_client()
        headers: dict[str, str] = {}

        cached = self._etag_cache.get(url)
        if cached is not None:
            headers["If-None-Match"] = cached.etag

        logger.debug("ESI GET %s", url)
        response = await client.get(url, headers=headers)

        # 304 — use cached data (costs only 1 token in practice)
        if response.status_code == 304:
            if cached is not None:
                logger.debug("ESI 304 — cache hit for %s", url)
                return cached.data
            # No cache entry — fall through to fetch full response
            # Remove If-None-Match and retry
            del headers["If-None-Match"]
            response = await client.get(url, headers=headers)

        # Check for errors
        if response.status_code == 420:
            raise EsiRateLimitError("Error-rate limit exceeded (420)")

        response.raise_for_status()

        data: list[dict[str, Any]] = response.json()

        # Cache the response if there's an ETag
        etag = response.headers.get("ETag")
        if etag is not None:
            self._etag_cache.set(url, etag, data)

        return data

    # ------------------------------------------------------------------
    # Pagination helper
    # ------------------------------------------------------------------

    async def _get_all_pages(self, path_template: str) -> list[dict[str, Any]]:
        """Fetch all pages from a paginated endpoint.

        Reads the X-Pages header from the first request, then fetches
        remaining pages concurrently.
        """
        # First page to discover total pages
        first_path = path_template.format(page=1)
        client = await self._get_client()
        url = f"{self.base_url}{first_path}"

        await self._token_bucket.consume(tokens=2)
        response = await client.get(url, headers={"User-Agent": self.user_agent})

        if response.status_code == 420:
            raise EsiRateLimitError("Error-rate limit exceeded (420)")
        response.raise_for_status()

        data: list[dict[str, Any]] = response.json()
        total_pages = int(response.headers.get("X-Pages", 1))

        if total_pages <= 1:
            return data

        # Fetch remaining pages concurrently
        semaphore = asyncio.Semaphore(5)  # limit concurrency

        async def fetch_page(page: int) -> list[dict[str, Any]]:
            async with semaphore:
                return await self._request(path_template.format(page=page))

        tasks = [fetch_page(p) for p in range(2, total_pages + 1)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in results:
            if isinstance(res, Exception):
                logger.error("Failed to fetch a page: %s", res)
            else:
                data.extend(res)

        return data

    # ------------------------------------------------------------------
    # Public API — Market endpoints
    # ------------------------------------------------------------------

    async def get_market_orders(
        self,
        region_id: int,
        order_type: str = "all",
        type_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch all active market orders in *region_id*.

        Parameters
        ----------
        region_id:
            EVE region ID (e.g. 10000002 for The Forge / Jita).
        order_type:
            One of ``"all"``, ``"buy"``, ``"sell"``.
        type_id:
            Optional item type_id to filter on.
        """
        params = f"&order_type={order_type}"
        if type_id is not None:
            params += f"&type_id={type_id}"

        path = f"/markets/{region_id}/orders/?page={{page}}{params}"
        return await self._get_all_pages(path)

    async def get_market_history(
        self,
        region_id: int,
        type_id: int,
    ) -> list[dict[str, Any]]:
        """Fetch daily market history for *type_id* in *region_id*.

        Returns ~500 days of OHLCV data.
        """
        path = f"/markets/{region_id}/history/?type_id={type_id}"
        return await self._request(path)

    async def get_market_prices(self) -> list[dict[str, Any]]:
        """Universe-wide average and adjusted prices for all items."""
        return await self._request("/markets/prices/")

    async def get_market_groups(self) -> list[dict[str, Any]]:
        """List all market group IDs."""
        return await self._request("/markets/groups/")

    async def get_market_group(self, market_group_id: int) -> dict[str, Any]:
        """Detail for a specific market group."""
        path = f"/markets/groups/{market_group_id}/"
        result = await self._request(path)
        return result  # type: ignore[return-value]

    async def get_markets_region_types(self, region_id: int) -> list[int]:
        """List type_ids with active orders in a region."""
        path = f"/markets/{region_id}/types/"
        return await self._request(path)  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Public API — Universe endpoints
    # ------------------------------------------------------------------

    async def get_type_info(self, type_id: int, language: str = "zh") -> dict[str, Any]:
        """Fetch item name, description, volume, etc."""
        path = f"/universe/types/{type_id}/?language={language}"
        result = await self._request(path)
        return result  # type: ignore[return-value]

    async def get_station_info(self, station_id: int) -> dict[str, Any]:
        """Fetch station name, owner, position."""
        path = f"/universe/stations/{station_id}/"
        result = await self._request(path)
        return result  # type: ignore[return-value]

    async def get_system_info(self, system_id: int) -> dict[str, Any]:
        """Fetch solar system info."""
        path = f"/universe/systems/{system_id}/"
        result = await self._request(path)
        return result  # type: ignore[return-value]

    async def get_region_info(self, region_id: int) -> dict[str, Any]:
        """Fetch region info."""
        path = f"/universe/regions/{region_id}/"
        result = await self._request(path)
        return result  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Public API — Industry endpoints
    # ------------------------------------------------------------------

    async def get_industry_systems(self) -> list[dict[str, Any]]:
        """Cost indices for solar systems (for manufacturing job fees)."""
        return await self._request("/industry/systems/")

    async def get_industry_facilities(self) -> list[dict[str, Any]]:
        """List of industry facilities."""
        return await self._request("/industry/facilities/")
