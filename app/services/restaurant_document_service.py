import os
import time
import uuid
import asyncio
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant_document import RestaurantDocument, DocType
from app.models.user import User

class RestaurantDocumentService:
    REQUIRED_DOCS = [
        'FSSAI_LICENSE',
        'PAN_CARD',
        'BANK_CANCELLED_CHEQUE',
        'OWNER_AADHAAR_FRONT',
        'OWNER_AADHAAR_BACK',
        'RESTAURANT_PHOTO_FRONT'
    ]

    OPTIONAL_DOCS = [
        'GST_CERTIFICATE',
        'SHOP_ACT_LICENSE',
        'MENU_PHOTO',
        'RESTAURANT_PHOTO_INTERIOR',
        'PARTNERSHIP_DEED'
    ]

    ALL_VALID_DOCS = REQUIRED_DOCS + OPTIONAL_DOCS

    def __init__(self, db: AsyncSession):
        self._db = db

    @staticmethod
    def _doc_value(value) -> str:
        return value.value if hasattr(value, "value") else str(value)

    async def get_document_status(self, partner_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        user = await self._db.scalar(select(User).where(User.id == user_id))
        docs = await self._db.scalars(
            select(RestaurantDocument).where(RestaurantDocument.partner_id == partner_id)
        )
        docs_list = list(docs.all())
        
        uploaded_types = {
            self._doc_value(d.doc_type)
            for d in docs_list
            if self._doc_value(d.status) != "REJECTED"
        }
        missing_required = [d for d in self.REQUIRED_DOCS if d not in uploaded_types]
        can_submit = len(missing_required) == 0

        docs_status = []
        for doc_type in self.ALL_VALID_DOCS:
            doc = next((d for d in docs_list if d.doc_type == doc_type), None)
            docs_status.append({
                "doc_type": doc_type,
                "is_required": doc_type in self.REQUIRED_DOCS,
                "status": self._doc_value(doc.status) if doc else None,
                "uploaded_at": doc.uploaded_at if doc else None,
                "rejection_reason": doc.rejection_reason if doc else None,
                "file_url": doc.file_url if doc else None
            })

        return {
            "overall_status": user.restaurant_status,
            "documents": docs_status,
            "missing_required": missing_required,
            "can_submit": can_submit
        }

    async def upload_document(
        self,
        partner_id: uuid.UUID,
        user_id: uuid.UUID,
        doc_type: str,
        file: UploadFile
    ) -> dict:
        if doc_type not in self.ALL_VALID_DOCS:
            raise HTTPException(status_code=400, detail="INVALID_DOC_TYPE")

        allowed_types = ['image/jpeg', 'image/png', 'application/pdf', 'image/jpg']
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail="INVALID_FILE_TYPE")

        content = await file.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="FILE_TOO_LARGE")

        ext = file.filename.split('.')[-1].lower() if file.filename else "jpg"
        directory = f"uploads/restaurant/{partner_id}/"
        os.makedirs(directory, exist_ok=True)
        filename = f"{doc_type}_{int(time.time())}.{ext}"
        filepath = os.path.join(directory, filename)

        await asyncio.to_thread(Path(filepath).write_bytes, content)

        file_url = f"/{directory}{filename}"

        doc = await self._db.scalar(
            select(RestaurantDocument).where(
                RestaurantDocument.partner_id == partner_id,
                RestaurantDocument.doc_type == doc_type
            )
        )
        if doc:
            doc.file_url = file_url
            doc.file_name = filename
            doc.status = "PENDING"
            doc.rejection_reason = None
            doc.uploaded_at = func.now()
        else:
            doc = RestaurantDocument(
                partner_id=partner_id,
                doc_type=doc_type,
                file_url=file_url,
                file_name=filename,
                status="PENDING"
            )
            self._db.add(doc)

        await self._db.commit()

        docs_query = await self._db.scalars(
            select(RestaurantDocument).where(
                RestaurantDocument.partner_id == partner_id,
                RestaurantDocument.status != "REJECTED"
            )
        )
        uploaded = {self._doc_value(d.doc_type) for d in docs_query.all()}
        
        if all(r in uploaded for r in self.REQUIRED_DOCS):
            user = await self._db.scalar(select(User).where(User.id == user_id))
            if user.restaurant_status == "PENDING_DOCS" or user.restaurant_status == "DOCS_REJECTED":
                user.restaurant_status = "DOCS_SUBMITTED"
                await self._db.commit()

        return await self.get_document_status(partner_id, user_id)
