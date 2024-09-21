from aiogram import Router, types
from aiogram.filters import Command
from core.models import db_helper
from services import CoinService, CryptoPriceService, UserService

router = Router()


@router.message(Command("all_prices"))
async def get_all_prices(message: types.Message):
    async with db_helper.db_session() as session:
        coin_service = CoinService(session)
        price_service = CryptoPriceService()

        all_coins = await coin_service.get_all_active_coins()
        coin_ids = [coin.coin_id_for_price_getter for coin in all_coins if coin.coin_id_for_price_getter]

        if not coin_ids:
            await message.answer("В системе нет активных монет с идентификаторами для получения цен.")
            return

        all_prices = await price_service.get_crypto_prices(coin_ids)

        if not all_prices:
            await message.answer("Не удалось получить текущие курсы. Попробуйте позже.")
            return

        response = "Текущие курсы всех монет:\n\n"
        for coin in all_coins:
            if coin.coin_id_for_price_getter:
                price = all_prices.get(str(coin.coin_id_for_price_getter), "N/A")
                response += f"{coin.code}: ${price}\n"
            else:
                response += f"{coin.code}: Цена недоступна\n"

        await message.answer(response)


@router.message(Command("portfolio_prices"))
async def get_portfolio_prices(message: types.Message):
    async with db_helper.db_session() as session:
        user_service = UserService(session)
        price_service = CryptoPriceService()

        user = await user_service.get_user(message.from_user.id)
        if not user:
            await message.answer("Пользователь не найден. Пожалуйста, начните с команды /start")
            return

        user_coins = await user_service.get_user_coins(user.chat_id)
        if not user_coins:
            await message.answer("В вашем портфолио нет монет.")
            return

        coin_ids = [coin.coin_id_for_price_getter for coin, _ in user_coins if coin.coin_id_for_price_getter]
        prices = await price_service.get_crypto_prices(coin_ids)

        response = "Текущие курсы монет в вашем портфолио:\n\n"
        for coin, association in user_coins:
            price = prices.get(coin.coin_id_for_price_getter, "N/A")
            response += f"{coin.code}: ${price}\n"
            if association.min_rate:
                response += f"  Мин. курс: ${association.min_rate}\n"
            if association.max_rate:
                response += f"  Макс. курс: ${association.max_rate}\n"
            response += "\n"

        await message.answer(response)
