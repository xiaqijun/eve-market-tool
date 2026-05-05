"""Bulk import all item names from Fuzzwork SDE SQLite with Chinese support."""
import asyncio
from app.core.database import AsyncSessionLocal
from app.core.esi import EsiClient
from app.services.sde_loader import SdeLoader


async def main():
    esi = EsiClient()
    try:
        async with AsyncSessionLocal() as db:
            loader = SdeLoader(esi, db)
            count = await loader.bulk_import_from_sde(download=True)
            print(f"Imported {count} items from SDE")
    finally:
        await esi.close()


if __name__ == "__main__":
    asyncio.run(main())
