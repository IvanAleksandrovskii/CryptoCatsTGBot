import asyncio

from aiogram import Router, types
from aiogram.filters import Command

from core import logger
from handlers import main_keyboard
from services import get_random_cat_image

router = Router()


@router.message(Command("meow"))
async def meow_handler(message: types.Message):
    max_retry = 3
    for retry in range(max_retry):
        try:
            cat_image = await get_random_cat_image()
            await message.answer_photo(cat_image, reply_markup=main_keyboard, caption="Мяу Мяу :3")
            return
        except Exception as e:
            logger.error(f"Failed to send cat image (attempt {retry + 1}/{max_retry}): {e}")
            if retry < max_retry - 1:
                await asyncio.sleep(1)

    await message.answer("Извините, я не смог отправить изображение! Попробуйте еще раз позже.",
                         reply_markup=main_keyboard)
