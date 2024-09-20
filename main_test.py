import asyncio
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv
import os

from core import logger
from core.models import http_helper, db_helper
from services import get_random_cat_image, UserService, CoinService, CryptoPriceService

logging.basicConfig(level=logging.INFO)
load_dotenv(".env")

BOT_TOKEN = os.getenv("BOT_TOKEN")

dp = Dispatcher()

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="/meow"), KeyboardButton(text="/get_prices"), KeyboardButton(text="/manage_coins")]],
    resize_keyboard=True
)


# User Coin Management States
class UserCoinManagementStates(StatesGroup):
    CHOOSING_ACTION = State()
    ADDING_COINS = State()
    SETTING_PARAMETERS = State()
    SETTING_MIN_RATE = State()
    SETTING_MAX_RATE = State()
    SETTING_GROWTH_PERCENTAGE = State()
    SETTING_DECLINE_PERCENTAGE = State()
    EDITING_COINS = State()
    DELETING_COINS = State()


coin_management_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Добавить монеты")],
        [KeyboardButton(text="Посмотреть мои монеты")],
        [KeyboardButton(text="Редактировать монеты")],
        [KeyboardButton(text="Удалить монеты")],
        [KeyboardButton(text="Вернуться в главное меню")]
    ],
    resize_keyboard=True
)


# Existing handlers
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

    await message.answer("Извините, я не смог отправить изображение! Попробуйте еще раз позже.",
                         reply_markup=main_keyboard)


@dp.message(Command("get_prices"))
async def price_handler(message: types.Message):
    await asyncio.sleep(2)
    await message.answer(f"ЭТА КОМАНДА НЕ ДОСТРОЕНА", reply_markup=main_keyboard)


# User Coin Management handlers
@dp.message(Command("manage_coins"))
async def start_coin_management(message: types.Message, state: FSMContext):
    await message.answer("Выберите действие:", reply_markup=coin_management_keyboard)
    await state.set_state(UserCoinManagementStates.CHOOSING_ACTION)


@dp.message(UserCoinManagementStates.CHOOSING_ACTION)
async def process_coin_management_choice(message: types.Message, state: FSMContext):
    if message.text == "Добавить монеты":
        await add_coins(message, state)
    elif message.text == "Посмотреть мои монеты":
        await list_user_coins(message, state)
    elif message.text == "Редактировать монеты":
        await edit_coins(message, state)
    elif message.text == "Удалить монеты":
        await delete_coins(message, state)
    elif message.text == "Вернуться в главное меню":
        await state.clear()
        await message.answer("Вы вернулись в главное меню", reply_markup=main_keyboard)
    else:
        await message.answer("Пожалуйста, выберите одно из предложенных действий.")


async def add_coins(message: types.Message, state: FSMContext):
    async for session in db_helper.session_getter():
        try:
            coin_service = CoinService(session)
            all_coins = await coin_service.get_all_coins()

            if not all_coins:
                await message.answer("В системе нет доступных монет.", reply_markup=coin_management_keyboard)
                return

            price_service = CryptoPriceService()
            coin_ids = [coin.coin_id_for_price_getter for coin in all_coins if coin.coin_id_for_price_getter]
            current_prices = await price_service.get_crypto_prices(coin_ids)

            sorted_coins = sorted(all_coins, key=lambda c: c.code)
            coin_list = []
            for i, coin in enumerate(sorted_coins, 1):
                price = current_prices.get(coin.coin_id_for_price_getter, "N/A")
                coin_list.append(f"{i}. {coin.code} - Текущий курс: {price}")

            await state.update_data(available_coins=sorted_coins)
            await message.answer("Доступные монеты:\n" + "\n".join(coin_list) +
                                 "\n\nВведите номера монет, которые хотите добавить (через запятую):")
            await state.set_state(UserCoinManagementStates.ADDING_COINS)
        finally:
            await session.close()


@dp.message(UserCoinManagementStates.ADDING_COINS)
async def process_coin_addition(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    available_coins = user_data['available_coins']

    try:
        selected_indices = [int(i.strip()) - 1 for i in message.text.split(',')]
        selected_coins = [available_coins[i] for i in selected_indices]
    except (ValueError, IndexError):
        await message.answer("Пожалуйста, введите корректные номера монет.")
        return

    await state.update_data(selected_coins=selected_coins)
    await message.answer("Выберите параметры для установки (через запятую):\n"
                         "1. Минимальный курс\n"
                         "2. Максимальный курс\n"
                         "3. Процент роста\n"
                         "4. Процент падения\n"
                         "Или введите 'пропустить' для пропуска настройки параметров.")
    await state.set_state(UserCoinManagementStates.SETTING_PARAMETERS)


@dp.message(UserCoinManagementStates.SETTING_PARAMETERS)
async def process_parameter_setting(message: types.Message, state: FSMContext):
    if message.text.lower() == 'пропустить':
        await save_user_coins(message, state)
        return

    try:
        params = [int(i.strip()) for i in message.text.split(',')]
        if not all(1 <= p <= 4 for p in params):
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите корректные номера параметров.")
        return

    user_data = await state.get_data()
    selected_coins = user_data['selected_coins']
    await state.update_data(params=params, current_coin_index=0)

    await process_next_parameter(message, state)


async def process_next_parameter(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    params = user_data['params']
    current_coin_index = user_data['current_coin_index']
    selected_coins = user_data['selected_coins']

    if current_coin_index >= len(selected_coins):
        await save_user_coins(message, state)
        return

    current_coin = selected_coins[current_coin_index]
    current_param = params[0] if params else None

    if current_param == 1:
        await message.answer(f"Введите минимальный курс для {current_coin.code}:")
        await state.set_state(UserCoinManagementStates.SETTING_MIN_RATE)
    elif current_param == 2:
        await message.answer(f"Введите максимальный курс для {current_coin.code}:")
        await state.set_state(UserCoinManagementStates.SETTING_MAX_RATE)
    elif current_param == 3:
        await message.answer(f"Введите процент роста для {current_coin.code}:")
        await state.set_state(UserCoinManagementStates.SETTING_GROWTH_PERCENTAGE)
    elif current_param == 4:
        await message.answer(f"Введите процент падения для {current_coin.code}:")
        await state.set_state(UserCoinManagementStates.SETTING_DECLINE_PERCENTAGE)
    else:
        await state.update_data(current_coin_index=current_coin_index + 1)
        await process_next_parameter(message, state)


@dp.message(UserCoinManagementStates.SETTING_MIN_RATE)
@dp.message(UserCoinManagementStates.SETTING_MAX_RATE)
@dp.message(UserCoinManagementStates.SETTING_GROWTH_PERCENTAGE)
@dp.message(UserCoinManagementStates.SETTING_DECLINE_PERCENTAGE)
async def process_parameter_value(message: types.Message, state: FSMContext):
    try:
        value = float(message.text)
    except ValueError:
        await message.answer("Пожалуйста, введите корректное числовое значение.")
        return

    user_data = await state.get_data()
    current_coin_index = user_data['current_coin_index']
    selected_coins = user_data['selected_coins']
    current_coin = selected_coins[current_coin_index]
    current_state = await state.get_state()

    if current_state == UserCoinManagementStates.SETTING_MIN_RATE:
        current_coin.min_rate = value
    elif current_state == UserCoinManagementStates.SETTING_MAX_RATE:
        current_coin.max_rate = value
    elif current_state == UserCoinManagementStates.SETTING_GROWTH_PERCENTAGE:
        current_coin.rate_percentage_growth = value
    elif current_state == UserCoinManagementStates.SETTING_DECLINE_PERCENTAGE:
        current_coin.rate_percentage_declines = value

    params = user_data['params']
    params.pop(0)
    await state.update_data(params=params)

    if not params:
        if current_state in [UserCoinManagementStates.SETTING_GROWTH_PERCENTAGE,
                             UserCoinManagementStates.SETTING_DECLINE_PERCENTAGE]:
            price_service = CryptoPriceService()
            current_price = await price_service.get_crypto_prices([current_coin.coin_id_for_price_getter])
            current_coin.saved_rate_to_compare = current_price.get(current_coin.coin_id_for_price_getter)

        await state.update_data(current_coin_index=current_coin_index + 1)

    await process_next_parameter(message, state)


async def save_user_coins(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    selected_coins = user_data['selected_coins']

    async for session in db_helper.session_getter():
        try:
            user_service = UserService(session)
            user = await user_service.get_user(message.from_user.id)

            for coin in selected_coins:
                await user_service.add_coin_to_user(user.id, coin.id,
                                                    min_rate=getattr(coin, 'min_rate', None),
                                                    max_rate=getattr(coin, 'max_rate', None),
                                                    rate_percentage_growth=getattr(coin, 'rate_percentage_growth',
                                                                                   None),
                                                    rate_percentage_declines=getattr(coin, 'rate_percentage_declines',
                                                                                     None),
                                                    saved_rate_to_compare=getattr(coin, 'saved_rate_to_compare', None))

            await message.answer("Монеты успешно добавлены!", reply_markup=coin_management_keyboard)
            await state.set_state(UserCoinManagementStates.CHOOSING_ACTION)
        finally:
            await session.close()


async def list_user_coins(message: types.Message, state: FSMContext):
    async for session in db_helper.session_getter():
        try:
            user_service = UserService(session)
            user_coins = await user_service.get_user_coins(message.from_user.id)

            if not user_coins:
                await message.answer("У вас нет добавленных монет.", reply_markup=coin_management_keyboard)
                return

            price_service = CryptoPriceService()
            coin_ids = [coin.coin_id_for_price_getter for coin, _ in user_coins if coin.coin_id_for_price_getter]
            current_prices = await price_service.get_crypto_prices(coin_ids)

            coin_list = []
            for i, (coin, association) in enumerate(user_coins, 1):
                price = current_prices.get(coin.coin_id_for_price_getter, "N/A")
                coin_info = f"{i}. {coin.code} - Текущий курс: {price}\n"
                coin_info += f"   Мин. курс: {association.min_rate}\n"
                coin_info += f"   Макс. курс: {association.max_rate}\n"
                coin_info += f"   % роста: {association.rate_percentage_growth}\n"
                coin_info += f"   % падения: {association.rate_percentage_declines}\n"
                coin_info += f"   Сохраненный курс: {association.saved_rate_to_compare}"
                coin_list.append(coin_info)

            await message.answer("Ваши монеты:\n" + "\n\n".join(coin_list), reply_markup=coin_management_keyboard)
        finally:
            await session.close()

    async def edit_coins(message: types.Message, state: FSMContext):
        await list_user_coins(message, state)
        await message.answer("Введите номер монеты, которую хотите отредактировать:")
        await state.set_state(UserCoinManagementStates.EDITING_COINS)

    @dp.message(UserCoinManagementStates.EDITING_COINS)
    async def process_coin_edit(message: types.Message, state: FSMContext):
        try:
            coin_index = int(message.text) - 1
            selected_coin, association = None, None
            async for session in db_helper.session_getter():
                try:
                    user_service = UserService(session)
                    user_coins = await user_service.get_user_coins(message.from_user.id)
                    selected_coin, association = user_coins[coin_index]
                except Exception as e:
                    logger.exception(e)
                finally:
                    await session.close()

            await state.update_data(selected_coin=selected_coin, association=association)
            await message.answer(
                f"Редактирование {selected_coin.code}. Выберите параметры для изменения (через запятую):\n"
                "1. Минимальный курс\n"
                "2. Максимальный курс\n"
                "3. Процент роста\n"
                "4. Процент падения")
            await state.set_state(UserCoinManagementStates.SETTING_PARAMETERS)
        except (ValueError, IndexError):
            await message.answer("Пожалуйста, введите корректный номер монеты.")

    # async def delete_coins(message: types.Message, state: FSMContext):
    #     await list_user_coins(message, state)
    #     await message.answer("Введите номера монет, которые хотите удалить (через запятую):")
    #     await state.set_state(UserCoinManagementStates.DELETING_COINS)

    @dp.message(UserCoinManagementStates.DELETING_COINS)
    async def process_coin_deletion(message: types.Message, state: FSMContext):
        try:
            coin_indices = [int(i.strip()) - 1 for i in message.text.split(',')]
            async for session in db_helper.session_getter():
                try:
                    user_service = UserService(session)
                    user_coins = await user_service.get_user_coins(message.from_user.id)
                    coins_to_delete = [user_coins[i][0] for i in coin_indices]

                    for coin in coins_to_delete:
                        await user_service.remove_coin_from_user(message.from_user.id, coin.id)

                    await message.answer("Выбранные монеты успешно удалены.", reply_markup=coin_management_keyboard)
                    await state.set_state(UserCoinManagementStates.CHOOSING_ACTION)
                finally:
                    await session.close()
        except (ValueError, IndexError):
            await message.answer("Пожалуйста, введите корректные номера монет.")

    # Existing admin commands
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


# Main function
async def main():
    logging.info("Starting the bot")
    bot = Bot(token=BOT_TOKEN)

    await http_helper.start()

    try:
        await dp.start_polling(bot)
    finally:
        await http_helper.dispose_all_clients()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())


async def delete_coins(message: types.Message, state: FSMContext):
    await list_user_coins(message, state)
    await message.answer("Введите номера монет, которые хотите удалить (через запятую):")
    await state.set_state(UserCoinManagementStates.DELETING_COINS)


async def process_coin_deletion(message: types.Message, state: FSMContext):
    try:
        coin_indices = [int(i.strip()) - 1 for i in message.text.split(',')]
        async for session in db_helper.session_getter():
            try:
                user_service = UserService(session)
                user_coins = await user_service.get_user_coins(message.from_user.id)
                coins_to_delete = [user_coins[i][0] for i in coin_indices]

                for coin in coins_to_delete:
                    await user_service.remove_coin_from_user(message.from_user.id, coin.id)

                await message.answer("Выбранные монеты успешно удалены.", reply_markup=coin_management_keyboard)
                await state.set_state(UserCoinManagementStates.CHOOSING_ACTION)
            finally:
                await session.close()
    except (ValueError, IndexError):
        await message.answer("Пожалуйста, введите корректные номера монет.")


async def edit_coins(message: types.Message, state: FSMContext):
    await list_user_coins(message, state)
    await message.answer("Введите номер монеты, которую хотите отредактировать:")
    await state.set_state(UserCoinManagementStates.EDITING_COINS)
