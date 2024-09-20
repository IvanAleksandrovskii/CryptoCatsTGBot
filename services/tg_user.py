from typing import List, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.models import TGUser, UserCoinAssociation, Coin


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_user(self, chat_id: int, username: str | None) -> TGUser:
        user = TGUser(chat_id=chat_id, username=username)
        self.session.add(user)
        await self.session.commit()
        return user

    async def get_user(self, chat_id: int) -> TGUser | None:
        result = await self.session.execute(select(TGUser).where(TGUser.chat_id == chat_id))
        return result.scalar_one_or_none()

    async def get_all_users(self) -> list[TGUser]:
        result = await self.session.execute(select(TGUser))
        result = result.scalars().unique().all()
        return [user for user in result]

    async def is_superuser(self, chat_id: int) -> bool:
        user = await self.get_user(chat_id)
        return user is not None and user.is_superuser

    async def add_coin_to_user(self, user_id: UUID, coin_id: UUID, **kwargs) -> UserCoinAssociation:
        association = UserCoinAssociation(user_id=user_id, coin_id=coin_id, **kwargs)
        self.session.add(association)
        await self.session.commit()
        await self.session.refresh(association)
        return association

    async def get_user_coins(self, chat_id: int) -> List[Tuple[Coin, UserCoinAssociation]]:
        user = await self.get_user(chat_id)
        if not user:
            return []
        result = await self.session.execute(
            select(Coin, UserCoinAssociation)
            .join(UserCoinAssociation, Coin.id == UserCoinAssociation.coin_id)
            .where(UserCoinAssociation.user_id == user.id)
        )
        return result.fetchall()

    async def update_user_coin(self, chat_id: int, coin_id: UUID, association_id: UUID, **kwargs) -> bool:
        user = await self.get_user(chat_id)
        if not user:
            return False
        result = await self.session.execute(
            select(UserCoinAssociation)
            .where(UserCoinAssociation.user_id == user.id)
            .where(UserCoinAssociation.coin_id == coin_id)
            .where(UserCoinAssociation.id == association_id)
        )
        association = result.scalar_one_or_none()
        if association:
            for key, value in kwargs.items():
                setattr(association, key, value)
            await self.session.commit()
            await self.session.refresh(association)
            return True
        return False

    async def remove_coin_from_user(self, chat_id: int, coin_id: UUID) -> bool:
        user = await self.get_user(chat_id)
        if not user:
            return False
        result = await self.session.execute(
            select(UserCoinAssociation)
            .where(UserCoinAssociation.user_id == user.id)
            .where(UserCoinAssociation.coin_id == coin_id)
        )
        association = result.scalar_one_or_none()
        if association:
            await self.session.delete(association)
            await self.session.commit()
            return True
        return False
