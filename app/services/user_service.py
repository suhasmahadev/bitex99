"""
User service: profile read and update.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import UserNotFoundError
from app.models.user import User
from app.schemas.user import UpdateProfileRequest, UserProfileResponse


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_profile(self, user_id: uuid.UUID) -> UserProfileResponse:
        user = await self._get_user(user_id)
        return UserProfileResponse(
            id=user.id,
            phone=user.phone,
            name=user.name,
            email=user.email,
            avatar_url=user.profile_picture,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at
        )

    async def update_profile(
        self, user_id: uuid.UUID, data: UpdateProfileRequest
    ) -> UserProfileResponse:
        user = await self._get_user(user_id)
        update_data = data.model_dump(exclude_unset=True)
        if 'profile_picture' in update_data:
            user.profile_picture = update_data.pop('profile_picture')
        for field, value in update_data.items():
            setattr(user, field, value)
        await self._db.flush()
        return UserProfileResponse(
            id=user.id,
            phone=user.phone,
            name=user.name,
            email=user.email,
            avatar_url=user.profile_picture,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at
        )

    async def _get_user(self, user_id: uuid.UUID) -> User:
        result = await self._db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise UserNotFoundError()
        return user
