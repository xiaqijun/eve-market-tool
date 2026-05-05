"""Price alert evaluation service.

Checks active alerts against current market prices and marks
triggered alerts.
"""

from __future__ import annotations

import datetime
import logging

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import PriceAlert

logger = logging.getLogger(__name__)


class PriceAlerter:
    """Evaluates price alerts against current orders."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def evaluate_all(self) -> list[dict]:
        """Evaluate all active price alerts. Returns triggered alerts."""
        result = await self.db.execute(
            select(PriceAlert).where(PriceAlert.is_active == True)  # noqa: E712
        )
        alerts = result.scalars().all()

        triggered = []
        now = datetime.datetime.now(datetime.timezone.utc)

        for alert in alerts:
            current_price = await self._get_lowest_sell_price(
                alert.type_id, alert.region_id
            )
            if current_price is None:
                continue

            if (
                alert.condition == "above"
                and current_price >= alert.threshold
            ) or (
                alert.condition == "below"
                and current_price <= alert.threshold
            ):
                alert.last_triggered = now
                triggered.append(
                    {
                        "alert_id": alert.id,
                        "type_id": alert.type_id,
                        "condition": alert.condition,
                        "threshold": alert.threshold,
                        "current_price": current_price,
                        "triggered_at": now.isoformat(),
                    }
                )

        if triggered:
            await self.db.commit()
            logger.info("Triggered %d price alerts", len(triggered))

        return triggered

    async def _get_lowest_sell_price(
        self, type_id: int, region_id: int
    ) -> float | None:
        sql = text("""
        WITH latest_fetch AS (
            SELECT MAX(fetched_at) AS ts FROM market_order_snapshot
        )
        SELECT mos.price
        FROM market_order_snapshot mos
        JOIN latest_fetch lf ON mos.fetched_at = lf.ts
        WHERE mos.type_id = :type_id
          AND mos.region_id = :region_id
          AND mos.is_buy_order = FALSE
          AND mos.volume_remain >= 1
        ORDER BY mos.price ASC
        LIMIT 1
        """)
        result = await self.db.execute(
            sql, {"type_id": type_id, "region_id": region_id}
        )
        row = result.fetchone()
        return float(row.price) if row else None
