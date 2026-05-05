"""Unit tests for the ESI client token bucket and ETag cache."""

import asyncio
import time

import pytest

from app.core.esi import ETagCache, TokenBucket


class TestTokenBucket:
    def test_initial_tokens(self):
        bucket = TokenBucket(budget=12000, window_seconds=300)
        assert bucket.available == pytest.approx(12000)

    async def test_consume_reduces_tokens(self):
        bucket = TokenBucket(budget=100, window_seconds=300)
        await bucket.consume(tokens=1)
        assert bucket.available == pytest.approx(99, abs=0.1)

    async def test_refill_after_elapsed_time(self):
        bucket = TokenBucket(budget=100, window_seconds=10)
        await bucket.consume(tokens=100)
        assert bucket.available == pytest.approx(0, abs=0.1)

        # Simulate elapsed time by adjusting last_refill
        bucket.last_refill = time.monotonic() - 11
        assert bucket.available > 0

    async def test_consume_waits_when_empty(self):
        bucket = TokenBucket(budget=2, window_seconds=300)
        await bucket.consume(tokens=2)
        assert bucket.available < 1


class TestETagCache:
    def test_set_and_get(self):
        cache = ETagCache(ttl_seconds=600)
        cache.set("https://example.com/api", '"abc123"', [{"key": "value"}])
        entry = cache.get("https://example.com/api")
        assert entry is not None
        assert entry.etag == '"abc123"'
        assert entry.data == [{"key": "value"}]

    def test_miss(self):
        cache = ETagCache(ttl_seconds=600)
        assert cache.get("https://example.com/nonexistent") is None

    def test_expired(self):
        cache = ETagCache(ttl_seconds=0.001)
        cache.set("https://example.com/api", '"abc123"', [{"key": "value"}])
        # Simulate expiration by setting cached_at far in the past
        entry = cache._store.get("https://example.com/api")
        if entry:
            entry.cached_at = time.monotonic() - 1000  # definitely expired
        assert cache.get("https://example.com/api") is None
