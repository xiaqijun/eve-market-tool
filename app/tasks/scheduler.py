"""APScheduler integration for periodic market data fetching."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import settings

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def init_scheduler() -> None:
    """Register periodic jobs and start the scheduler."""
    from app.tasks.jobs import (
        compute_arbitrage_opportunities,
        compute_hot_items,
        evaluate_price_alerts,
        fetch_all_market_orders,
        fetch_universe_prices,
        prune_market_order_snapshots,
        resolve_item_names,
    )

    if not settings.scheduler_enabled:
        logger.info("Scheduler disabled via config")
        return

    interval = max(1, settings.market_fetch_interval_minutes)

    # Fetch orders every N minutes
    scheduler.add_job(
        fetch_all_market_orders,
        "interval",
        minutes=interval,
        id="fetch_orders",
        replace_existing=True,
    )

    # Fetch universe prices every N minutes
    scheduler.add_job(
        fetch_universe_prices,
        "interval",
        minutes=interval,
        id="fetch_prices",
        replace_existing=True,
    )

    # Compute arbitrage after orders are likely fetched (offset by 2 min)
    scheduler.add_job(
        compute_arbitrage_opportunities,
        "interval",
        minutes=interval,
        id="compute_arbitrage",
        replace_existing=True,
    )

    # Detect hot items
    scheduler.add_job(
        compute_hot_items,
        "interval",
        minutes=interval,
        id="compute_hot_items",
        replace_existing=True,
    )

    # Evaluate price alerts
    scheduler.add_job(
        evaluate_price_alerts,
        "interval",
        minutes=interval,
        id="evaluate_alerts",
        replace_existing=True,
    )

    # Resolve Chinese item names for unknown type_ids
    scheduler.add_job(
        resolve_item_names,
        "interval",
        minutes=interval,
        id="resolve_items",
        replace_existing=True,
    )

    # Prune old snapshots daily at 03:00
    scheduler.add_job(
        prune_market_order_snapshots,
        "cron",
        hour=3,
        minute=7,
        id="prune_snapshots",
        replace_existing=True,
    )

    logger.info("Scheduler initialized: %d jobs registered", len(scheduler.get_jobs()))


async def start_scheduler() -> None:
    if settings.scheduler_enabled:
        scheduler.start()
        logger.info("Scheduler started")


async def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down")
