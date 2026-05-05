from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from app.dependencies import DB, CurrentUser, RestaurantUser
from app.services.restaurant_document_service import RestaurantDocumentService

router = APIRouter(prefix="/api/v1/restaurant/documents", tags=["Restaurant Documents"])

@router.get("/status")
async def get_document_status(
    current_user: CurrentUser,
    db: DB,
    partner: RestaurantUser
):
    if not partner:
        raise HTTPException(status_code=400, detail="Complete profile setup first")
    svc = RestaurantDocumentService(db)
    return await svc.get_document_status(partner.id, current_user.id)

@router.post("/upload")
async def upload_document(
    current_user: CurrentUser,
    db: DB,
    partner: RestaurantUser,
    doc_type: str = Form(...),
    file: UploadFile = File(...)
):
    if not partner:
        raise HTTPException(status_code=400, detail="Complete profile setup first")
    svc = RestaurantDocumentService(db)
    return await svc.upload_document(partner.id, current_user.id, doc_type, file)

@router.post("/submit")
async def submit_documents(
    current_user: CurrentUser,
    db: DB,
    partner: RestaurantUser
):
    if not partner:
        raise HTTPException(status_code=400, detail="Complete profile setup first")
    
    svc = RestaurantDocumentService(db)
    status_data = await svc.get_document_status(partner.id, current_user.id)
    if not status_data["can_submit"]:
        raise HTTPException(status_code=400, detail={
            "error_code": "MISSING_DOCUMENTS",
            "missing": status_data["missing_required"]
        })
    
    if current_user.restaurant_status != "DOCS_SUBMITTED":
        if current_user.restaurant_status == "DOCS_APPROVED":
            raise HTTPException(status_code=400, detail="Documents already approved")
        
        current_user.restaurant_status = "DOCS_SUBMITTED"
        await db.commit()

    return {"message": "Documents submitted successfully. Waiting for admin approval."}
