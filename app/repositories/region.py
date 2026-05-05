"""Repository layer: data access for regions."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.region import Region


async def get_all_active_regions(db: AsyncSession) -> list[Region]:
    result = await db.execute(
        select(Region).where(Region.is_active == True).order_by(Region.name)  # noqa: E712
    )
    return list(result.scalars().all())


async def get_region_by_eve_id(db: AsyncSession, eve_region_id: int) -> Region | None:
    result = await db.execute(
        select(Region).where(Region.eve_region_id == eve_region_id)
    )
    return result.scalar_one_or_none()


async def seed_default_regions(db: AsyncSession) -> list[Region]:
    """Create the five major trade hub regions if they don't exist."""
    defaults = [
        (10000002, "The Forge (熔炉)", 60003760, 30000142),
        (10000043, "Domain (多美)", 60008494, 30002187),
        (10000032, "Sinq Laison (辛迪加)", 60011866, 30002659),
        (10000030, "Heimatar (海玛特)", 60004588, 30002510),
        (10000042, "Metropolis (大都会)", 60005686, 30002053),
    ]

    regions = []
    for eve_id, name, station_id, system_id in defaults:
        existing = await get_region_by_eve_id(db, eve_id)
        if existing is None:
            region = Region(
                eve_region_id=eve_id,
                name=name,
                station_id=station_id,
                solar_system_id=system_id,
            )
            db.add(region)
            regions.append(region)
        else:
            regions.append(existing)

    await db.commit()
    return regions
