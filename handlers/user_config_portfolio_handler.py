from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from core import logger
from core.models import db_helper
from handlers import main_keyboard
from handlers.keyboards import coin_management_keyboard
from services import CoinService, CryptoPriceService, UserService

router = Router()


class UserCoinManagementStates(StatesGroup):
    CHOOSING_ACTION = State()
    ADDING_COIN = State()
    SETTING_MIN_RATE = State()
    SETTING_MAX_RATE = State()
    SETTING_GROWTH_PERCENTAGE = State()
    SETTING_DECLINE_PERCENTAGE = State()
    CHOOSING_COIN_TO_EDIT = State()
    EDITING_COIN = State()
    CHOOSING_COIN_TO_DELETE = State()


@router.message(Command("manage_coins"))
async def start_coin_management(message: types.Message, state: FSMContext):
    await message.answer("Выберите действие:", reply_markup=coin_management_keyboard)
    await state.set_state(UserCoinManagementStates.CHOOSING_ACTION)


@router.message(UserCoinManagementStates.CHOOSING_ACTION)
async def process_coin_management_choice(message: types.Message, state: FSMContext):
    if message.text == "Добавить монету":
        await add_coin(message, state)
    elif message.text == "Редактировать монету":
        await choose_coin_to_edit(message, state)
    elif message.text == "Удалить монету":
        await choose_coin_to_delete(message, state)
    elif message.text == "Мои монеты":
        await list_user_coins(message, state)
    elif message.text == "Вернуться в главное меню":
        await state.clear()
        await message.answer("Вы вернулись в главное меню", reply_markup=main_keyboard)
    else:
        await message.answer("Пожалуйста, выберите одно из предложенных действий.")


async def add_coin(message: types.Message, state: FSMContext):
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
                                 "\n\nВведите номер монеты, которую хотите добавить:")
            await state.set_state(UserCoinManagementStates.ADDING_COIN)
        finally:
            await session.close()


@router.message(UserCoinManagementStates.ADDING_COIN)
async def process_coin_addition(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    available_coins = user_data['available_coins']

    try:
        selected_index = int(message.text) - 1
        selected_coin = available_coins[selected_index]
    except (ValueError, IndexError):
        await message.answer("Пожалуйста, введите корректный номер монеты.")
        return

    async for session in db_helper.session_getter():
        try:
            user_service = UserService(session)
            user = await user_service.get_user(message.from_user.id)
            if not user:
                await message.answer("Произошла ошибка: пользователь не найден.",
                                     reply_markup=coin_management_keyboard)
                return

            user_coins = await user_service.get_user_coins(user.chat_id)
            existing_coin = next((coin for coin, _ in user_coins if coin.id == selected_coin.id), None)

            if existing_coin:
                keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="Удалить и добавить заново",
                                                callback_data=f"replace_coin:{selected_coin.id}")],
                    [types.InlineKeyboardButton(text="Отмена", callback_data="cancel_add_coin")]
                ])
                await message.answer(f"Монета {selected_coin.code} уже добавлена. Хотите удалить её и добавить заново?",
                                     reply_markup=keyboard)
                return

            await state.update_data(selected_coin=selected_coin, user_id=user.id)
            await message.answer(f"Введите минимальный курс для {selected_coin.code} (или 'пропустить' / '/empty'):")
            await state.set_state(UserCoinManagementStates.SETTING_MIN_RATE)
        finally:
            await session.close()


@router.callback_query(lambda c: c.data.startswith("replace_coin:"))
async def replace_coin(callback_query: types.CallbackQuery, state: FSMContext):
    coin_id = callback_query.data.split(":")[1]

    async for session in db_helper.session_getter():
        try:
            user_service = UserService(session)
            user = await user_service.get_user(callback_query.from_user.id)
            if not user:
                await callback_query.answer("Произошла ошибка: пользователь не найден.")
                return

            await user_service.remove_coin_from_user(user.id, coin_id)

            coin_service = CoinService(session)
            coin = await coin_service.get_coin_by_id(coin_id)

            if not coin:
                await callback_query.answer("Произошла ошибка: монета не найдена.")
                return

            await state.update_data(selected_coin=coin)
            await callback_query.message.answer(f"Монета {coin.code} удалена. Теперь давайте добавим её заново.")
            await callback_query.message.answer(f"Введите минимальный курс для {coin.code} (или 'пропустить' / '/empty'):")
            await state.set_state(UserCoinManagementStates.SETTING_MIN_RATE)
        finally:
            await session.close()

    await callback_query.answer()


@router.callback_query(lambda c: c.data == "cancel_add_coin")
async def cancel_add_coin(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.answer("Добавление монеты отменено.", reply_markup=coin_management_keyboard)
    await state.set_state(UserCoinManagementStates.CHOOSING_ACTION)
    await callback_query.answer()


@router.message(UserCoinManagementStates.SETTING_MIN_RATE)
async def process_min_rate(message: types.Message, state: FSMContext):
    if message.text.lower() in ['пропустить', '/empty']:
        await state.update_data(min_rate=None)
    else:
        try:
            min_rate = float(message.text)
            await state.update_data(min_rate=min_rate)
        except ValueError:
            await message.answer("Пожалуйста, введите корректное числовое значение, 'пропустить' или '/empty'.")
            return

    await message.answer("Введите максимальный курс (или 'пропустить' / '/empty'):")
    await state.set_state(UserCoinManagementStates.SETTING_MAX_RATE)


@router.message(UserCoinManagementStates.SETTING_MAX_RATE)
async def process_max_rate(message: types.Message, state: FSMContext):
    if message.text.lower() in ['пропустить', '/empty']:
        await state.update_data(max_rate=None)
    else:
        try:
            max_rate = float(message.text)
            await state.update_data(max_rate=max_rate)
        except ValueError:
            await message.answer("Пожалуйста, введите корректное числовое значение, 'пропустить' или '/empty'.")
            return

    await message.answer("Введите процент роста (или 'пропустить' / '/empty'):")
    await state.set_state(UserCoinManagementStates.SETTING_GROWTH_PERCENTAGE)


@router.message(UserCoinManagementStates.SETTING_GROWTH_PERCENTAGE)
async def process_growth_percentage(message: types.Message, state: FSMContext):
    if message.text.lower() in ['пропустить', '/empty']:
        await state.update_data(growth_percentage=None)
    else:
        try:
            growth_percentage = float(message.text)
            await state.update_data(growth_percentage=growth_percentage)
        except ValueError:
            await message.answer("Пожалуйста, введите корректное числовое значение, 'пропустить' или '/empty'.")
            return

    await message.answer("Введите процент падения (или 'пропустить' / '/empty'):")
    await state.set_state(UserCoinManagementStates.SETTING_DECLINE_PERCENTAGE)


@router.message(UserCoinManagementStates.SETTING_DECLINE_PERCENTAGE)
async def process_decline_percentage(message: types.Message, state: FSMContext):
    if message.text.lower() in ['пропустить', '/empty']:
        await state.update_data(decline_percentage=None)
    else:
        try:
            decline_percentage = float(message.text)
            await state.update_data(decline_percentage=decline_percentage)
        except ValueError:
            await message.answer("Пожалуйста, введите корректное числовое значение, 'пропустить' или '/empty'.")
            return

    await save_user_coin(message, state)


async def save_user_coin(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    selected_coin = user_data['selected_coin']
    user_id = user_data['user_id']

    async with db_helper.db_session() as session:
        try:
            user_service = UserService(session)
            price_service = CryptoPriceService()

            current_prices = await price_service.get_crypto_prices([selected_coin.coin_id_for_price_getter])
            saved_rate_to_compare = current_prices.get(selected_coin.coin_id_for_price_getter)

            await user_service.add_coin_to_user(
                user_id,
                selected_coin.id,
                min_rate=user_data.get('min_rate'),
                max_rate=user_data.get('max_rate'),
                rate_percentage_growth=user_data.get('growth_percentage'),
                rate_percentage_declines=user_data.get('decline_percentage'),
                saved_rate_to_compare=saved_rate_to_compare
            )

            await message.answer(f"Монета {selected_coin.code} успешно добавлена!",
                                 reply_markup=coin_management_keyboard)
            await state.set_state(UserCoinManagementStates.CHOOSING_ACTION)
        except Exception as e:
            logger.error(f"Error saving user coin: {e}")
            await message.answer("Произошла ошибка при сохранении монеты. Пожалуйста, попробуйте позже.",
                                 reply_markup=coin_management_keyboard)


@router.message(UserCoinManagementStates.EDITING_COIN)
async def process_new_value(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    selected_coin = user_data['selected_coin']
    editing_param = user_data['editing_param']
    association = user_data['association']

    try:
        new_value = float(message.text)
    except ValueError:
        await message.answer("Пожалуйста, введите корректное числовое значение.")
        return

    async with db_helper.db_session() as session:
        try:
            user_service = UserService(session)
            await user_service.update_user_coin(
                message.from_user.id,
                selected_coin.id,
                association.id,  # Добавляем ID ассоциации
                **{editing_param: new_value}
            )

            await message.answer(f"Параметр {editing_param} для {selected_coin.code} успешно обновлен!",
                                 reply_markup=coin_management_keyboard)
            await state.set_state(UserCoinManagementStates.CHOOSING_ACTION)
        except Exception as e:
            logger.error(f"Error updating user coin: {e}")
            await message.answer("Произошла ошибка при обновлении монеты. Пожалуйста, попробуйте позже.",
                                 reply_markup=coin_management_keyboard)


async def choose_coin_to_edit(message: types.Message, state: FSMContext):
    async for session in db_helper.session_getter():
        try:
            user_service = UserService(session)
            user_coins = await user_service.get_user_coins(message.from_user.id)

            if not user_coins:
                await message.answer("У вас нет добавленных монет.", reply_markup=coin_management_keyboard)
                return

            coin_list = [f"{i + 1}. {coin.code}" for i, (coin, _) in enumerate(user_coins)]
            await state.update_data(user_coins=user_coins)
            await message.answer("Выберите монету для редактирования:\n" + "\n".join(coin_list))
            await state.set_state(UserCoinManagementStates.CHOOSING_COIN_TO_EDIT)
        finally:
            await session.close()


@router.message(UserCoinManagementStates.CHOOSING_COIN_TO_EDIT)
async def process_coin_choice_for_edit(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    user_coins = user_data['user_coins']

    try:
        selected_index = int(message.text) - 1
        selected_coin, association = user_coins[selected_index]
    except (ValueError, IndexError):
        await message.answer("Пожалуйста, введите корректный номер монеты.")
        return

    await state.update_data(selected_coin=selected_coin, association=association)
    await message.answer(f"Редактирование {selected_coin.code}. Выберите параметр для изменения:\n"
                         "1. Минимальный курс\n"
                         "2. Максимальный курс\n"
                         "3. Процент роста\n"
                         "4. Процент падения")
    await state.set_state(UserCoinManagementStates.EDITING_COIN)


@router.message(UserCoinManagementStates.EDITING_COIN)
async def process_edit_parameter(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    selected_coin = user_data['selected_coin']
    association = user_data['association']

    try:
        param = int(message.text)
        if param not in [1, 2, 3, 4]:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, выберите число от 1 до 4.")
        return

    if param == 1:
        await message.answer(f"Текущий минимальный курс: {association.min_rate}\n"
                             f"Введите новый минимальный курс для {selected_coin.code}:")
        await state.update_data(editing_param="min_rate")
    elif param == 2:
        await message.answer(f"Текущий максимальный курс: {association.max_rate}\n"
                             f"Введите новый максимальный курс для {selected_coin.code}:")
        await state.update_data(editing_param="max_rate")
    elif param == 3:
        await message.answer(f"Текущий процент роста: {association.rate_percentage_growth}\n"
                             f"Введите новый процент роста для {selected_coin.code}:")
        await state.update_data(editing_param="rate_percentage_growth")
    elif param == 4:
        await message.answer(f"Текущий процент падения: {association.rate_percentage_declines}\n"
                             f"Введите новый процент падения для {selected_coin.code}:")
        await state.update_data(editing_param="rate_percentage_declines")


async def choose_coin_to_delete(message: types.Message, state: FSMContext):
    async for session in db_helper.session_getter():
        try:
            user_service = UserService(session)
            user_coins = await user_service.get_user_coins(message.from_user.id)

            if not user_coins:
                await message.answer("У вас нет добавленных монет.", reply_markup=coin_management_keyboard)
                return

            coin_list = [f"{i + 1}. {coin.code}" for i, (coin, _) in enumerate(user_coins)]
            await state.update_data(user_coins=user_coins)
            await message.answer("Выберите монету для удаления:\n" + "\n".join(coin_list))
            await state.set_state(UserCoinManagementStates.CHOOSING_COIN_TO_DELETE)
        finally:
            await session.close()


@router.message(UserCoinManagementStates.CHOOSING_COIN_TO_DELETE)
async def process_coin_deletion(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    user_coins = user_data['user_coins']

    try:
        selected_index = int(message.text) - 1
        selected_coin, _ = user_coins[selected_index]
    except (ValueError, IndexError):
        await message.answer("Пожалуйста, введите корректный номер монеты.")
        return

    async for session in db_helper.session_getter():
        try:
            user_service = UserService(session)
            deleted = await user_service.remove_coin_from_user(message.from_user.id, selected_coin.id)

            if deleted:
                await message.answer(f"Монета {selected_coin.code} успешно удалена!",
                                     reply_markup=coin_management_keyboard)
            else:
                await message.answer(f"Не удалось удалить монету {selected_coin.code}. Попробуйте еще раз позже.",
                                     reply_markup=coin_management_keyboard)

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
