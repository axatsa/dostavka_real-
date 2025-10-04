# main.py (полная исправленная версия)
import asyncio
import logging

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage


from database import Database
from states import AdminStates, ShoppingStates, OrderStates, RegistrationStates
from user_handlers import UserHandlers
from admins import AdminHandlers

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токены и настройки
# Add at the top of main.py
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Then use them like this:
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")


async def main():
    # Инициализация бота и диспетчера
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Инициализация базы данных
    db = Database()

    # Инициализация обработчиков
    user_handlers = UserHandlers(bot)
    admin_handlers = AdminHandlers(bot)

    # ===== РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ ПОЛЬЗОВАТЕЛЕЙ =====
    # Команды
    dp.message.register(user_handlers.cmd_start, Command("start"))

    # Регистрация
    dp.message.register(user_handlers.process_phone, RegistrationStates.waiting_for_phone, F.contact)
    dp.message.register(user_handlers.process_name, RegistrationStates.waiting_for_name)

    # Главное меню
    dp.message.register(user_handlers.show_catalog, F.text == "🛒 Каталог")
    dp.message.register(user_handlers.show_cart, F.text == "🛍️ Корзина")

    # Каталог и товары
    dp.callback_query.register(user_handlers.process_category, F.data.startswith("category_"))
    dp.callback_query.register(user_handlers.process_product, F.data.startswith("product_"))

    # Количество товара
    dp.callback_query.register(user_handlers.quantity_minus, F.data == "qty_minus")
    dp.callback_query.register(user_handlers.quantity_plus, F.data == "qty_plus")
    dp.callback_query.register(user_handlers.add_to_cart, F.data == "add_to_cart")
    dp.callback_query.register(user_handlers.continue_shopping, F.data == "continue_shopping")

    # Корзина
    dp.message.register(user_handlers.back_to_catalog, ShoppingStates.viewing_cart, F.text == "🛒 В каталог")
    dp.message.register(user_handlers.start_checkout, ShoppingStates.viewing_cart, F.text == "💳 К оформлению")

    # Оформление заказа
    dp.message.register(user_handlers.process_delivery_date, OrderStates.waiting_for_date)
    dp.message.register(user_handlers.process_delivery_time, OrderStates.waiting_for_time)
    dp.message.register(user_handlers.process_delivery_address, OrderStates.waiting_for_address)
    dp.callback_query.register(user_handlers.confirm_order, F.data == "confirm_order")
    dp.callback_query.register(user_handlers.cancel_order, F.data == "cancel_order")

    # Callback queries для навигации
    dp.callback_query.register(user_handlers.back_to_categories_callback, F.data == "back_to_categories")
    dp.callback_query.register(user_handlers.view_cart_inline, F.data == "view_cart")
    dp.callback_query.register(user_handlers.start_checkout_inline, F.data == "start_checkout_inline")
    dp.callback_query.register(user_handlers.clear_cart, F.data == "clear_cart")

    # ===== РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ АДМИНА =====
    # Команда админа - ВАЖНО: регистрируем ДО общего обработчика сообщений
    @dp.message(Command("admin"))
    async def cmd_admin(message: types.Message, state: FSMContext):
        await admin_handlers.cmd_admin(message, state)

    # Обработчики состояний админа
    dp.message.register(admin_handlers.check_admin_password, AdminStates.waiting_for_password)
    dp.message.register(admin_handlers.start_add_product, AdminStates.admin_menu, F.text == "➕ Добавить товар")
    dp.message.register(admin_handlers.show_all_products, AdminStates.admin_menu, F.text == "📋 Список товаров")
    dp.message.register(admin_handlers.exit_admin, AdminStates.admin_menu, F.text == "🔙 Выйти из админки")
    dp.message.register(admin_handlers.start_edit_product, AdminStates.admin_menu, F.text == "✏️ Изменить товар")
    dp.message.register(admin_handlers.start_delete_product, AdminStates.admin_menu, F.text == "🗑 Удалить товар")
    dp.message.register(admin_handlers.process_product_name, AdminStates.adding_product_name)
    dp.message.register(admin_handlers.process_product_price, AdminStates.adding_product_price)
    dp.message.register(admin_handlers.process_product_quantity, AdminStates.adding_product_quantity)
    dp.message.register(admin_handlers.process_product_category, AdminStates.adding_product_category)
    dp.message.register(admin_handlers.skip_photo, AdminStates.adding_product_photo, F.text == "пропустить")
    dp.message.register(admin_handlers.process_product_photo, AdminStates.adding_product_photo, F.photo)
    dp.message.register(admin_handlers.process_edit_product, AdminStates.editing_product)
    dp.message.register(admin_handlers.process_delete_product, AdminStates.deleting_product)

    # Редактирование товара
    dp.message.register(admin_handlers.process_edit_field_selection, AdminStates.editing_product_select_field)
    dp.message.register(admin_handlers.process_edit_product_name, AdminStates.editing_product_name)
    dp.message.register(admin_handlers.process_edit_product_price, AdminStates.editing_product_price)
    dp.message.register(admin_handlers.process_edit_product_quantity, AdminStates.editing_product_quantity)
    dp.message.register(admin_handlers.process_edit_product_category, AdminStates.editing_product_category)
    dp.message.register(admin_handlers.process_edit_product_photo, AdminStates.editing_product_photo,
                        F.text == "пропустить")
    dp.message.register(admin_handlers.process_edit_product_photo, AdminStates.editing_product_photo, F.photo)

    # REGOS orders management handlers
    @dp.message(lambda message: message.text == "📦 Управление заказами REGOS")
    async def regos_orders_menu(message: types.Message, state: FSMContext):
        await admin_handlers.show_regos_orders_menu(message)

    @dp.message(lambda message: message.text == "🔄 Синхронизировать заказы")
    async def sync_regos_orders(message: types.Message):
        await admin_handlers.sync_regos_orders(message)

    @dp.message(lambda message: message.text == "📋 Проверить статус заказа")
    async def check_regos_order_status(message: types.Message, state: FSMContext):
        await admin_handlers.show_regos_order_status(message, state)

    @dp.message(AdminStates.regos_check_order_status)
    async def process_check_regos_order_status(message: types.Message, state: FSMContext):
        await admin_handlers.process_regos_order_status(message, state)

    @dp.message(lambda message: message.text == "✏️ Обновить статус заказа")
    async def update_regos_order_status(message: types.Message, state: FSMContext):
        await admin_handlers.update_regos_order_status(message, state)

    @dp.message(AdminStates.regos_update_order_status)
    async def process_update_regos_status(message: types.Message, state: FSMContext):
        await admin_handlers.process_update_regos_status(message, state)

    @dp.message(lambda message: message.text in ["🔙 Назад в админ-панель", "🔙 Назад к заказам"])
    async def back_to_admin_menu(message: types.Message, state: FSMContext):
        await admin_handlers.cmd_admin(message, state)

    # Неизвестные сообщения (регистрируется ПОСЛЕДНИМ)
    dp.message.register(user_handlers.unknown_message)

    # Запуск бота
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())