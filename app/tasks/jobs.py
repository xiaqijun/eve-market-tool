"""Individual scheduled job functions.

Each job runs inside its own DB session and ESI client instance.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.esi import EsiClient
from app.services.market_fetcher import MarketDataFetcher

logger = logging.getLogger(__name__)


async def fetch_all_market_orders() -> None:
    """Fetch current market orders for all active hub regions."""
    from app.core.database import AsyncSessionLocal
    from app.repositories.region import get_all_active_regions

    esi = EsiClient()
    try:
        async with AsyncSessionLocal() as db:
            regions = await get_all_active_regions(db)
            region_ids = [r.eve_region_id for r in regions]

            if not region_ids:
                region_ids = settings.hub_region_ids

            fetcher = MarketDataFetcher(esi, db)
            results = await fetcher.fetch_orders_all_regions(region_ids)

            total = sum(results.values())
            logger.info("fetch_all_market_orders: %d orders across %d regions", total, len(results))

            # Resolve unknown item names (Chinese)
            resolved = await fetcher.resolve_unknown_items(limit=300)
            logger.info("fetch_all_market_orders: resolved %d new items", resolved)

    except Exception:
        logger.exception("fetch_all_market_orders failed")
    finally:
        await esi.close()


async def resolve_item_names() -> None:
    """Resolve Chinese item names for unknown type_ids."""
    from app.core.database import AsyncSessionLocal

    esi = EsiClient()
    try:
        async with AsyncSessionLocal() as db:
            fetcher = MarketDataFetcher(esi, db)
            count = await fetcher.resolve_unknown_items(limit=500)
            logger.info("resolve_item_names: resolved %d items", count)
    except Exception:
        logger.exception("resolve_item_names failed")
    finally:
        await esi.close()


async def fetch_universe_prices() -> None:
    """Fetch universe-wide average prices."""
    from app.core.database import AsyncSessionLocal

    esi = EsiClient()
    try:
        async with AsyncSessionLocal() as db:
            fetcher = MarketDataFetcher(esi, db)
            count = await fetcher.fetch_prices_all()
            logger.info("fetch_universe_prices: %d entries", count)

    except Exception:
        logger.exception("fetch_universe_prices failed")
    finally:
        await esi.close()


async def prune_market_order_snapshots() -> None:
    """Delete old market order snapshots according to retention policy:
    - Keep all snapshots for 48 hours
    - After 48 hours, keep one per hour for 30 days
    - After 30 days, keep one per day for 1 year
    """
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import text

    try:
        async with AsyncSessionLocal() as db:
            # Delete snapshots older than 48 hours that aren't "keep" candidates
            result = await db.execute(text("""
                DELETE FROM market_order_snapshot
                WHERE fetched_at < NOW() - INTERVAL '48 hours'
                  AND id NOT IN (
                      SELECT DISTINCT ON (
                          type_id, region_id,
                          date_trunc('hour', fetched_at)
                      ) id
                      FROM market_order_snapshot
                      WHERE fetched_at < NOW() - INTERVAL '48 hours'
                        AND fetched_at >= NOW() - INTERVAL '30 days'
                      ORDER BY type_id, region_id,
                               date_trunc('hour', fetched_at),
                               fetched_at DESC
                  )
                  AND id NOT IN (
                      SELECT DISTINCT ON (
                          type_id, region_id,
                          date_trunc('day', fetched_at)
                      ) id
                      FROM market_order_snapshot
                      WHERE fetched_at < NOW() - INTERVAL '30 days'
                      ORDER BY type_id, region_id,
                               date_trunc('day', fetched_at),
                               fetched_at DESC
                  )
            """))
            deleted = result.rowcount
            await db.commit()
            if deleted:
                logger.info("prune_market_order_snapshots: deleted %d rows", deleted)
    except Exception:
        logger.exception("prune_market_order_snapshots failed")


async def compute_arbitrage_opportunities() -> None:
    """Run arbitrage scan using latest snapshots."""
    from app.core.database import AsyncSessionLocal
    from app.services.arbitrage_engine import ArbitrageEngine

    try:
        async with AsyncSessionLocal() as db:
            engine = ArbitrageEngine(db)
            results = await engine.scan(min_profit_margin=0.05, top_n=100)
            logger.info("compute_arbitrage: found %d opportunities", len(results))
    except Exception:
        logger.exception("compute_arbitrage failed")


async def compute_hot_items() -> None:
    """Detect items with unusual volume movements."""
    from app.core.database import AsyncSessionLocal
    from app.services.dashboard import DashboardService

    try:
        async with AsyncSessionLocal() as db:
            service = DashboardService(db)
            items = await service.get_hot_items(limit=30)
            logger.info("compute_hot_items: found %d hot items", len(items))
    except Exception:
        logger.exception("compute_hot_items failed")


async def evaluate_price_alerts() -> None:
    """Evaluate all active price alerts."""
    from app.core.database import AsyncSessionLocal
    from app.services.price_alerter import PriceAlerter

    try:
        async with AsyncSessionLocal() as db:
            alerter = PriceAlerter(db)
            triggered = await alerter.evaluate_all()
            if triggered:
                logger.info("evaluate_price_alerts: triggered %d alerts", len(triggered))
    except Exception:
        logger.exception("evaluate_price_alerts failed")
