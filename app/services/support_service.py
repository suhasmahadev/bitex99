import uuid
import logging
from datetime import UTC, datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.support_ticket import SupportTicket, TicketCategory, TicketStatus

logger = logging.getLogger(__name__)

async def create_ticket(
    partner_id: uuid.UUID,
    category: str,
    subject: str,
    description: str,
    assignment_id: uuid.UUID | None,
    db: AsyncSession
) -> SupportTicket:
    try:
        cat_enum = TicketCategory(category)
    except ValueError:
        cat_enum = TicketCategory.OTHER
        
    ticket = SupportTicket(
        partner_id=partner_id,
        assignment_id=assignment_id,
        category=cat_enum,
        subject=subject,
        description=description,
        status=TicketStatus.OPEN,
        created_at=datetime.now(UTC)
    )
    db.add(ticket)
    await db.flush()
    return ticket

async def get_tickets(partner_id: uuid.UUID, db: AsyncSession, page: int = 1, limit: int = 20):
    offset = (page - 1) * limit
    query = select(SupportTicket).where(SupportTicket.partner_id == partner_id).order_by(SupportTicket.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    tickets = result.scalars().all()
    
    return [
        {
            "id": str(t.id),
            "category": t.category.value,
            "subject": t.subject,
            "description": t.description,
            "status": t.status.value,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        } for t in tickets
    ]

async def get_ticket(ticket_id: uuid.UUID, partner_id: uuid.UUID, db: AsyncSession):
    ticket = await db.scalar(select(SupportTicket).where(SupportTicket.id == ticket_id, SupportTicket.partner_id == partner_id))
    if not ticket:
        return None
    return {
        "id": str(ticket.id),
        "category": ticket.category.value,
        "subject": ticket.subject,
        "description": ticket.description,
        "status": ticket.status.value,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
    }
