from aiogram import Router, types
from aiogram.filters import CommandStart

from core import logger
from core.models import db_helper
from handlers import main_keyboard
from services import UserService

router = Router()


@router.message(CommandStart())
async def start_handler(message: types.Message):
    username = message.from_user.username
    chat_id = message.chat.id

    async for session in db_helper.session_getter():
        try:
            user_service = UserService(session)
            user = await user_service.get_user(chat_id)
            if not user:
                await user_service.create_user(chat_id, username)
                await message.answer(
                    f"Привет, {username}! Я бот для отслеживания цен криптовалют. И я люблю котиков :3",
                    reply_markup=main_keyboard)
            else:
                await message.answer(f"С возвращением, {username}! Посмотрим цены или котиков?",
                                     reply_markup=main_keyboard)
        except Exception as e:
            logger.error(f"Database error: {e}")
            await message.answer("Извините, произошла ошибка. Пожалуйста, попробуйте позже.",
                                 reply_markup=main_keyboard)
        finally:
            await session.close()
