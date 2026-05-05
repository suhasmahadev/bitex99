import uuid
from fastapi import APIRouter
from pydantic import BaseModel
from app.dependencies import ApprovedPartner, DB
from app.services import support_service

router = APIRouter(prefix="/api/v1/partner/support/tickets", tags=["Partner Support"])

class TicketCreate(BaseModel):
    category: str
    subject: str
    description: str
    assignment_id: uuid.UUID | None = None

@router.post("")
async def create_ticket(
    req: TicketCreate,
    partner: ApprovedPartner,
    db: DB
):
    ticket = await support_service.create_ticket(
        partner.id,
        req.category,
        req.subject,
        req.description,
        req.assignment_id,
        db
    )
    await db.commit()
    return {
        "id": str(ticket.id),
        "status": ticket.status.value,
        "category": ticket.category.value,
        "subject": ticket.subject
    }

@router.get("")
async def list_tickets(
    partner: ApprovedPartner,
    db: DB,
    page: int = 1,
    limit: int = 20
):
    return await support_service.get_tickets(partner.id, db, page, limit)
