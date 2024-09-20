import asyncio
import logging

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv
import os

from core.models import http_helper
from handlers import router as handlers_router
from services import PriceMonitor

logging.basicConfig(level=logging.INFO)
load_dotenv(".env")

BOT_TOKEN = os.getenv("BOT_TOKEN")

dp = Dispatcher()

dp.include_router(handlers_router)


async def start_price_monitor(bot):
    price_monitor = PriceMonitor(bot, update_interval=300)  # Check every 5 minutes
    await price_monitor.run()


async def main():
    logging.info("Starting the bot")
    bot = Bot(token=BOT_TOKEN)

    await http_helper.start()

    # Start PriceMonitor in a separate task
    price_monitor_task = asyncio.create_task(start_price_monitor(bot))

    try:
        await dp.start_polling(bot)
    finally:
        # Cancel PriceMonitor task
        price_monitor_task.cancel()
        try:
            await price_monitor_task
        except asyncio.CancelledError:
            pass

        await http_helper.dispose_all_clients()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
