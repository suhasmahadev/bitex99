"""
Assignment lifecycle router — SPEC2.md Section 8.
Prefix: /api/v1/partner/assignments
Auth: require_approved_partner() on all endpoints.

Full lifecycle: accept → reached-restaurant → picked-up → reached-customer → deliver/failed
"""

import logging
import uuid

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.dependencies import ApprovedPartner, DB, Redis
from app.services.assignment_service import AssignmentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/partner/assignments", tags=["Partner Assignments"])


def _get_svc(db: DB, redis: Redis) -> AssignmentService:
    return AssignmentService(db, redis)


def _raise_if_error(result: dict) -> dict:
    """If the service returned an error dict, convert to HTTPException."""
    if "status_code" in result:
        code = result.pop("status_code")
        raise HTTPException(status_code=code, detail=result)
    return result


# ── POST /{id}/accept ───────────────────────────────────────────────────────

@router.post("/{assignment_id}/accept")
async def accept_assignment(
    assignment_id: uuid.UUID,
    partner: ApprovedPartner,
    db: DB,
    redis: Redis,
):
    svc = _get_svc(db, redis)
    result = await svc.accept_assignment(assignment_id, partner)
    return _raise_if_error(result)


# ── POST /{id}/reject ───────────────────────────────────────────────────────

class RejectRequest(BaseModel):
    reason: str | None = None


@router.post("/{assignment_id}/reject")
async def reject_assignment(
    assignment_id: uuid.UUID,
    partner: ApprovedPartner,
    db: DB,
    redis: Redis,
    body: RejectRequest | None = None,
):
    svc = _get_svc(db, redis)
    reason = body.reason if body else None
    result = await svc.reject_assignment(assignment_id, partner, reason)
    return _raise_if_error(result)


# ── POST /{id}/reached-restaurant ───────────────────────────────────────────

@router.post("/{assignment_id}/reached-restaurant")
async def reached_restaurant(
    assignment_id: uuid.UUID,
    partner: ApprovedPartner,
    db: DB,
    redis: Redis,
):
    svc = _get_svc(db, redis)
    result = await svc.reached_restaurant(assignment_id, partner)
    return _raise_if_error(result)


# ── POST /{id}/picked-up ────────────────────────────────────────────────────

@router.post("/{assignment_id}/picked-up")
async def picked_up(
    assignment_id: uuid.UUID,
    partner: ApprovedPartner,
    db: DB,
    redis: Redis,
):
    svc = _get_svc(db, redis)
    result = await svc.picked_up(assignment_id, partner)
    return _raise_if_error(result)


# ── POST /{id}/reached-customer ─────────────────────────────────────────────

@router.post("/{assignment_id}/reached-customer")
async def reached_customer(
    assignment_id: uuid.UUID,
    partner: ApprovedPartner,
    db: DB,
    redis: Redis,
):
    svc = _get_svc(db, redis)
    result = await svc.reached_customer(assignment_id, partner)
    return _raise_if_error(result)


# ── POST /{id}/deliver ──────────────────────────────────────────────────────

class DeliverRequest(BaseModel):
    otp: str


@router.post("/{assignment_id}/deliver")
async def deliver(
    assignment_id: uuid.UUID,
    body: DeliverRequest,
    partner: ApprovedPartner,
    db: DB,
    redis: Redis,
):
    svc = _get_svc(db, redis)
    result = await svc.deliver(assignment_id, partner, body.otp)
    return _raise_if_error(result)


# ── POST /{id}/failed ───────────────────────────────────────────────────────

class FailedRequest(BaseModel):
    reason: str  # CUSTOMER_UNAVAILABLE, ADDRESS_NOT_FOUND, CUSTOMER_REFUSED, OTHER
    description: str = ""


@router.post("/{assignment_id}/failed")
async def fail_delivery(
    assignment_id: uuid.UUID,
    body: FailedRequest,
    partner: ApprovedPartner,
    db: DB,
    redis: Redis,
):
    svc = _get_svc(db, redis)
    result = await svc.fail_delivery(assignment_id, partner, body.reason, body.description)
    return _raise_if_error(result)


# ── GET /active ─────────────────────────────────────────────────────────────

@router.get("/active")
async def get_active_assignment(
    partner: ApprovedPartner,
    db: DB,
    redis: Redis,
):
    svc = _get_svc(db, redis)
    result = await svc.get_active_assignment(partner)
    if result is None:
        return {"active_assignment": None}
    return result


# ── GET /history ────────────────────────────────────────────────────────────

@router.get("/history")
async def get_assignment_history(
    partner: ApprovedPartner,
    db: DB,
    redis: Redis,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
):
    svc = _get_svc(db, redis)
    return await svc.get_assignment_history(partner, page, limit, status)
