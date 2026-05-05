"""SDE (Static Data Export) loader for item names and blueprints.

Two strategies:
1. Bulk import from Fuzzwork SDE SQLite (~30s for 20k+ items)
2. Lazy ESI resolution (fallback, per-item, slow)
"""

from __future__ import annotations

import logging
import sqlite3
import urllib.request
from pathlib import Path

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.esi import EsiClient
from app.models.item import Item
from app.models.manufacturing import Blueprint, BlueprintMaterial

logger = logging.getLogger(__name__)

# Fuzzwork SDE download URL
SDE_URL = "https://www.fuzzwork.co.uk/dump/sqlite-latest.sqlite.bz2"
SDE_LOCAL_PATH = Path("sde.sqlite")


class SdeLoader:
    """Resolves item type_ids to names, volumes, etc."""

    def __init__(self, esi: EsiClient, db: AsyncSession) -> None:
        self.esi = esi
        self.db = db

    # ------------------------------------------------------------------
    # Bulk import from SDE SQLite
    # ------------------------------------------------------------------

    async def bulk_import_from_sde(self, download: bool = False) -> int:
        """Import ALL items from the Fuzzwork SDE SQLite with Chinese names.

        If `download=True`, downloads the latest SDE first (~200MB).
        Otherwise expects the file at `sde.sqlite`.

        Returns total items imported.
        """
        if download:
            _download_sde()

        if not SDE_LOCAL_PATH.exists():
            logger.warning("SDE file not found at %s. Run with download=True.", SDE_LOCAL_PATH)
            return 0

        logger.info("Opening SDE SQLite at %s ...", SDE_LOCAL_PATH)
        sde = sqlite3.connect(str(SDE_LOCAL_PATH))
        sde.row_factory = sqlite3.Row

        # Try Chinese names first via trnTranslations
        # The key columns vary by SDE version; try multiple approaches
        items = _extract_items_with_chinese_names(sde)

        if not items:
            # Fall back to English names only
            logger.warning("No Chinese translations found, using English names")
            items = _extract_items_english(sde)

        sde.close()

        if not items:
            logger.warning("No items found in SDE")
            return 0

        # Upsert into our item table
        count = await self._bulk_upsert_items(items)
        logger.info("Imported %d items from SDE", count)
        return count

    # ------------------------------------------------------------------
    # ESI-based resolution (fallback)
    # ------------------------------------------------------------------

    async def bulk_import_blueprints(self) -> int:
        """Import all manufacturing blueprints and materials from SDE.

        Uses Fuzzwork SDE table industryActivity, industryActivityMaterials,
        and industryActivityProducts.  Only imports manufacturing (activityID=1).

        Returns total blueprints imported.
        """
        if not SDE_LOCAL_PATH.exists():
            logger.warning("SDE file not found for blueprint import")
            return 0

        sde = sqlite3.connect(str(SDE_LOCAL_PATH))
        sde.row_factory = sqlite3.Row

        # Check table existence
        tables = {r[0] for r in sde.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        needed = {"industryActivity", "industryActivityMaterials", "industryActivityProducts"}
        missing = needed - tables
        if missing:
            logger.warning("SDE missing blueprint tables: %s", missing)
            sde.close()
            return 0

        # Get manufacturing blueprints (activityID=1 = manufacturing)
        bps = sde.execute("""
            SELECT ia.typeID AS blueprint_type_id, iap.productTypeID AS product_type_id,
                   ia.time AS manufacturing_time
            FROM industryActivity ia
            JOIN industryActivityProducts iap
                ON ia.typeID = iap.typeID AND ia.activityID = iap.activityID
            WHERE ia.activityID = 1
        """).fetchall()
        logger.info("Found %d manufacturing blueprints in SDE", len(bps))

        # Clear existing
        from sqlalchemy import delete
        await self.db.execute(delete(BlueprintMaterial))
        await self.db.execute(delete(Blueprint))
        await self.db.commit()

        # Insert blueprints in batches
        imported = 0
        for batch in _chunk(bps, 500):
            bp_rows = [
                dict(
                    blueprint_type_id=r["blueprint_type_id"],
                    product_type_id=r["product_type_id"],
                    manufacturing_time=r["manufacturing_time"],
                    activity_type="manufacturing",
                )
                for r in batch
            ]
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            stmt = pg_insert(Blueprint).values(bp_rows)
            stmt = stmt.on_conflict_do_nothing(constraint="blueprint_blueprint_type_id_key")
            await self.db.execute(stmt)
            imported += len(bp_rows)
        await self.db.commit()
        logger.info("Inserted %d blueprints", imported)

        # Insert materials for all manufacturing blueprints
        mats = sde.execute("""
            SELECT iam.typeID AS blueprint_type_id, iam.materialTypeID AS material_type_id,
                   iam.quantity
            FROM industryActivityMaterials iam
            WHERE iam.activityID = 1
        """).fetchall()
        logger.info("Found %d material entries in SDE", len(mats))

        # Get blueprint internal IDs for FK mapping
        result = await self.db.execute(
            select(Blueprint.id, Blueprint.blueprint_type_id)
        )
        bp_id_map = {r.blueprint_type_id: r.id for r in result.fetchall()}

        mat_count = 0
        for batch in _chunk(mats, 1000):
            mat_rows = [
                dict(
                    blueprint_id=bp_id_map[r["blueprint_type_id"]],
                    material_type_id=r["material_type_id"],
                    quantity=r["quantity"],
                )
                for r in batch
                if r["blueprint_type_id"] in bp_id_map
            ]
            if mat_rows:
                from sqlalchemy.dialects.postgresql import insert as pg_insert
                stmt = pg_insert(BlueprintMaterial).values(mat_rows)
                await self.db.execute(stmt)
                mat_count += len(mat_rows)
        await self.db.commit()
        logger.info("Inserted %d blueprint materials", mat_count)

        sde.close()
        return imported

    async def resolve_items(self, type_ids: set[int]) -> dict[int, str]:
        """Ensure all *type_ids* have entries in the Item table.

        Checks the database first; unknown IDs fetch from ESI concurrently.
        Returns {type_id: name}.
        """
        existing = await self._get_existing_type_ids(type_ids)
        missing = type_ids - existing

        if missing:
            logger.info("Resolving %d unknown type_ids via ESI...", len(missing))
            import asyncio

            # Fetch concurrently in batches of 20
            sem = asyncio.Semaphore(20)
            resolved: dict[int, str] = {}

            async def fetch_one(tid: int):
                async with sem:
                    try:
                        info = await self.esi.get_type_info(tid)
                        name = info.get("name", f"#{tid}")
                        resolved[tid] = name
                        return dict(
                            type_id=tid, name=name,
                            description=info.get("description"),
                            group_id=info.get("group_id"),
                            category_id=info.get("category_id"),
                            volume=info.get("volume"),
                            is_published=info.get("published", True),
                            icon_id=info.get("icon_id"),
                        )
                    except Exception:
                        logger.exception("Failed to resolve type_id=%d", tid)
                        resolved[tid] = f"#{tid}"
                        return None

            tasks = [fetch_one(tid) for tid in missing]
            results = await asyncio.gather(*tasks)

            rows = [r for r in results if r is not None]
            if rows:
                await self._bulk_insert(rows)

            await self.db.commit()

            existing_names = await self._get_existing_names(existing)
            existing_names.update(resolved)
            return existing_names

        return await self._get_existing_names(existing)

    async def resolve_one(self, type_id: int) -> str:
        result = await self.resolve_items({type_id})
        return result.get(type_id, f"#{type_id}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_existing_type_ids(self, type_ids: set[int]) -> set[int]:
        if not type_ids:
            return set()
        result = await self.db.execute(
            select(Item.type_id).where(Item.type_id.in_(type_ids))
        )
        return {row[0] for row in result.fetchall()}

    async def _get_existing_names(self, type_ids: set[int]) -> dict[int, str]:
        if not type_ids:
            return {}
        result = await self.db.execute(
            select(Item.type_id, Item.name).where(Item.type_id.in_(type_ids))
        )
        return {row.type_id: row.name for row in result.fetchall()}

    async def _bulk_upsert_items(self, items: list[dict]) -> int:
        """Upsert items into the database using INSERT ON CONFLICT."""
        from sqlalchemy.dialects.postgresql import insert

        for batch in _chunk(items, 500):
            stmt = insert(Item).values(batch)
            stmt = stmt.on_conflict_do_update(
                constraint="item_type_id_key",
                set_=dict(
                    name=stmt.excluded.name,
                    description=stmt.excluded.description,
                    group_id=stmt.excluded.group_id,
                    category_id=stmt.excluded.category_id,
                    volume=stmt.excluded.volume,
                    icon_id=stmt.excluded.icon_id,
                ),
            )
            await self.db.execute(stmt)

        await self.db.commit()
        return len(items)

    async def _bulk_insert(self, rows: list[dict]) -> None:
        from sqlalchemy.dialects.postgresql import insert

        stmt = insert(Item).values(rows)
        stmt = stmt.on_conflict_do_nothing(constraint="item_type_id_key")
        await self.db.execute(stmt)


# ------------------------------------------------------------------
# SDE extraction functions
# ------------------------------------------------------------------


def _extract_items_with_chinese_names(sde: sqlite3.Connection) -> list[dict]:
    """Try to extract Chinese item names from SDE.

    The Fuzzwork SDE has invTypes + trnTranslations tables.
    We try multiple possible column names for the join.
    """
    # First, discover the schema
    tables = {r[0] for r in sde.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

    if "invTypes" not in tables:
        return []

    inv_cols = {r[1] for r in sde.execute("PRAGMA table_info(invTypes)").fetchall()}

    # Try to find Chinese translations
    if "trnTranslations" in tables:
        trn_cols = {r[1] for r in sde.execute("PRAGMA table_info(trnTranslations)").fetchall()}

        # Find the join column (typeNameID, descriptionID, or keyID)
        for join_col in ("typeNameID", "descriptionID", "keyID", "tcID"):
            if join_col in inv_cols:
                try:
                    rows = sde.execute(f"""
                        SELECT i.typeID, COALESCE(zh.text, i.typeName) AS name,
                               i.groupID, i.categoryID, i.volume, i.basePrice
                        FROM invTypes i
                        LEFT JOIN trnTranslations zh
                            ON zh.keyID = i.{join_col} AND zh.languageID = 'zh'
                        WHERE i.published = 1
                    """).fetchall()
                    if rows:
                        return [_row_to_dict(r) for r in rows]
                except Exception:
                    continue

    # Fall back to just invTypes (English names)
    return _extract_items_english(sde)


def _extract_items_english(sde: sqlite3.Connection) -> list[dict]:
    """Extract English item names from invTypes only."""
    try:
        rows = sde.execute("""
            SELECT typeID, typeName AS name,
                   groupID, categoryID, volume, basePrice
            FROM invTypes
            WHERE published = 1
        """).fetchall()
        return [_row_to_dict(r) for r in rows]
    except Exception:
        return []


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(
        type_id=row["typeID"],
        name=row["name"],
        group_id=row["groupID"] if "groupID" in row.keys() else None,
        category_id=row["categoryID"] if "categoryID" in row.keys() else None,
        volume=row["volume"] if "volume" in row.keys() else None,
        base_price=row["basePrice"] if "basePrice" in row.keys() else None,
        is_published=True,
    )


# ------------------------------------------------------------------
# Download helper
# ------------------------------------------------------------------


def _download_sde() -> None:
    """Download the Fuzzwork SDE SQLite (compressed, ~80MB download, ~300MB extracted)."""
    import bz2

    url = SDE_URL
    dest = SDE_LOCAL_PATH

    if dest.exists():
        logger.info("SDE already exists at %s", dest)
        return

    logger.info("Downloading SDE from %s ...", url)
    compressed = Path(str(dest) + ".bz2")

    urllib.request.urlretrieve(url, compressed)
    logger.info("Extracting SDE (this may take a minute)...")

    # Stream decompress to avoid OOM (SDE is ~1.2GB uncompressed)
    with bz2.open(compressed, "rb") as src, open(dest, "wb") as dst:
        while True:
            chunk = src.read(8 * 1024 * 1024)  # 8MB chunks
            if not chunk:
                break
            dst.write(chunk)

    # Only delete compressed file if extraction succeeded
    if dest.stat().st_size > 0:
        compressed.unlink()
        logger.info("SDE compressed file removed (extraction OK)")
    else:
        logger.warning("SDE extraction produced empty file, keeping .bz2")
    logger.info("SDE ready at %s", dest)


def _chunk(lst: list, n: int):
    for i in range(0, len(lst), n):
        yield lst[i: i + n]
