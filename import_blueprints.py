"""Download SDE and import all manufacturing blueprints + materials."""
import asyncio, bz2, os, urllib.request
from pathlib import Path
from app.core.database import AsyncSessionLocal
from app.core.esi import EsiClient
from app.services.sde_loader import SdeLoader

SDE_URL = "https://www.fuzzwork.co.uk/dump/sqlite-latest.sqlite.bz2"
SDE_FILE = Path("sde.sqlite")


def ensure_sde():
    """Download and extract SDE if not present."""
    if SDE_FILE.exists() and SDE_FILE.stat().st_size > 0:
        print(f"SDE found: {SDE_FILE.stat().st_size / 1e6:.0f}MB")
        return

    bz2_path = Path("sde.sqlite.bz2")
    if not bz2_path.exists():
        print(f"Downloading SDE from {SDE_URL}...")
        urllib.request.urlretrieve(SDE_URL, bz2_path)
        print(f"Downloaded: {bz2_path.stat().st_size / 1e6:.0f}MB")

    print("Extracting SDE...")
    with bz2.open(bz2_path, "rb") as src, open(SDE_FILE, "wb") as dst:
        while True:
            chunk = src.read(8 * 1024 * 1024)
            if not chunk:
                break
            dst.write(chunk)

    bz2_path.unlink()
    print(f"Extracted: {SDE_FILE.stat().st_size / 1e6:.0f}MB")


async def main():
    ensure_sde()

    esi = EsiClient()
    try:
        async with AsyncSessionLocal() as db:
            loader = SdeLoader(esi, db)
            count = await loader.bulk_import_blueprints()
            print(f"Imported {count} blueprints with materials")

            # Show sample
            from sqlalchemy import text
            result = await db.execute(text(
                "SELECT b.blueprint_type_id, b.product_type_id, COUNT(bm.id) as mats "
                "FROM blueprint b LEFT JOIN blueprint_material bm ON b.id = bm.blueprint_id "
                "GROUP BY b.id LIMIT 5"
            ))
            for r in result.fetchall():
                print(f"  BP {r.blueprint_type_id} -> product {r.product_type_id} ({r.mats} materials)")
    finally:
        await esi.close()


if __name__ == "__main__":
    asyncio.run(main())
