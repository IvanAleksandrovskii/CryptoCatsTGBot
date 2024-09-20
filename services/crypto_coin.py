from sqlalchemy import select, Sequence
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

    async def get_coin_by_code(self, code: str) -> Coin:
        result = await self.session.execute(select(Coin).where(Coin.code == code))
        return result.scalar_one_or_none()

    async def get_all_coins(self) -> Sequence[Coin]:
        result = await self.session.execute(select(Coin))
        return [coin for coin in result.scalars().all()]
