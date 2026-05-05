"""
Address service: CRUD for multi-address management.
"""

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import AddressNotFoundError, ForbiddenError
from app.models.address import Address
from app.schemas.address import (
    AddressResponse,
    CreateAddressRequest,
    UpdateAddressRequest,
)


class AddressService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_addresses(self, user_id: uuid.UUID) -> list[AddressResponse]:
        result = await self._db.execute(
            select(Address)
            .where(Address.user_id == user_id)
            .order_by(Address.is_default.desc(), Address.created_at.desc())
        )
        return [AddressResponse.model_validate(a) for a in result.scalars().all()]

    async def create_address(
        self, user_id: uuid.UUID, data: CreateAddressRequest
    ) -> AddressResponse:
        # If this is marked as default, un-default all others
        if data.is_default:
            await self._clear_default(user_id)

        address = Address(user_id=user_id, **data.model_dump())
        self._db.add(address)
        await self._db.flush()
        return AddressResponse.model_validate(address)

    async def update_address(
        self, user_id: uuid.UUID, address_id: uuid.UUID, data: UpdateAddressRequest
    ) -> AddressResponse:
        address = await self._get_address(user_id, address_id)
        update_data = data.model_dump(exclude_unset=True)

        if update_data.get("is_default"):
            await self._clear_default(user_id)

        for field, value in update_data.items():
            setattr(address, field, value)
        await self._db.flush()
        return AddressResponse.model_validate(address)

    async def delete_address(self, user_id: uuid.UUID, address_id: uuid.UUID) -> None:
        address = await self._get_address(user_id, address_id)
        await self._db.delete(address)
        await self._db.flush()

    async def set_default(self, user_id: uuid.UUID, address_id: uuid.UUID) -> AddressResponse:
        address = await self._get_address(user_id, address_id)
        await self._clear_default(user_id)
        address.is_default = True
        await self._db.flush()
        return AddressResponse.model_validate(address)

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _get_address(self, user_id: uuid.UUID, address_id: uuid.UUID) -> Address:
        result = await self._db.execute(
            select(Address).where(Address.id == address_id)
        )
        address = result.scalar_one_or_none()
        if address is None:
            raise AddressNotFoundError()
        if address.user_id != user_id:
            raise ForbiddenError(detail="This address does not belong to you")
        return address

    async def _clear_default(self, user_id: uuid.UUID) -> None:
        await self._db.execute(
            update(Address)
            .where(Address.user_id == user_id, Address.is_default.is_(True))
            .values(is_default=False)
        )
