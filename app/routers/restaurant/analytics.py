from fastapi import APIRouter, Query

from app.dependencies import ApprovedRestaurant, DB
from app.services.restaurant_analytics_service import RestaurantAnalyticsService

router = APIRouter(prefix="/api/v1/restaurant/analytics", tags=["Restaurant Analytics"])


@router.get("/overview")
async def overview(partner: ApprovedRestaurant, db: DB):
    return await RestaurantAnalyticsService().get_overview(partner.restaurant_id, db)


@router.get("/revenue-chart")
async def revenue_chart(
    partner: ApprovedRestaurant,
    db: DB,
    period: str = Query("7days", pattern="^(7days|30days|3months|year)$"),
):
    return await RestaurantAnalyticsService().get_revenue_chart(partner.restaurant_id, period, db)


@router.get("/top-items")
async def top_items(
    partner: ApprovedRestaurant,
    db: DB,
    period: str = Query("7days", pattern="^(7days|30days|alltime)$"),
    limit: int = Query(10, ge=1, le=100),
):
    items = await RestaurantAnalyticsService().get_top_items(partner.restaurant_id, period, limit, db)
    return {"items": items}


@router.get("/peak-hours")
async def peak_hours(partner: ApprovedRestaurant, db: DB):
    return await RestaurantAnalyticsService().get_peak_hours(partner.restaurant_id, db)


@router.get("/ratings-summary")
async def ratings_summary(partner: ApprovedRestaurant, db: DB):
    return await RestaurantAnalyticsService().get_ratings_summary(partner.restaurant_id, db)
