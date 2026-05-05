"""One-time backfill: resolve Chinese item names for all type_ids in the database."""
import asyncio
from app.core.database import AsyncSessionLocal
from app.core.esi import EsiClient
from app.services.market_fetcher import MarketDataFetcher


async def main():
    esi = EsiClient()
    try:
        async with AsyncSessionLocal() as db:
            fetcher = MarketDataFetcher(esi, db)
            count = await fetcher.resolve_unknown_items(limit=500)
            print(f"Resolved {count} new items")
    finally:
        await esi.close()


if __name__ == "__main__":
    asyncio.run(main())
