from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.models import TGUser


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
