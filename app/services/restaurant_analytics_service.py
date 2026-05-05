import uuid
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone

try:
    import pytz
    IST = pytz.timezone("Asia/Kolkata")
except ImportError:  # pragma: no cover - fallback for minimal test envs
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _as_float(value) -> float:
    return float(value or 0)


def _ist_midnight(day: date) -> datetime:
    naive = datetime.combine(day, time.min)
    if hasattr(IST, "localize"):
        return IST.localize(naive).astimezone(timezone.utc)
    return naive.replace(tzinfo=IST).astimezone(timezone.utc)


def _period_start(period: str) -> datetime:
    today = datetime.now(IST).date()
    today_start = _ist_midnight(today)
    if period == "7days":
        return today_start - timedelta(days=6)
    if period == "30days":
        return today_start - timedelta(days=29)
    if period == "3months":
        return today_start - timedelta(days=89)
    if period == "year":
        return today_start - timedelta(days=364)
    if period == "alltime":
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    raise HTTPException(status_code=422, detail="Invalid period")


class RestaurantAnalyticsService:
    async def _stats(
        self,
        restaurant_id: uuid.UUID,
        db: AsyncSession,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> dict:
        where = ["restaurant_id = :restaurant_id"]
        params = {"restaurant_id": restaurant_id}
        if start_at is not None:
            where.append("created_at >= :start_at")
            params["start_at"] = start_at
        if end_at is not None:
            where.append("created_at < :end_at")
            params["end_at"] = end_at

        result = await db.execute(
            text(
                f"""
                SELECT COUNT(*) AS order_count,
                       COALESCE(SUM(total_amount), 0) AS revenue,
                       COUNT(*) FILTER (WHERE status='CANCELLED') AS cancelled
                FROM orders
                WHERE {" AND ".join(where)}
                """
            ),
            params,
        )
        row = result.mappings().one()
        orders = int(row["order_count"] or 0)
        revenue = _as_float(row["revenue"])
        cancelled = int(row["cancelled"] or 0)
        return {
            "orders": orders,
            "revenue": revenue,
            "avg_order_value": round(revenue / orders, 2) if orders else 0.0,
            "cancelled": cancelled,
            "cancellation_rate": round((cancelled / orders) * 100, 2) if orders else 0.0,
        }

    async def get_overview(self, restaurant_id: uuid.UUID, db: AsyncSession) -> dict:
        today_ist = datetime.now(IST).date()
        today_start = _ist_midnight(today_ist)
        today_end = today_start + timedelta(days=1)
        week_start = today_start - timedelta(days=today_ist.weekday())
        month_start = _ist_midnight(today_ist.replace(day=1))
        last_month_date = today_ist.replace(day=1) - timedelta(days=1)
        last_month_start = _ist_midnight(last_month_date.replace(day=1))

        stats_row = (
            await db.execute(
                text(
                    """
                    SELECT
                        COUNT(*) FILTER (WHERE created_at >= :today_start AND created_at < :today_end) AS today_orders,
                        COALESCE(SUM(total_amount) FILTER (WHERE created_at >= :today_start AND created_at < :today_end), 0) AS today_revenue,
                        COUNT(*) FILTER (WHERE status='CANCELLED' AND created_at >= :today_start AND created_at < :today_end) AS today_cancelled,
                        COUNT(*) FILTER (WHERE created_at >= :week_start) AS week_orders,
                        COALESCE(SUM(total_amount) FILTER (WHERE created_at >= :week_start), 0) AS week_revenue,
                        COUNT(*) FILTER (WHERE status='CANCELLED' AND created_at >= :week_start) AS week_cancelled,
                        COUNT(*) FILTER (WHERE created_at >= :month_start) AS month_orders,
                        COALESCE(SUM(total_amount) FILTER (WHERE created_at >= :month_start), 0) AS month_revenue,
                        COUNT(*) FILTER (WHERE status='CANCELLED' AND created_at >= :month_start) AS month_cancelled,
                        COUNT(*) FILTER (WHERE created_at >= :last_month_start AND created_at < :month_start) AS last_month_orders,
                        COALESCE(SUM(total_amount) FILTER (WHERE created_at >= :last_month_start AND created_at < :month_start), 0) AS last_month_revenue,
                        COUNT(*) FILTER (WHERE status='CANCELLED' AND created_at >= :last_month_start AND created_at < :month_start) AS last_month_cancelled,
                        COUNT(*) AS all_orders,
                        COALESCE(SUM(total_amount), 0) AS all_revenue,
                        COUNT(*) FILTER (WHERE status='CANCELLED') AS all_cancelled
                    FROM orders
                    WHERE restaurant_id = :restaurant_id
                    """
                ),
                {
                    "restaurant_id": restaurant_id,
                    "today_start": today_start,
                    "today_end": today_end,
                    "week_start": week_start,
                    "month_start": month_start,
                    "last_month_start": last_month_start,
                },
            )
        ).mappings().one()

        def pack(prefix: str) -> dict:
            orders = int(stats_row[f"{prefix}_orders"] or 0)
            revenue = _as_float(stats_row[f"{prefix}_revenue"])
            cancelled = int(stats_row[f"{prefix}_cancelled"] or 0)
            return {
                "orders": orders,
                "revenue": revenue,
                "avg_order_value": round(revenue / orders, 2) if orders else 0.0,
                "cancelled": cancelled,
                "cancellation_rate": round((cancelled / orders) * 100, 2) if orders else 0.0,
            }

        today = pack("today")
        this_week = pack("week")
        this_month = pack("month")
        last_month = pack("last_month")
        all_time = pack("all")

        best_day_row = (
            await db.execute(
                text(
                    """
                    SELECT to_char(created_at AT TIME ZONE 'Asia/Kolkata', 'FMDay') AS day_name,
                           COALESCE(SUM(total_amount), 0) AS revenue
                    FROM orders
                    WHERE restaurant_id = :restaurant_id
                    AND created_at >= :week_start
                    AND status NOT IN ('CANCELLED','FAILED')
                    GROUP BY day_name
                    ORDER BY revenue DESC
                    LIMIT 1
                    """
                ),
                {"restaurant_id": restaurant_id, "week_start": week_start},
            )
        ).mappings().first()

        restaurant_row = (
            await db.execute(
                text("SELECT rating, total_reviews FROM restaurants WHERE id = :restaurant_id"),
                {"restaurant_id": restaurant_id},
            )
        ).mappings().first()

        last_revenue = last_month["revenue"]
        growth = (
            round(((this_month["revenue"] - last_revenue) / last_revenue) * 100, 2)
            if last_revenue
            else 0.0
        )

        return {
            "today": today,
            "this_week": {
                "orders": this_week["orders"],
                "revenue": this_week["revenue"],
                "best_day": best_day_row["day_name"] if best_day_row else None,
                "best_day_revenue": _as_float(best_day_row["revenue"]) if best_day_row else 0.0,
            },
            "this_month": {
                "orders": this_month["orders"],
                "revenue": this_month["revenue"],
                "growth_vs_last_month": growth,
            },
            "all_time": {
                "total_orders": all_time["orders"],
                "total_revenue": all_time["revenue"],
                "avg_rating": _as_float(restaurant_row["rating"]) if restaurant_row else 0.0,
                "total_reviews": int(restaurant_row["total_reviews"] or 0) if restaurant_row else 0,
            },
        }

    async def get_revenue_chart(self, restaurant_id: uuid.UUID, period: str, db: AsyncSession) -> dict:
        if period not in {"7days", "30days", "3months", "year"}:
            raise HTTPException(status_code=422, detail="Invalid period")

        start_at = _period_start(period)
        result = await db.execute(
            text(
                """
                SELECT DATE(created_at AT TIME ZONE 'Asia/Kolkata') AS order_date,
                       COUNT(*) AS order_count,
                       COALESCE(SUM(total_amount), 0) AS revenue
                FROM orders
                WHERE restaurant_id = :restaurant_id
                AND status NOT IN ('CANCELLED','FAILED')
                AND created_at >= :start_at
                GROUP BY DATE(created_at AT TIME ZONE 'Asia/Kolkata')
                ORDER BY order_date ASC
                """
            ),
            {"restaurant_id": restaurant_id, "start_at": start_at},
        )
        daily = {
            row["order_date"]: {"orders": int(row["order_count"]), "revenue": _as_float(row["revenue"])}
            for row in result.mappings()
        }

        today = datetime.now(IST).date()
        if period in {"7days", "30days"}:
            days = 7 if period == "7days" else 30
            dates = [today - timedelta(days=days - 1 - i) for i in range(days)]
            return {
                "labels": [d.strftime("%b %d") for d in dates],
                "revenue": [daily.get(d, {}).get("revenue", 0.0) for d in dates],
                "orders": [daily.get(d, {}).get("orders", 0) for d in dates],
            }

        buckets: dict[str, dict] = defaultdict(lambda: {"orders": 0, "revenue": 0.0})
        for d, values in daily.items():
            if period == "3months":
                bucket_start = d - timedelta(days=d.weekday())
                label = bucket_start.strftime("%b %d")
            else:
                label = d.strftime("%b %Y")
            buckets[label]["orders"] += values["orders"]
            buckets[label]["revenue"] += values["revenue"]

        labels = []
        if period == "3months":
            start_day = today - timedelta(days=89)
            week_start = start_day - timedelta(days=start_day.weekday())
            while week_start <= today:
                labels.append(week_start.strftime("%b %d"))
                week_start += timedelta(days=7)
        else:
            cursor = date(today.year, today.month, 1)
            for _ in range(12):
                labels.append(cursor.strftime("%b %Y"))
                cursor = (cursor.replace(day=28) - timedelta(days=32)).replace(day=1)
            labels.reverse()

        return {
            "labels": labels,
            "revenue": [round(buckets[label]["revenue"], 2) for label in labels],
            "orders": [buckets[label]["orders"] for label in labels],
        }

    async def get_top_items(self, restaurant_id: uuid.UUID, period: str, limit: int, db: AsyncSession) -> list[dict]:
        start_at = _period_start(period)
        rows = (
            await db.execute(
                text(
                    """
                    SELECT oi.name, oi.menu_item_id,
                           COUNT(*) AS order_count,
                           COALESCE(SUM(oi.price * oi.quantity), 0) AS revenue
                    FROM order_items oi
                    JOIN orders o ON o.id = oi.order_id
                    WHERE o.restaurant_id = :restaurant_id
                    AND o.status = 'DELIVERED'
                    AND o.created_at >= :start_at
                    GROUP BY oi.menu_item_id, oi.name
                    ORDER BY order_count DESC
                    LIMIT :limit
                    """
                ),
                {"restaurant_id": restaurant_id, "start_at": start_at, "limit": limit},
            )
        ).mappings().all()
        return [
            {
                "rank": idx,
                "menu_item_id": str(row["menu_item_id"]) if row["menu_item_id"] else None,
                "name": row["name"],
                "order_count": int(row["order_count"] or 0),
                "orders_count": int(row["order_count"] or 0),
                "revenue": _as_float(row["revenue"]),
            }
            for idx, row in enumerate(rows, start=1)
        ]

    async def get_peak_hours(self, restaurant_id: uuid.UUID, db: AsyncSession) -> dict:
        rows = (
            await db.execute(
                text(
                    """
                    SELECT EXTRACT(HOUR FROM created_at AT TIME ZONE 'Asia/Kolkata') AS hour,
                           COUNT(*) AS order_count
                    FROM orders
                    WHERE restaurant_id = :restaurant_id
                    AND status NOT IN ('CANCELLED','FAILED')
                    AND created_at >= now() - INTERVAL '30 days'
                    GROUP BY hour
                    ORDER BY hour ASC
                    """
                ),
                {"restaurant_id": restaurant_id},
            )
        ).mappings().all()
        counts = {int(row["hour"]): int(row["order_count"]) for row in rows}
        return {
            "hours": [
                {
                    "hour": f"{hour:02d}:00",
                    "order_count": counts.get(hour, 0),
                    "avg_orders": round(counts.get(hour, 0) / 30, 2),
                }
                for hour in range(24)
            ]
        }

    async def get_ratings_summary(self, restaurant_id: uuid.UUID, db: AsyncSession) -> dict:
        restaurant = (
            await db.execute(
                text("SELECT rating, total_reviews FROM restaurants WHERE id = :restaurant_id"),
                {"restaurant_id": restaurant_id},
            )
        ).mappings().first()

        food_rows = (
            await db.execute(
                text("SELECT food_rating, COUNT(*) AS count FROM reviews WHERE restaurant_id=:restaurant_id GROUP BY food_rating"),
                {"restaurant_id": restaurant_id},
            )
        ).mappings().all()
        delivery_rows = (
            await db.execute(
                text("SELECT delivery_rating, COUNT(*) AS count FROM reviews WHERE restaurant_id=:restaurant_id GROUP BY delivery_rating"),
                {"restaurant_id": restaurant_id},
            )
        ).mappings().all()
        recent = (
            await db.execute(
                text(
                    """
                    SELECT food_rating, delivery_rating, comment, response_text, created_at
                    FROM reviews
                    WHERE restaurant_id = :restaurant_id
                    AND comment IS NOT NULL
                    ORDER BY created_at DESC
                    LIMIT 5
                    """
                ),
                {"restaurant_id": restaurant_id},
            )
        ).mappings().all()

        combined = {i: 0 for i in range(1, 6)}
        food_breakdown = {i: 0 for i in range(1, 6)}
        delivery_breakdown = {i: 0 for i in range(1, 6)}
        for row in food_rows:
            food_breakdown[int(row["food_rating"])] = int(row["count"])
            combined[int(row["food_rating"])] += int(row["count"])
        for row in delivery_rows:
            delivery_breakdown[int(row["delivery_rating"])] = int(row["count"])
            combined[int(row["delivery_rating"])] += int(row["count"])

        return {
            "overall_rating": _as_float(restaurant["rating"]) if restaurant else 0.0,
            "total_reviews": int(restaurant["total_reviews"] or 0) if restaurant else 0,
            "breakdown": {f"{i}_star": combined[i] for i in range(5, 0, -1)},
            "food_breakdown": {str(k): v for k, v in food_breakdown.items()},
            "delivery_breakdown": {str(k): v for k, v in delivery_breakdown.items()},
            "recent_reviews": [
                {
                    "food_rating": row["food_rating"],
                    "delivery_rating": row["delivery_rating"],
                    "comment": row["comment"],
                    "response_text": row.get("response_text"),
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                }
                for row in recent
            ],
        }
