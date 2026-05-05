"""
FastAPI application factory with lifespan, middleware, routers, and OpenAPI config.
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app.config import get_settings
from app.exceptions import register_exception_handlers
from app.middleware import register_middleware
from app.redis_client import close_redis, init_redis
from app.routers import auth, users, addresses, restaurants, menu, cart, orders, reviews, coupons
from app.routers.delivery import kyc, profile as delivery_profile, admin_kyc, duty, assignments, location, earnings, payouts, support, incentives
from app.routers.restaurant import profile as restaurant_profile, documents as restaurant_documents, admin_restaurant
from app.routers.restaurant import menu as restaurant_menu, orders as restaurant_orders
from app.routers.restaurant import analytics as restaurant_analytics, payouts as restaurant_payouts
from app.routers.restaurant import offers as restaurant_offers, reviews as restaurant_reviews
from fastapi.staticfiles import StaticFiles

settings = get_settings()

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀  %s v%s starting…", settings.APP_NAME, settings.APP_VERSION)
    await init_redis()
    
    import asyncio
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.database import AsyncSessionLocal
    from app.models.delivery_partner import DeliveryPartner
    from app.models.partner_location import PartnerLocation
    from app.models.partner_shift import PartnerShift
    from datetime import UTC, datetime, timedelta
    from sqlalchemy import select, delete

    async def cleanup_task():
        while True:
            try:
                await asyncio.sleep(300) # every 5 mins
                async with AsyncSessionLocal() as db:
                    now_utc = datetime.now(UTC)
                    await db.execute(delete(PartnerLocation).where(PartnerLocation.recorded_at < now_utc - timedelta(hours=24)))
                    
                    stale_time = now_utc - timedelta(minutes=10)
                    stale_partners = await db.scalars(
                        select(DeliveryPartner).where(
                            DeliveryPartner.is_online == True,
                            DeliveryPartner.last_location_at < stale_time
                        )
                    )
                    for p in stale_partners:
                        p.is_online = False
                        logger.info(f"Partner {p.fe_id} auto-offlined — stale GPS")
                        shift = await db.scalar(
                            select(PartnerShift).where(
                                PartnerShift.partner_id == p.id,
                                PartnerShift.ended_at.is_(None)
                            )
                        )
                        if shift:
                            shift.ended_at = now_utc
                            
                    await db.commit()
            except Exception as e:
                logger.error(f"Cleanup task error: {e}")

    task = asyncio.create_task(cleanup_task())
    yield
    task.cancel()
    await close_redis()
    logger.info("🛑  %s shut down", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-grade Zomato customer API: OTP auth, restaurant discovery, cart, orders, reviews.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    redirect_slashes=False,
)

register_middleware(app)
register_exception_handlers(app)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(addresses.router)
app.include_router(restaurants.router)
app.include_router(menu.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(reviews.router)
app.include_router(coupons.router)
app.include_router(kyc.router)
app.include_router(delivery_profile.router)
app.include_router(admin_kyc.router)
app.include_router(duty.router)
app.include_router(assignments.router)
app.include_router(location.router)
app.include_router(earnings.router)
app.include_router(payouts.router)
app.include_router(support.router)
app.include_router(incentives.router)

app.include_router(restaurant_profile.router)
app.include_router(restaurant_documents.router)
app.include_router(admin_restaurant.router)
app.include_router(restaurant_menu.router)
app.include_router(restaurant_orders.router)
app.include_router(restaurant_analytics.router)
app.include_router(restaurant_payouts.router)
app.include_router(restaurant_offers.router)
app.include_router(restaurant_reviews.router)

import os
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

from fastapi import WebSocket, WebSocketDisconnect, Query
from app.utils.jwt import verify_access_token
from datetime import UTC, datetime

class ConnectionManager:
    def __init__(self):
        self.partner_order_connections = {}
        self.partner_location_connections = {}
        self.restaurant_connections = {}   # restaurant_id (str) → WebSocket
        self.user_connections = {}         # user_id (str) → WebSocket

    async def send_to_partner(self, partner_id, message):
        ws = self.partner_order_connections.get(str(partner_id))
        if ws:
            try:
                await ws.send_json(message)
            except Exception:
                self.partner_order_connections.pop(str(partner_id), None)

    async def send_to_user(self, user_id, message):
        ws = self.user_connections.get(str(user_id))
        if ws:
            try:
                await ws.send_json(message)
            except Exception:
                self.user_connections.pop(str(user_id), None)

    async def send_to_restaurant(self, restaurant_id, message):
        ws = self.restaurant_connections.get(str(restaurant_id))
        if ws:
            try:
                await ws.send_json(message)
            except Exception:
                self.restaurant_connections.pop(str(restaurant_id), None)

manager = ConnectionManager()
app.state.connection_manager = manager

@app.websocket("/api/v1/ws/partner/location")
async def partner_location_ws(websocket: WebSocket, token: str = Query(...)):
    from app.services import location_service
    from app.database import AsyncSessionLocal
    import redis.asyncio as aioredis
    from app.redis_client import get_redis
    
    try:
        payload = verify_access_token(token)
        if payload.get("role") != "DELIVERY_PARTNER":
            await websocket.close(code=4001)
            return
    except:
        await websocket.close(code=4001)
        return
        
    partner_id = payload.get("partner_id")
    
    async with AsyncSessionLocal() as db:
        from app.models.delivery_partner import DeliveryPartner
        from sqlalchemy import select
        partner = await db.scalar(select(DeliveryPartner).where(DeliveryPartner.id == partner_id))
        if not partner or not partner.is_online:
            await websocket.close(code=4001)
            return
            
    await websocket.accept()
    manager.partner_location_connections[partner_id] = websocket
    await websocket.send_json({"event": "CONNECTED", "message": "Location tracking active"})
    
    redis = await get_redis()
    
    try:
        while True:
            data = await websocket.receive_json()
            async with AsyncSessionLocal() as db:
                await location_service.update_location(
                    partner_id,
                    data.get('latitude', 0),
                    data.get('longitude', 0),
                    data.get('speed_kmph'),
                    data.get('heading_degrees'),
                    data.get('accuracy_meters'),
                    db,
                    redis
                )
                await db.commit()
            await websocket.send_json({
                "event": "LOCATION_RECEIVED",
                "timestamp": datetime.now(UTC).isoformat()
            })
    except WebSocketDisconnect:
        manager.partner_location_connections.pop(partner_id, None)


@app.websocket("/api/v1/ws/partner/orders")
async def partner_orders_ws(websocket: WebSocket, token: str = Query(...)):
    from app.redis_client import get_redis
    import asyncio
    
    try:
        payload = verify_access_token(token)
        if payload.get("role") != "DELIVERY_PARTNER":
            await websocket.close(code=4001)
            return
    except:
        await websocket.close(code=4001)
        return
        
    partner_id = payload.get("partner_id")
    await websocket.accept()
    manager.partner_order_connections[partner_id] = websocket
    
    redis = await get_redis()
    val = await redis.get(f"assignment_pending:{partner_id}")
    if val:
        await websocket.send_json({"event": "NEW_ORDER"})
        
    try:
        while True:
            await asyncio.sleep(30)
            await websocket.send_json({"event": "PING"})
    except WebSocketDisconnect:
        manager.partner_order_connections.pop(partner_id, None)


@app.websocket("/api/v1/ws/restaurant/orders")
async def restaurant_orders_ws(websocket: WebSocket, token: str = Query(...)):
    """Restaurant real-time order feed."""
    import json as _json
    from app.redis_client import get_redis
    from app.database import AsyncSessionLocal
    from app.models.restaurant_partner import RestaurantPartner
    from sqlalchemy import select

    try:
        payload = verify_access_token(token)
        if payload.get("role") != "RESTAURANT_PARTNER":
            await websocket.close(code=4001)
            return
    except Exception:
        await websocket.close(code=4001)
        return

    restaurant_id = payload.get("restaurant_id")
    partner_id = payload.get("restaurant_partner_id")

    async with AsyncSessionLocal() as db:
        partner = await db.scalar(
            select(RestaurantPartner).where(RestaurantPartner.id == partner_id)
        )
        from app.models.user import User
        import uuid
        user = await db.scalar(
            select(User).where(User.id == uuid.UUID(payload.get("sub")))
        )
        if not partner or not user or user.restaurant_status != "DOCS_APPROVED":
            await websocket.close(code=4003)
            return

    await websocket.accept()
    manager.restaurant_connections[str(restaurant_id)] = websocket

    redis = get_redis()

    # Drain buffered pending orders
    key = f"restaurant:pending:{restaurant_id}"
    while True:
        order_json = await redis.lpop(key)
        if not order_json:
            break
        try:
            await websocket.send_json(_json.loads(order_json))
        except Exception:
            break

    # Send current PLACED orders immediately
    async with AsyncSessionLocal() as db:
        from app.services.order_management_service import OrderManagementService
        svc = OrderManagementService(db)
        live = await svc.get_live_orders(uuid.UUID(restaurant_id))
        if live.get("placed"):
            await websocket.send_json({"event": "PENDING_ORDERS", "orders": live["placed"]})

    # Keep-alive ping loop
    try:
        while True:
            await asyncio.sleep(30)
            await websocket.send_json({"event": "PING"})
    except WebSocketDisconnect:
        manager.restaurant_connections.pop(str(restaurant_id), None)
# ── Health ────────────────────────────────────────────────────────────────────
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from fastapi import Depends
from app.database import get_db
from app.redis_client import get_redis
import redis.asyncio as aioredis

@app.get("/api/v1/health", tags=["Health"], include_in_schema=True)
async def health(
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> dict:
    from datetime import UTC, datetime
    db_status = "ok"
    redis_status = "ok"

    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error("DB health check failed: %s", e)
        db_status = "error"

    try:
        await redis.ping()
    except Exception as e:
        logger.error("Redis health check failed: %s", e)
        redis_status = "error"

    overall = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"
    return {
        "success": True,
        "data": {
            "status": overall,
            "db": db_status,
            "redis": redis_status,
            "version": settings.APP_VERSION,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    }


# ── Frontend test UI ──────────────────────────────────────────────────────────
_STATIC = Path(__file__).parent.parent / "static" / "index.html"


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def frontend() -> HTMLResponse:
    return HTMLResponse(content=_STATIC.read_text(encoding="utf-8"))
