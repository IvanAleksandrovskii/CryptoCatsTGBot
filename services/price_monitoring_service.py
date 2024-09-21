import asyncio
from aiogram import Bot
# from aiogram.types import InputFile

from core import logger
from core.models import db_helper, Coin, UserCoinAssociation
from services import UserService, CoinService, CryptoPriceService
from services.get_cat_image import get_random_cat_image


class PriceMonitor:
    def __init__(self, bot: Bot, update_interval: int = 300):
        self.bot = bot
        self.update_interval = update_interval
        self.crypto_price_service = CryptoPriceService()

    @staticmethod
    def check_price_conditions(coin: Coin, association: UserCoinAssociation, current_price: float):
        conditions_met = []

        if association.min_rate and current_price <= association.min_rate:
            conditions_met.append(f"Цена {coin.code} упала до {current_price:.2f} (ниже {association.min_rate:.2f})")

        if association.max_rate and current_price >= association.max_rate:
            conditions_met.append(
                f"Цена {coin.code} поднялась до {current_price:.2f} (выше {association.max_rate:.2f})")

        if association.rate_percentage_growth and association.saved_rate_to_compare:
            growth = (current_price - association.saved_rate_to_compare) / association.saved_rate_to_compare * 100
            if growth >= association.rate_percentage_growth:
                conditions_met.append(
                    f"Цена {coin.code} выросла на {growth:.2f}% (больше {association.rate_percentage_growth:.2f}%)")

        if association.rate_percentage_declines and association.saved_rate_to_compare:
            decline = (association.saved_rate_to_compare - current_price) / association.saved_rate_to_compare * 100
            if decline >= association.rate_percentage_declines:
                conditions_met.append(
                    f"Цена {coin.code} упала на {decline:.2f}% (больше {association.rate_percentage_declines:.2f}%)")

        return conditions_met

    async def process_user(self, user, current_prices, cat_image_url):
        async with db_helper.db_session() as session:
            user_service = UserService(session)
            user_coins = await user_service.get_user_coins(user.chat_id)

            all_conditions_met = []
            for coin, association in user_coins:
                if coin.coin_id_for_price_getter in current_prices:
                    current_price = current_prices[coin.coin_id_for_price_getter]
                    conditions_met = self.check_price_conditions(coin, association, current_price)
                    all_conditions_met.extend(conditions_met)

                    # Update saved_rate_to_compare
                    await user_service.update_user_coin(
                        user.chat_id,
                        coin.id,
                        association.id,
                        saved_rate_to_compare=current_price
                    )

            if all_conditions_met:
                message = "Уведомление о изменении цены:\n" + "\n".join(all_conditions_met)
                await self.bot.send_photo(user.chat_id, photo=cat_image_url, caption=message)

    async def update_prices_and_notify(self):
        try:
            async with db_helper.db_session() as session:
                user_service = UserService(session)
                coin_service = CoinService(session)

                all_users = await user_service.get_all_users()
                all_coins = await coin_service.get_all_active_coins()

            coin_ids = [coin.coin_id_for_price_getter for coin in all_coins if coin.coin_id_for_price_getter]
            current_prices = await self.crypto_price_service.get_crypto_prices(coin_ids)

            # Get a single cat image URL for all notifications
            cat_image_url = await get_random_cat_image()

            # Process users concurrently
            await asyncio.gather(*[self.process_user(user, current_prices, cat_image_url) for user in all_users])

        except Exception as e:
            logger.error(f"Failed to update prices and notify users: {e}")

    async def run(self):
        while True:
            await self.update_prices_and_notify()
            await asyncio.sleep(self.update_interval)
