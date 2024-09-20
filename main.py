import asyncio
import logging
from uuid import UUID

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv
import os

from core.models import http_helper, db_helper
from services import get_random_cat_image, UserService, CoinService

logging.basicConfig(level=logging.INFO)
load_dotenv(".env")

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="/meow"), KeyboardButton(text="/get_prices"), ]],
    resize_keyboard=True
)


@dp.message(CommandStart())
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
            logging.error(f"Database error: {e}")
            await message.answer("Извините, произошла ошибка. Пожалуйста, попробуйте позже.",
                                 reply_markup=main_keyboard)
        finally:
            await session.close()


@dp.message(Command("meow"))
async def meow_handler(message: types.Message):
    max_retry = 3
    for retry in range(max_retry):
        try:
            cat_image = await get_random_cat_image()
            await message.answer_photo(cat_image, reply_markup=main_keyboard, caption="Мяу Мяу :3")
            return
        except Exception as e:
            logging.error(f"Failed to send cat image (attempt {retry + 1}/{max_retry}): {e}")
            if retry < max_retry - 1:
                await asyncio.sleep(1)

    await message.answer("Извините, я не смог отправить изображение! Попробуйте еще раз позже.",
                         reply_markup=main_keyboard)


@dp.message(Command("get_prices"))
async def price_handler(message: types.Message):
    await asyncio.sleep(2)

    await message.answer(f"ЭТА КОМАНДА НЕ ДОСТРОЕНА", reply_markup=main_keyboard)


@dp.message(Command("list_coins"))
async def list_coins(message: types.Message):
    chat_id = message.chat.id

    async for session in db_helper.session_getter():
        try:
            user_service = UserService(session)
            if not await user_service.is_superuser(chat_id):
                await message.answer("У вас нет прав для выполнения этой команды.", reply_markup=main_keyboard)
                return

            coin_service = CoinService(session)
            all_coins = await coin_service.get_all_coins()

            if not all_coins:
                await message.answer("Список монет пуст.", reply_markup=main_keyboard)
                return

            coins_text = "\n\n".join([
                f"Код: {coin.code}\n"
                f"ID для цены: {coin.coin_id_for_price_getter or 'Не указан'}\n"
                f"ID: {coin.id}\n"
                f"Название: {coin.name or 'Не указано'}"
                for coin in all_coins
            ])

            await message.answer(f"Список всех монет:\n\n{coins_text}", reply_markup=main_keyboard)

        except Exception as e:
            logging.error(f"Failed to get all coins: {e}")
            await message.answer("Произошла ошибка при получении списка монет.", reply_markup=main_keyboard)
        finally:
            await session.close()


class AddCoinStates(StatesGroup):
    WAITING_FOR_CODE = State()
    WAITING_FOR_NAME = State()
    WAITING_FOR_PRICE_ID = State()
    CONFIRM_ADD_MORE = State()


@dp.message(Command("add_coin"))
async def start_add_coin(message: types.Message, state: FSMContext):
    chat_id = message.chat.id

    async for session in db_helper.session_getter():
        try:
            user_service = UserService(session)
            if not await user_service.is_superuser(chat_id):
                await message.answer("У вас нет прав для выполнения этой команды.", reply_markup=main_keyboard)
                return
        finally:
            await session.close()

    await state.set_state(AddCoinStates.WAITING_FOR_CODE)
    await message.answer("Введите код монеты:", reply_markup=types.ReplyKeyboardRemove())


@dp.message(AddCoinStates.WAITING_FOR_CODE)
async def process_code(message: types.Message, state: FSMContext):
    code = message.text.upper()
    await state.update_data(code=code)
    await state.set_state(AddCoinStates.WAITING_FOR_NAME)
    await message.answer("Введите название монеты (или /empty для пропуска):")


@dp.message(AddCoinStates.WAITING_FOR_NAME)
async def process_name(message: types.Message, state: FSMContext):
    name = None if message.text == "/empty" else message.text
    await state.update_data(name=name)
    await state.set_state(AddCoinStates.WAITING_FOR_PRICE_ID)
    await message.answer("Введите ID для получения цены (или /empty для пропуска):")


@dp.message(AddCoinStates.WAITING_FOR_PRICE_ID)
async def process_price_id(message: types.Message, state: FSMContext):
    price_id = None if message.text == "/empty" else message.text
    await state.update_data(coin_id_for_price_getter=price_id)

    data = await state.get_data()

    async for session in db_helper.session_getter():
        try:
            coin_service = CoinService(session)
            new_coin = await coin_service.add_coin(data['code'], data['name'], data['coin_id_for_price_getter'])

            confirm_keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="Добавить еще"), KeyboardButton(text="Показать все")]
                ],
                resize_keyboard=True
            )

            await state.set_state(AddCoinStates.CONFIRM_ADD_MORE)
            await message.answer(
                f"Монета успешно добавлена: {new_coin}\nХотите добавить еще или показать все добавленные?",
                reply_markup=confirm_keyboard)
        except Exception as e:
            logging.error(f"Failed to add coin: {e}")
            await message.answer("Произошла ошибка при добавлении монеты. Попробуйте позже.",
                                 reply_markup=main_keyboard)
            await state.clear()
        finally:
            await session.close()


@dp.message(AddCoinStates.CONFIRM_ADD_MORE)
async def confirm_add_more(message: types.Message, state: FSMContext):
    if message.text == "Добавить еще":
        await state.set_state(AddCoinStates.WAITING_FOR_CODE)
        await message.answer("Введите код новой монеты:", reply_markup=types.ReplyKeyboardRemove())
    elif message.text == "Показать все":
        async for session in db_helper.session_getter():
            try:
                coin_service = CoinService(session)

                all_coins = await coin_service.get_all_coins()

                coins_text = "\n".join(
                    [f"{coin.code} - {coin.coin_id_for_price_getter or 'Не указан'}" for coin in all_coins])

                if coins_text:
                    await message.answer(f"Все добавленные монеты (код - код для источника):\n\n{coins_text}",
                                         reply_markup=main_keyboard)
                else:
                    await message.answer("Список монет пуст.", reply_markup=main_keyboard)
            except Exception as e:
                logging.error(f"Failed to get all coins: {e}")
                await message.answer("Произошла ошибка при получении списка монет.", reply_markup=main_keyboard)
            finally:
                await session.close()
        await state.clear()
    else:
        await message.answer("Пожалуйста, выберите одну из предложенных опций.", reply_markup=main_keyboard)


class EditCoinStates(StatesGroup):
    CHOOSING_COIN = State()
    EDITING_CODE = State()
    EDITING_NAME = State()
    EDITING_PRICE_ID = State()
    CONFIRM_EDIT = State()


@dp.message(Command("edit_coin"))
async def start_edit_coins(message: types.Message, state: FSMContext):
    chat_id = message.chat.id

    async for session in db_helper.session_getter():
        try:
            user_service = UserService(session)
            if not await user_service.is_superuser(chat_id):
                await message.answer("У вас нет прав для выполнения этой команды.", reply_markup=main_keyboard)
                return

            coin_service = CoinService(session)
            all_coins = await coin_service.get_all_coins()

            if not all_coins:
                await message.answer("Список монет пуст. Нечего редактировать.", reply_markup=main_keyboard)
                return

            coins_text = "\n".join(
                [f"{coin.id}: {coin.code} - {coin.coin_id_for_price_getter or 'Не указан'}" for coin in all_coins])
            await message.answer(
                f"Список всех монет (ID: код - код для источника):\n\n{coins_text}\n\nВведите ID монеты, которую хотите отредактировать:")

            await state.set_state(EditCoinStates.CHOOSING_COIN)
        except Exception as e:
            logging.error(f"Failed to get coins for editing: {e}")
            await message.answer("Произошла ошибка при получении списка монет.", reply_markup=main_keyboard)
        finally:
            await session.close()


@dp.message(EditCoinStates.CHOOSING_COIN)
async def process_coin_choice(message: types.Message, state: FSMContext):
    try:
        coin_id = UUID(message.text)
        await state.update_data(coin_id=str(coin_id))
        await state.set_state(EditCoinStates.EDITING_CODE)
        await message.answer("Введите новый код монеты (или /skip для пропуска):")
    except ValueError:
        await message.answer("Пожалуйста, введите корректный ID монеты.")


@dp.message(EditCoinStates.EDITING_CODE)
async def process_edit_code(message: types.Message, state: FSMContext):
    if message.text != "/skip":
        await state.update_data(new_code=message.text.upper())
    await state.set_state(EditCoinStates.EDITING_NAME)
    await message.answer("Введите новое название монеты (или /skip для пропуска):")


@dp.message(EditCoinStates.EDITING_NAME)
async def process_edit_name(message: types.Message, state: FSMContext):
    if message.text != "/skip":
        await state.update_data(new_name=message.text)
    await state.set_state(EditCoinStates.EDITING_PRICE_ID)
    await message.answer("Введите новый ID для получения цены (или /skip для пропуска):")


@dp.message(EditCoinStates.EDITING_PRICE_ID)
async def process_edit_price_id(message: types.Message, state: FSMContext):
    if message.text != "/skip":
        await state.update_data(new_coin_id_for_price_getter=message.text)

    data = await state.get_data()
    coin_id = data['coin_id']
    new_code = data.get('new_code')
    new_name = data.get('new_name')
    new_coin_id_for_price_getter = data.get('new_coin_id_for_price_getter')

    async for session in db_helper.session_getter():
        try:
            coin_service = CoinService(session)
            updated_coin = await coin_service.update_coin(coin_id, new_code, new_name, new_coin_id_for_price_getter)

            if updated_coin:
                await message.answer(f"Монета успешно обновлена: {updated_coin}", reply_markup=main_keyboard)
            else:
                await message.answer("Монета с указанным ID не найдена.", reply_markup=main_keyboard)
        except Exception as e:
            logging.error(f"Failed to update coin: {e}")
            await message.answer("Произошла ошибка при обновлении монеты.", reply_markup=main_keyboard)
        finally:
            await session.close()

    await state.clear()


class DeleteCoinStates(StatesGroup):
    CHOOSING_COIN = State()
    CONFIRMING_DELETE = State()


@dp.message(Command("delete_coin"))
async def start_delete_coin(message: types.Message, state: FSMContext):
    chat_id = message.chat.id

    async for session in db_helper.session_getter():
        try:
            user_service = UserService(session)
            if not await user_service.is_superuser(chat_id):
                await message.answer("У вас нет прав для выполнения этой команды.", reply_markup=main_keyboard)
                return

            coin_service = CoinService(session)
            all_coins = await coin_service.get_all_coins()

            if not all_coins:
                await message.answer("Список монет пуст. Нечего удалять.", reply_markup=main_keyboard)
                return

            coins_text = "\n".join(
                [f"{coin.id}: {coin.code} - {coin.coin_id_for_price_getter or 'Не указан'}" for coin in all_coins])
            await message.answer(
                f"Список всех монет (ID: код - код для источника):\n\n{coins_text}\n\nВведите ID монеты, которую хотите удалить:")

            await state.set_state(DeleteCoinStates.CHOOSING_COIN)
        except Exception as e:
            logging.error(f"Failed to get coins for deletion: {e}")
            await message.answer("Произошла ошибка при получении списка монет.", reply_markup=main_keyboard)
        finally:
            await session.close()


@dp.message(DeleteCoinStates.CHOOSING_COIN)
async def process_coin_choice_for_delete(message: types.Message, state: FSMContext):
    try:
        coin_id = UUID(message.text)
        await state.update_data(coin_id=str(coin_id))

        async for session in db_helper.session_getter():
            try:
                coin_service = CoinService(session)
                coin = await coin_service.get_coin_by_id(coin_id)
                if coin:
                    await message.answer(f"Вы уверены, что хотите удалить монету {coin.code}? (Да/Нет)")
                    await state.set_state(DeleteCoinStates.CONFIRMING_DELETE)
                else:
                    await message.answer("Монета с указанным ID не найдена.", reply_markup=main_keyboard)
                    await state.clear()
            except Exception as e:
                logging.error(f"Failed to get coin for deletion: {e}")
                await message.answer("Произошла ошибка при получении информации о монете.", reply_markup=main_keyboard)
                await state.clear()
            finally:
                await session.close()
    except ValueError:
        await message.answer("Пожалуйста, введите корректный ID монеты.")


@dp.message(DeleteCoinStates.CONFIRMING_DELETE)
async def confirm_coin_deletion(message: types.Message, state: FSMContext):
    if message.text.lower() == "да":
        data = await state.get_data()
        coin_id = data['coin_id']

        async for session in db_helper.session_getter():
            try:
                coin_service = CoinService(session)
                deleted = await coin_service.delete_coin(coin_id)
                if deleted:
                    await message.answer("Монета успешно удалена.", reply_markup=main_keyboard)
                else:
                    await message.answer("Не удалось удалить монету. Возможно, она уже была удалена.",
                                         reply_markup=main_keyboard)
            except Exception as e:
                logging.error(f"Failed to delete coin: {e}")
                await message.answer("Произошла ошибка при удалении монеты.", reply_markup=main_keyboard)
            finally:
                await session.close()
    else:
        await message.answer("Удаление монеты отменено.", reply_markup=main_keyboard)

    await state.clear()


async def main():
    logging.info("Starting the bot")
    await http_helper.start()
    # price_updates_task = asyncio.create_task(send_price_updates())
    try:
        await dp.start_polling(bot)
    finally:
        # price_updates_task.cancel()
        await http_helper.dispose_all_clients()


if __name__ == "__main__":
    asyncio.run(main())
