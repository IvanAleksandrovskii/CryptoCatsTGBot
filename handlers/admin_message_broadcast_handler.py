from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import ContentType
from aiogram.fsm.state import State, StatesGroup
from aiogram import Router, types

from core import logger
from core.models import db_helper
from services import UserService

router = Router()


class AdminBroadcastStates(StatesGroup):
    WAITING_FOR_MESSAGE = State()
    WAITING_FOR_CONFIRMATION = State()


class AdminPersonalMessageStates(StatesGroup):
    WAITING_FOR_USER_ID = State()
    WAITING_FOR_MESSAGE = State()


@router.message(Command("broadcast"))
async def start_broadcast(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await message.answer("У вас нет прав для выполнения этой команды.")
        return

    await message.answer(
        "Введите сообщение для массовой рассылки. Вы можете отправить текст, фото, видео, аудио или документ.")
    await state.set_state(AdminBroadcastStates.WAITING_FOR_MESSAGE)


@router.message(AdminBroadcastStates.WAITING_FOR_MESSAGE)
async def process_broadcast_message(message: types.Message, state: FSMContext):
    await state.update_data(message=message)
    await message.answer("Вы уверены, что хотите отправить это сообщение всем пользователям? (Да/Нет)")
    await state.set_state(AdminBroadcastStates.WAITING_FOR_CONFIRMATION)


@router.message(AdminBroadcastStates.WAITING_FOR_CONFIRMATION)
async def confirm_broadcast(message: types.Message, state: FSMContext):
    if message.text.lower() != "да":
        await message.answer("Рассылка отменена.")
        await state.clear()
        return

    data = await state.get_data()
    broadcast_message = data['message']

    async with db_helper.db_session() as session:
        user_service = UserService(session)
        all_users = await user_service.get_all_users()

    for user in all_users:
        try:
            if broadcast_message.content_type == ContentType.TEXT:
                await message.bot.send_message(user.chat_id, broadcast_message.text)
            elif broadcast_message.content_type == ContentType.PHOTO:
                await message.bot.send_photo(user.chat_id, broadcast_message.photo[-1].file_id,
                                             caption=broadcast_message.caption)
            elif broadcast_message.content_type == ContentType.VIDEO:
                await message.bot.send_video(user.chat_id, broadcast_message.video.file_id,
                                             caption=broadcast_message.caption)
            elif broadcast_message.content_type == ContentType.AUDIO:
                await message.bot.send_audio(user.chat_id, broadcast_message.audio.file_id,
                                             caption=broadcast_message.caption)
            elif broadcast_message.content_type == ContentType.DOCUMENT:
                await message.bot.send_document(user.chat_id, broadcast_message.document.file_id,
                                                caption=broadcast_message.caption)
        except Exception as e:
            logger.error(f"Failed to send broadcast to user {user.chat_id}: {e}")

    await message.answer("Рассылка выполнена успешно.")
    await state.clear()


@router.message(Command("send_personal"))
async def start_personal_message(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await message.answer("У вас нет прав для выполнения этой команды.")
        return

    await message.answer("Введите chat_id пользователя, которому хотите отправить сообщение.")
    await state.set_state(AdminPersonalMessageStates.WAITING_FOR_USER_ID)


@router.message(AdminPersonalMessageStates.WAITING_FOR_USER_ID)
async def process_user_id(message: types.Message, state: FSMContext):
    try:
        user_id = int(message.text)
        await state.update_data(user_id=user_id)
        await message.answer(
            "Теперь введите сообщение для пользователя. Вы можете отправить текст, фото, видео, аудио или документ.")
        await state.set_state(AdminPersonalMessageStates.WAITING_FOR_MESSAGE)
    except ValueError:
        await message.answer("Пожалуйста, введите корректный chat_id (целое число).")


@router.message(AdminPersonalMessageStates.WAITING_FOR_MESSAGE)
async def send_personal_message(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = data['user_id']

    try:
        if message.content_type == ContentType.TEXT:
            await message.bot.send_message(user_id, message.text)
        elif message.content_type == ContentType.PHOTO:
            await message.bot.send_photo(user_id, message.photo[-1].file_id, caption=message.caption)
        elif message.content_type == ContentType.VIDEO:
            await message.bot.send_video(user_id, message.video.file_id, caption=message.caption)
        elif message.content_type == ContentType.AUDIO:
            await message.bot.send_audio(user_id, message.audio.file_id, caption=message.caption)
        elif message.content_type == ContentType.DOCUMENT:
            await message.bot.send_document(user_id, message.document.file_id, caption=message.caption)

        await message.answer(f"Сообщение успешно отправлено пользователю с chat_id {user_id}.")
    except Exception as e:
        await message.answer(f"Не удалось отправить сообщение пользователю. Ошибка: {e}")

    await state.clear()


@router.message(Command("list_users"))
async def list_users(message: types.Message):
    if not await is_admin(message.from_user.id):
        await message.answer("У вас нет прав для выполнения этой команды.")
        return

    async with db_helper.db_session() as session:
        user_service = UserService(session)
        all_users = await user_service.get_all_users()

    user_list = []
    for user in all_users:
        user_list.append(f"Username: {user.username or 'Не указан'}, Chat ID: {user.chat_id}")

    users_text = "\n".join(user_list)

    if users_text:
        await message.answer(f"Список пользователей:\n\n{users_text}")
    else:
        await message.answer("Список пользователей пуст.")


async def is_admin(user_id: int) -> bool:
    async with db_helper.db_session() as session:
        user_service = UserService(session)
        return await user_service.is_superuser(user_id)
