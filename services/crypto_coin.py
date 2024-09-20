from typing import List, Type
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Coin


class CoinService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_coin(self, code: str, name: str = None, coin_id_for_price_getter: str = None) -> Coin:
        coin = Coin(code=code, name=name, coin_id_for_price_getter=coin_id_for_price_getter)
        self.session.add(coin)
        await self.session.commit()
        await self.session.refresh(coin)
        return coin

    async def get_coin_by_code(self, code: UUID) -> Coin:
        result = await self.session.execute(select(Coin).where(Coin.code == code))
        return result.scalar_one_or_none()

    async def get_coin_by_id(self, coin_id: UUID) -> Coin:
        result = await self.session.execute(select(Coin).where(Coin.id == coin_id))
        return result.scalar_one_or_none()

    async def get_all_coins(self) -> List[Coin]:
        result = await self.session.execute(select(Coin))
        return [coin for coin in result.scalars().all()]

    async def update_coin(self, coin_id: UUID, code: str = None, name: str = None,
                          coin_id_for_price_getter: str = None) -> Type[Coin] | None:
        coin = await self.session.get(Coin, coin_id)
        if coin:
            if code is not None:
                coin.code = code
            if name is not None:
                coin.name = name
            if coin_id_for_price_getter is not None:
                coin.coin_id_for_price_getter = coin_id_for_price_getter
            await self.session.commit()
            await self.session.refresh(coin)
        return coin

    async def delete_coin(self, coin_id: UUID) -> bool:
        coin = await self.session.get(Coin, coin_id)
        if coin:
            await self.session.delete(coin)
            await self.session.commit()
            return True
        return False
