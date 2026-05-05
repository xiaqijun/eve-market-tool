"""Seed the 5 major trade hub regions into the database."""
import asyncio
from app.core.database import AsyncSessionLocal
from app.repositories.region import seed_default_regions


async def main():
    async with AsyncSessionLocal() as db:
        regions = await seed_default_regions(db)
        for r in regions:
            print(f"Seeded: {r.name} (region_id={r.eve_region_id})")
        print(f"Total: {len(regions)} regions")


if __name__ == "__main__":
    asyncio.run(main())
