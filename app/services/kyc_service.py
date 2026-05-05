import os
import time
import uuid
import asyncio
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.delivery_partner import DeliveryPartner
from app.models.kyc_document import KycDocument, DocType
from app.models.user import User
from app.schemas.kyc import DocumentStatus, KYCStatusResponse

REQUIRED_DOCS = {
    'AADHAAR_FRONT', 'AADHAAR_BACK', 'PAN_CARD',
    'DRIVING_LICENSE_FRONT', 'DRIVING_LICENSE_BACK',
    'VEHICLE_RC', 'VEHICLE_INSURANCE',
    'BANK_PASSBOOK', 'PROFILE_PHOTO'
}

class KYCService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_kyc_status(self, partner_id: uuid.UUID) -> KYCStatusResponse:
        partner = await self._db.scalar(select(DeliveryPartner).where(DeliveryPartner.id == partner_id))
        if not partner:
            raise HTTPException(status_code=404, detail="Partner not found")
            
        user = await self._db.scalar(select(User).where(User.id == partner.user_id))
        
        docs = await self._db.scalars(
            select(KycDocument).where(KycDocument.partner_id == partner_id)
        )
        docs_list = list(docs)
        
        uploaded_doc_types = {doc.doc_type.name for doc in docs_list}
        missing_required = list(REQUIRED_DOCS - uploaded_doc_types)
        
        doc_statuses = [
            DocumentStatus(
                doc_type=doc.doc_type.name,
                status=doc.status.name,
                uploaded_at=doc.uploaded_at,
                rejection_reason=doc.rejection_reason,
            )
            for doc in docs_list
        ]
        
        return KYCStatusResponse(
            overall_status=user.partner_status,
            documents=doc_statuses,
            missing_required=missing_required,
            can_submit=len(missing_required) == 0
        )

    async def upload_document(self, partner_id: uuid.UUID, doc_type: str, file: UploadFile) -> KYCStatusResponse:
        try:
            doc_enum = DocType(doc_type)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid doc_type")
            
        if file.content_type not in ['image/jpeg', 'image/png', 'application/pdf']:
            raise HTTPException(
                status_code=400, 
                detail={"error_code": "INVALID_FILE_TYPE", "message": "Only JPEG, PNG, PDF allowed"}
            )
            
        contents = await file.read()
        if len(contents) > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=400, 
                detail={"error_code": "FILE_TOO_LARGE", "max_size_mb": 5}
            )
            
        ext = file.filename.split('.')[-1] if file.filename and '.' in file.filename else 'bin'
        filename = f"{doc_type}_{int(time.time())}.{ext}"
        
        directory = os.path.join("uploads", "kyc", str(partner_id))
        os.makedirs(directory, exist_ok=True)
        
        file_path = os.path.join(directory, filename)
        await asyncio.to_thread(Path(file_path).write_bytes, contents)
            
        file_url = f"/uploads/kyc/{partner_id}/{filename}"
        
        stmt = insert(KycDocument).values(
            partner_id=partner_id,
            doc_type=doc_enum,
            file_url=file_url,
            file_name=file.filename,
            status='PENDING'
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=['partner_id', 'doc_type'],
            set_={
                'file_url': file_url,
                'file_name': file.filename,
                'status': 'PENDING',
                'rejection_reason': None,
                'uploaded_at': func.now()
            }
        )
        await self._db.execute(stmt)
        await self._db.flush()
        
        # Check if ALL required docs now uploaded
        docs = await self._db.scalars(
            select(KycDocument).where(KycDocument.partner_id == partner_id)
        )
        uploaded_doc_types = {doc.doc_type.name for doc in docs}
        missing_required = REQUIRED_DOCS - uploaded_doc_types
        
        if len(missing_required) == 0:
            partner = await self._db.scalar(select(DeliveryPartner).where(DeliveryPartner.id == partner_id))
            user = await self._db.scalar(select(User).where(User.id == partner.user_id))
            if user.partner_status == "PENDING_KYC":
                user.partner_status = "KYC_SUBMITTED"
                
        await self._db.commit()
        return await self.get_kyc_status(partner_id)

    async def submit_kyc(self, partner_id: uuid.UUID) -> dict[str, str]:
        status = await self.get_kyc_status(partner_id)
        if len(status.missing_required) > 0:
            raise HTTPException(status_code=400, detail="Missing required documents")
            
        partner = await self._db.scalar(select(DeliveryPartner).where(DeliveryPartner.id == partner_id))
        user = await self._db.scalar(select(User).where(User.id == partner.user_id))
        
        if user.partner_status != "KYC_SUBMITTED":
             raise HTTPException(status_code=400, detail="Status must be KYC_SUBMITTED")
             
        return {"message": "KYC submitted successfully"}
