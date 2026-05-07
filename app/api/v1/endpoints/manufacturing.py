"""Manufacturing API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.manufacturing import (
    ManufacturingAnalysisRequest,
    ManufacturingAnalysisResponse,
    ManufacturingSummary,
)
from app.services.manufacturing import ManufacturingAnalyzer

router = APIRouter(prefix="/manufacturing", tags=["manufacturing"])


@router.get("/blueprints")
async def search_blueprints(
    q: str = Query(default="", description="Search by product name"),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Search blueprints by product name."""
    from sqlalchemy import text

    if not q:
        result = await db.execute(text(
            "SELECT b.blueprint_type_id, b.product_type_id, i.name AS product_name, "
            "COUNT(bm.id) AS material_count "
            "FROM blueprint b "
            "LEFT JOIN item i ON i.type_id = b.product_type_id "
            "LEFT JOIN blueprint_material bm ON bm.blueprint_id = b.id "
            "GROUP BY b.id, i.name "
            "ORDER BY b.blueprint_type_id LIMIT :limit"
        ), {"limit": limit})
    else:
        result = await db.execute(text(
            "SELECT b.blueprint_type_id, b.product_type_id, i.name AS product_name, "
            "COUNT(bm.id) AS material_count "
            "FROM blueprint b "
            "JOIN item i ON i.type_id = b.product_type_id "
            "LEFT JOIN blueprint_material bm ON bm.blueprint_id = b.id "
            "WHERE i.name ILIKE :q "
            "GROUP BY b.id, i.name "
            "ORDER BY i.name LIMIT :limit"
        ), {"q": f"%{q}%", "limit": limit})

    return [
        {
            "blueprint_type_id": r.blueprint_type_id,
            "product_type_id": r.product_type_id,
            "product_name": r.product_name or f"#{r.product_type_id}",
            "material_count": r.material_count,
        }
        for r in result.fetchall()
    ]


@router.post("/analyze", response_model=ManufacturingAnalysisResponse)
async def analyze_blueprint(
    request: ManufacturingAnalysisRequest,
    db: AsyncSession = Depends(get_db),
):
    """Run a manufacturing profitability analysis for a blueprint."""
    analyzer = ManufacturingAnalyzer(db)
    try:
        result = await analyzer.analyze_blueprint(
            blueprint_type_id=request.blueprint_type_id,
            region_id=request.region_id,
            quantity=request.quantity,
            facility_tax=request.facility_tax,
            system_id=request.system_id,
        )
        return ManufacturingAnalysisResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/analyses", response_model=list[ManufacturingSummary])
async def list_analyses(
    region_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List saved manufacturing analyses."""
    analyzer = ManufacturingAnalyzer(db)
    results = await analyzer.get_analyses(region_id=region_id, limit=limit)
    return [ManufacturingSummary(**r) for r in results]


@router.get("/top", response_model=list[ManufacturingSummary])
async def get_top_manufacturing(
    region_id: int = Query(default=10000002),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get most profitable manufacturing opportunities."""
    analyzer = ManufacturingAnalyzer(db)
    results = await analyzer.get_top_manufacturing(region_id=region_id, limit=limit)
    return [ManufacturingSummary(**r) for r in results]
