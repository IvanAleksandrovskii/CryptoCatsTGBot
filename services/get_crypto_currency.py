from typing import Dict

from core.models import http_helper


async def get_crypto_prices() -> Dict[str, float]:
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "bitcoin,ethereum,nolus,celestia,coreum,dymension,islamic-coin,matic-network,lava-network,terra-luna,dydx,crypto-com-chain,saga-2,the-open-network",
        "vs_currencies": "usd"
    }
    async with http_helper as client:  # TODO: fix
        response = await client.request('GET', url)
        data = await response.json()

    return {
        "BTC": data["bitcoin"]["usd"],
        "ETH": data["ethereum"]["usd"],
        "NLS": data["nolus"]["usd"],
        "TIA": data["celestia"]["usd"],
        "COREUM": data["coreum"]["usd"],
        "DYM": data["dymension"]["usd"],
        "ISLM": data["islamic-coin"]["usd"],
        "MATIC": data["matic-network"]["usd"],
        "LAVA": data["lava-network"]["usd"],
        "LUNA": data["terra-luna"]["usd"],
        "DYDX": data["dydx"]["usd"],
        "CRO": data["crypto-com-chain"]["usd"],
        "SAGA": data["saga-2"]["usd"],
        "TON": data["the-open-network"]["usd"]
    }

# def compare_prices(current: Dict[str, float], previous: Dict[str, float]) -> Dict[str, Tuple[float, float]]:
#     return {
#         coin: (price, ((price - previous[coin]) / previous[coin]) * 100 if previous[coin] != 0 else 0)
#         for coin, price in current.items()
#     }


# @dp.message(Command("price"))
# async def price_handler(message: types.Message):
#     current_prices = await get_crypto_prices()
#     previous_prices = getattr(price_handler, "previous_prices", current_prices)
#     price_changes = compare_prices(current_prices, previous_prices)
#
#     response = "Текущие курсы криптовалют:\n\n"
#     for coin, (price, change) in price_changes.items():
#         change_symbol = "🔺" if change > 0 else "🔻" if change < 0 else "➡️"
#         response += f"{coin}: ${price:.4f} {change_symbol} {abs(change):.2f}%\n"
#
#     cat_image_url = await get_random_cat_image()
#
#     await message.answer_photo(photo=cat_image_url, caption=response)
#
#     price_handler.previous_prices = current_prices


# async def send_price_updates():
#     while True:
#         current_prices = await get_crypto_prices()
#         previous_prices = getattr(send_price_updates, "previous_prices", current_prices)
#         price_changes = compare_prices(current_prices, previous_prices)
#
#         response = "Обновление курсов криптовалют:\n\n"
#         for coin, (price, change) in price_changes.items():
#             change_symbol = "🔺" if change > 0 else "🔻" if change < 0 else "➡️"
#             response += f"{coin}: ${price:.4f} {change_symbol} {abs(change):.2f}%\n"
#
#         cat_image_url = await get_random_cat_image()
#
#         async for session in db_helper.session_getter():
#             try:
#                 user_service = UserService(session)
#                 users = await user_service.get_all_users()
#                 for user in users:
#                     try:
#                         await bot.send_photo(user.chat_id, photo=cat_image_url, caption=response)
#                     except Exception as e:
#                         logging.error(f"Failed to send message to user {user.chat_id}: {e}")
#             except Exception as e:
#                 logging.error(f"Failed to get users: {e}")
#             finally:
#                 await session.close()
#
#         send_price_updates.previous_prices = current_prices
#         await asyncio.sleep(300)  # 5 minutes
