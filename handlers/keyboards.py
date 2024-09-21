from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="/start"), KeyboardButton(text="/meow")],
              [KeyboardButton(text="/manage_coins"), KeyboardButton(text="/portfolio_prices")],
              [KeyboardButton(text="/all_prices")]],
    # KeyboardButton(text="/get_prices")
    resize_keyboard=True
)

admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="/start"), KeyboardButton(text="/admin_help"), ],
              [KeyboardButton(text="/list_coins"), KeyboardButton(text="/add_coin"), ],
              [KeyboardButton(text="/edit_coin"), KeyboardButton(text="/delete_coin"),],
              [KeyboardButton(text="/broadcast"), KeyboardButton(text="/send_personal")],
              [KeyboardButton(text="/list_users")],
              ],
    resize_keyboard=True
)

coin_management_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="/start")],
        [KeyboardButton(text="Добавить монету")],
        [KeyboardButton(text="Редактировать монету")],
        [KeyboardButton(text="Удалить монету")],
        [KeyboardButton(text="Мои монеты")],
        [KeyboardButton(text="Вернуться в главное меню")]
    ],
    resize_keyboard=True
)
