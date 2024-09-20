import asyncio
import logging

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
    keyboard=[[KeyboardButton(text="/meow"),  KeyboardButton(text="/get_prices"), ]],
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
                await message.answer(f"Привет, {username}! Я бот для отслеживания цен криптовалют. И я люблю котиков :3", reply_markup=main_keyboard)
            else:
                await message.answer(f"С возвращением, {username}! Посмотрим цены или котиков?", reply_markup=main_keyboard)
        except Exception as e:
            logging.error(f"Database error: {e}")
            await message.answer("Извините, произошла ошибка. Пожалуйста, попробуйте позже.", reply_markup=main_keyboard)
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

    await message.answer("Извините, я не смог отправить изображение! Попробуйте еще раз позже.", reply_markup=main_keyboard)


@dp.message(Command("get_prices"))
async def price_handler(message: types.Message):

    await asyncio.sleep(2)

    await message.answer(f"ЭТА КОМАНДА НЕ ДОСТРОЕНА", reply_markup=main_keyboard)


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
