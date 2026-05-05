import uuid

from fastapi import APIRouter
from sqlalchemy import select, func
from pydantic import BaseModel

from app.dependencies import DB, AdminUser
from app.models.restaurant import Restaurant
from app.models.restaurant_partner import RestaurantPartner
from app.models.restaurant_document import RestaurantDocument
from app.models.user import User

router = APIRouter(prefix="/api/v1/admin/restaurant", tags=["Admin Restaurant"])

class RejectDocumentRequest(BaseModel):
    doc_type: str
    reason: str

@router.get("/pending")
async def get_pending_restaurants(
    admin: AdminUser,
    db: DB
):
    users = await db.scalars(select(User).where(User.restaurant_status == "DOCS_SUBMITTED"))
    user_ids = [u.id for u in users.all()]
    if not user_ids:
        return []
    
    partners = await db.scalars(select(RestaurantPartner).where(RestaurantPartner.user_id.in_(user_ids)))
    
    results = []
    for partner in partners:
        restaurant = await db.scalar(select(Restaurant).where(Restaurant.id == partner.restaurant_id))
        docs = await db.scalars(select(RestaurantDocument).where(RestaurantDocument.partner_id == partner.id))
        user = await db.scalar(select(User).where(User.id == partner.user_id))
        
        results.append({
            "partner_id": partner.id,
            "restaurant_name": restaurant.name,
            "city": restaurant.city,
            "owner_name": partner.owner_name,
            "phone": user.phone,
            "submitted_at": partner.joined_at,
            "documents": [
                {
                    "doc_type": d.doc_type,
                    "status": d.status,
                    "file_url": d.file_url,
                    "uploaded_at": d.uploaded_at
                } for d in docs.all()
            ]
        })
    return results

@router.post("/{partner_id}/approve")
async def approve_restaurant(
    partner_id: uuid.UUID,
    admin: AdminUser,
    db: DB
):
    partner = await db.scalar(select(RestaurantPartner).where(RestaurantPartner.id == partner_id))
    user = await db.scalar(select(User).where(User.id == partner.user_id))
    restaurant = await db.scalar(select(Restaurant).where(Restaurant.id == partner.restaurant_id))

    docs = await db.scalars(select(RestaurantDocument).where(RestaurantDocument.partner_id == partner.id))
    for doc in docs.all():
        doc.status = "APPROVED"
        doc.verified_at = func.now()
        doc.verified_by = admin.id
    
    user.restaurant_status = "DOCS_APPROVED"
    restaurant.is_open = True

    await db.commit()
    return {"message": "Approved. Restaurant is now live."}

@router.post("/{partner_id}/reject")
async def reject_document(
    partner_id: uuid.UUID,
    body: RejectDocumentRequest,
    admin: AdminUser,
    db: DB
):
    doc = await db.scalar(
        select(RestaurantDocument).where(
            RestaurantDocument.partner_id == partner_id,
            RestaurantDocument.doc_type == body.doc_type
        )
    )
    if doc:
        doc.status = "REJECTED"
        doc.rejection_reason = body.reason
        doc.verified_at = func.now()
        doc.verified_by = admin.id
    
    partner = await db.scalar(select(RestaurantPartner).where(RestaurantPartner.id == partner_id))
    user = await db.scalar(select(User).where(User.id == partner.user_id))
    user.restaurant_status = "DOCS_REJECTED"

    await db.commit()
    return {"message": "Document rejected"}
