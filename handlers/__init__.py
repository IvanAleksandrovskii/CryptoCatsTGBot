__all__ = [
    "router",
    "main_keyboard",
    "admin_keyboard",
]
from .keyboards import main_keyboard, admin_keyboard

from aiogram import Router

from .on_start_handler import router as on_start_router
from .meow_handler import router as meow_router
from .admin_coin_handlers import router as admin_coin_router
from .user_config_portfolio_handler import router as user_config_portfolio_router

router = Router()
router.include_router(on_start_router)
router.include_router(meow_router)
router.include_router(admin_coin_router)
router.include_router(user_config_portfolio_router)
