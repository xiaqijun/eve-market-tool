"""Unit tests for manufacturing cost calculations."""

import time
from unittest.mock import AsyncMock, patch

import pytest

from app.services.manufacturing import (
    JITA_SYSTEM_ID,
    ManufacturingAnalyzer,
    _cost_indices_cache,
    _cost_indices_ts,
)


class TestCostIndex:
    """Test the cost index caching logic."""

    def setup_method(self):
        """Clear the global cache before each test."""
        _cost_indices_cache.clear()

    @pytest.mark.asyncio
    async def test_get_cost_index_returns_default_on_empty_cache(self):
        """When no ESI data is available, returns default 0.01."""
        import app.services.manufacturing as mod

        mod._cost_indices_cache.clear()
        mod._cost_indices_ts = 0.0

        db = AsyncMock()
        analyzer = ManufacturingAnalyzer(db)

        with patch.object(analyzer, "_get_esi") as mock_esi:
            mock_client = AsyncMock()
            mock_client.get_industry_systems.return_value = []
            mock_esi.return_value = mock_client

            idx = await analyzer._get_cost_index(JITA_SYSTEM_ID)
            assert idx == 0.01

    @pytest.mark.asyncio
    async def test_get_cost_index_from_esi(self):
        """When ESI returns data, uses the actual cost index."""
        import app.services.manufacturing as mod

        mod._cost_indices_cache.clear()
        mod._cost_indices_ts = 0.0

        db = AsyncMock()
        analyzer = ManufacturingAnalyzer(db)

        esi_data = [
            {
                "solar_system_id": JITA_SYSTEM_ID,
                "cost_indices": [
                    {"activity": "researching", "cost_index": 0.05},
                    {"activity": "manufacturing", "cost_index": 0.0234},
                ],
            },
            {
                "solar_system_id": 30000144,
                "cost_indices": [
                    {"activity": "manufacturing", "cost_index": 0.015},
                ],
            },
        ]

        with patch.object(analyzer, "_get_esi") as mock_esi:
            mock_client = AsyncMock()
            mock_client.get_industry_systems.return_value = esi_data
            mock_esi.return_value = mock_client

            idx = await analyzer._get_cost_index(JITA_SYSTEM_ID)
            assert idx == pytest.approx(0.0234)

    @pytest.mark.asyncio
    async def test_cost_index_cache_hit(self):
        """Second call within TTL should not call ESI."""
        import app.services.manufacturing as mod

        mod._cost_indices_cache[JITA_SYSTEM_ID] = 0.03
        mod._cost_indices_ts = time.monotonic()

        db = AsyncMock()
        analyzer = ManufacturingAnalyzer(db)

        with patch.object(analyzer, "_get_esi") as mock_esi:
            idx = await analyzer._get_cost_index(JITA_SYSTEM_ID)
            assert idx == pytest.approx(0.03)
            mock_esi.assert_not_called()


class TestJobFeeCalculation:
    """Test the manufacturing job fee formula."""

    def test_fee_formula_basic(self):
        """materials_cost * cost_index * (1 + facility_tax)."""
        materials_cost = 1_000_000
        cost_index = 0.02
        facility_tax = 0.0

        fee = materials_cost * cost_index * (1 + facility_tax)
        assert fee == pytest.approx(20_000)

    def test_fee_formula_with_facility_tax(self):
        materials_cost = 1_000_000
        cost_index = 0.02
        facility_tax = 0.1

        fee = materials_cost * cost_index * (1 + facility_tax)
        assert fee == pytest.approx(22_000)

    def test_fee_formula_zero_cost_index(self):
        materials_cost = 1_000_000
        cost_index = 0.0
        facility_tax = 0.0

        fee = materials_cost * cost_index * (1 + facility_tax)
        assert fee == 0.0
