import asyncio
import logging
from typing import Dict, List, Tuple
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from core import logger
from core.models import http_helper, db_helper
from services import CoinService


class CryptoPriceService:
    def __init__(self, update_interval: int = 300):
        self.update_interval = update_interval
        self.previous_prices: Dict[str, float] = {}

    @staticmethod
    async def get_crypto_prices(coin_ids: List[str]) -> Dict[str, float]:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": ",".join(coin_ids),
            "vs_currencies": "usd"
        }
        client = await http_helper.get_client()
        try:
            response = await client.request('GET', url, params=params)
            data = await response.json()
        except Exception as e:
            logging.error(f"Request error: %s", e)
        finally:
            await http_helper.release_client(client)

        return {coin_id: data[coin_id]["usd"] for coin_id in coin_ids if coin_id in data}

    async def update_prices(self):
        async for session in db_helper.session_getter():
            try:
                coin_service = CoinService(session)
                active_coins = await coin_service.get_all_active_coins()

                coin_ids = [coin.coin_id_for_price_getter for coin in active_coins if coin.coin_id_for_price_getter]
                current_prices = await self.get_crypto_prices(coin_ids)

                for coin in active_coins:
                    if coin.coin_id_for_price_getter in current_prices:
                        price = current_prices[coin.coin_id_for_price_getter]
                        previous_price = self.previous_prices.get(coin.code, price)
                        price_change = price - previous_price
                        change_symbol = '+' if price_change >= 0 else '-'

                        print(f"{coin.code} {price:.4f} {change_symbol}{abs(price_change):.4f}")

                        self.previous_prices[coin.code] = price

            except Exception as e:
                logging.error(f"Failed to update prices: {e}")
            finally:
                await session.close()

    async def run(self):
        while True:
            await self.update_prices()
            await asyncio.sleep(self.update_interval)


async def main():
    logging.basicConfig(level=logging.INFO)
    await http_helper.start()

    price_service = CryptoPriceService(update_interval=30)
    await price_service.run()


# if __name__ == "__main__":
#     try:
#         asyncio.run(main())
#     except KeyboardInterrupt:
#         logger.info("Shutting down...")
#     finally:
#         http_helper.dispose_all_clients()
