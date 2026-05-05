from fastapi import APIRouter
from app.dependencies import ApprovedPartner, DB, Redis
from app.services import location_service
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/partner/location", tags=["Partner Location"])

class LocationUpdate(BaseModel):
    latitude: float
    longitude: float
    speed_kmph: float | None = None
    heading_degrees: int | None = None
    accuracy_meters: float | None = None

@router.post("/update")
async def update_location(
    data: LocationUpdate,
    partner: ApprovedPartner,
    db: DB,
    redis: Redis
):
    result = await location_service.update_location(
        partner.id,
        data.latitude,
        data.longitude,
        data.speed_kmph,
        data.heading_degrees,
        data.accuracy_meters,
        db,
        redis
    )
    await db.commit()
    return result
