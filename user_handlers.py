import os
import logging
from aiogram import Bot, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from datetime import datetime, time

from database import Database
from keyboards import *
from states import RegistrationStates, ShoppingStates, OrderStates

logger = logging.getLogger(__name__)

db = Database()

ADMIN_GROUP_ID = -1003161488318


class UserHandlers:
    def __init__(self, bot: Bot):
        self.bot = bot

    # ===== ОБРАБОТЧИКИ КОМАНД =====
    async def cmd_start(self, message: types.Message, state: FSMContext):
        user_id = message.from_user.id
        user = db.get_user(user_id)

        if user:
            await message.answer(
                f"С возвращением, {user['name']}! 👋",
                reply_markup=get_main_menu_keyboard()
            )
        else:
            await message.answer(
                "Добро пожаловать в бот доставки продуктов! 🛒\n\n"
                "Для начала работы необходимо пройти простую регистрацию.\n"
                "Пожалуйста, поделитесь своим номером телефона:",
                reply_markup=get_phone_keyboard()
            )
            await state.set_state(RegistrationStates.waiting_for_phone)

    def is_valid_date(self, date_str: str) -> bool:
        try:
            input_date = datetime.strptime(date_str, "%d.%m.%Y").date()
            today = datetime.now().date()
            return input_date >= today
        except ValueError:
            return False

    def is_valid_time(self, time_str: str) -> bool:
        try:
            datetime.strptime(time_str, "%H:%M")
            return True
        except ValueError:
            return False

    def is_valid_datetime_combination(self, date_str: str, time_str: str) -> bool:
        try:
            input_datetime = datetime.strptime(
                f"{date_str} {time_str}",
                "%d.%m.%Y %H:%M"
            )
            return input_datetime > datetime.now()
        except ValueError:
            return False

    # ===== ОБРАБОТЧИКИ РЕГИСТРАЦИИ =====
    async def process_phone(self, message: types.Message, state: FSMContext):
        phone = message.contact.phone_number
        await state.update_data(phone=phone)

        await message.answer(
            "Отлично! Теперь введите ваше имя:",
            reply_markup=types.ReplyKeyboardRemove()
        )
        await state.set_state(RegistrationStates.waiting_for_name)

    async def process_name(self, message: types.Message, state: FSMContext):
        name = message.text
        user_data = await state.get_data()
        user_id = message.from_user.id

        db.add_user(user_id, name, user_data["phone"])

        await message.answer(
            f"✅ Регистрация успешно завершена!\n\n"
            f"Ваши данные:\n"
            f"Имя: {name}\n"
            f"Телефон: {user_data['phone']}\n\n"
            f"Теперь вы можете начать покупки!",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()

    # ===== ОБРАБОТЧИКИ ГЛАВНОГО МЕНЮ =====
    async def show_catalog(self, message: types.Message, state: FSMContext):
        await message.answer(
            "Выберите категорию товаров:",
            reply_markup=get_categories_keyboard()
        )
        await state.set_state(ShoppingStates.selecting_category)

    async def show_cart(self, message: types.Message, state: FSMContext):
        user_id = message.from_user.id
        cart_items = db.get_user_cart(user_id)

        if not cart_items:
            await message.answer(
                "Ваша корзина пуста 😔\n"
                "Перейдите в каталог, чтобы добавить товары.",
                reply_markup=get_main_menu_keyboard()
            )
        else:
            cart_text = "🛍️ Ваша корзина:\n\n"
            total = 0

            for item in cart_items:
                item_total = item["price"] * item["quantity"]
                total += item_total
                cart_text += f"• {item['name']}: {item['quantity']} {item['unit']} × {item['price']}сум = {item_total}сум\n"

            cart_text += f"\n💰 Итого: {total}сум"

            await message.answer(cart_text, reply_markup=get_cart_keyboard())
            await state.set_state(ShoppingStates.viewing_cart)

    # ===== ОБРАБОТЧИКИ КАТАЛОГА =====
    async def process_category(self, callback: types.CallbackQuery, state: FSMContext):
        category_id = int(callback.data.replace("category_", ""))
        products = db.get_products_by_category(category_id)

        if products:
            await callback.message.edit_text(
                f"Товары в выбранной категории:",
                reply_markup=get_products_keyboard(category_id)
            )
        else:
            await callback.answer("В этой категории пока нет товаров", show_alert=True)

        await state.set_state(ShoppingStates.selecting_product)

    async def process_product(self, callback: types.CallbackQuery, state: FSMContext):
        product_id = int(callback.data.replace("product_", ""))
        product = db.get_product(product_id)

        if product:
            await state.update_data(selected_product=product_id, quantity=0)

            if product["image"]:
                # Создаем временный файл для изображения
                temp_filename = f"temp_{product_id}.jpg"
                with open(temp_filename, "wb") as f:
                    f.write(product["image"])

                with open(temp_filename, "rb") as photo_file:
                    photo = types.BufferedInputFile(
                        file=photo_file.read(),
                        filename=temp_filename
                    )
                    await callback.message.answer_photo(
                        photo=photo,
                        caption=f"📦 {product['name']}\n"
                                f"💰 Цена: {product['price']}сум/{product['unit']}\n"
                                f"📊 Доступно: {product['quantity']} {product['unit']}\n\n"
                                f"Выберите количество:",
                        reply_markup=get_quantity_keyboard(0)
                    )

                # Удаляем временный файл
                os.remove(temp_filename)
            else:
                await callback.message.edit_text(
                    f"📦 {product['name']}\n"
                    f"💰 Цена: {product['price']}сум/{product['unit']}\n"
                    f"📊 Доступно: {product['quantity']} {product['unit']}\n\n"
                    f"Выберите количество:",
                    reply_markup=get_quantity_keyboard(0)
                )

            await state.set_state(ShoppingStates.selecting_quantity)

    # ===== ОБРАБОТЧИКИ КОЛИЧЕСТВА =====
    async def quantity_minus(self, callback: types.CallbackQuery, state: FSMContext):
        data = await state.get_data()
        quantity = max(0, data.get("quantity", 0) - 1)
        await state.update_data(quantity=quantity)

        await callback.message.edit_reply_markup(
            reply_markup=get_quantity_keyboard(quantity)
        )

    async def quantity_plus(self, callback: types.CallbackQuery, state: FSMContext):
        data = await state.get_data()
        product_id = data.get("selected_product")
        product = db.get_product(product_id)

        if product:
            quantity = min(product["quantity"], data.get("quantity", 0) + 1)
            await state.update_data(quantity=quantity)

            await callback.message.edit_reply_markup(
                reply_markup=get_quantity_keyboard(quantity)
            )

    async def add_to_cart(self, callback: types.CallbackQuery, state: FSMContext):
        data = await state.get_data()
        quantity = data.get("quantity", 0)

        if quantity == 0:
            await callback.answer("Выберите количество товара", show_alert=True)
            return

        user_id = callback.from_user.id
        product_id = data.get("selected_product")

        db.add_to_cart(user_id, product_id, quantity)

        await callback.answer(f"✅ Товар добавлен в корзину ({quantity} кг)", show_alert=True)

        # Возврат к категориям
        try:
            await callback.message.edit_text(
                "Выберите категорию товаров:",
                reply_markup=get_categories_keyboard()
            )
        except:
            await callback.message.answer(
                "Выберите категорию товаров:",
                reply_markup=get_categories_keyboard()
            )
        await state.set_state(ShoppingStates.selecting_category)

    async def continue_shopping(self, callback: types.CallbackQuery, state: FSMContext):
        try:
            await callback.message.edit_text(
                "Выберите категорию товаров:",
                reply_markup=get_categories_keyboard()
            )
        except:
            await callback.message.answer(
                "Выберите категорию товаров:",
                reply_markup=get_categories_keyboard()
            )
        await state.set_state(ShoppingStates.selecting_category)

    # ===== ОБРАБОТЧИКИ КОРЗИНЫ И ОФОРМЛЕНИЯ =====
    async def back_to_catalog(self, message: types.Message, state: FSMContext):
        await self.show_catalog(message, state)

    async def start_checkout(self, message: types.Message, state: FSMContext):
        await message.answer(
            "📅 Введите дату доставки (в формате ДД.ММ.ГГГГ):",
            reply_markup=types.ReplyKeyboardRemove()
        )
        await state.set_state(OrderStates.waiting_for_date)

    async def process_delivery_date(self, message: types.Message, state: FSMContext):
        date = message.text.strip()

        if not self.is_valid_date(date):
            await message.answer(
                "❌ Неверный формат даты или выбрана прошедшая дата. "
                "Пожалуйста, введите дату в формате ДД.ММ.ГГГГ (например, 25.12.2023)"
            )
            return

        await state.update_data(delivery_date=date)
        current_time = datetime.now().strftime("%H:%M")

        await message.answer(
            f"🕐 Введите время доставки (например, {current_time}):\n"
            "• Время должно быть в формате ЧЧ:ММ (например, 14:30)\n"
            "• Время работы: с 09:00 до 22:00"
        )
        await state.set_state(OrderStates.waiting_for_time)

    async def process_delivery_time(self, message: types.Message, state: FSMContext):
        time_str = message.text.strip()

        # Проверяем формат времени
        if not self.is_valid_time(time_str):
            await message.answer(
                "❌ Неверный формат времени. Пожалуйста, введите время в формате ЧЧ:ММ\n"
                "Пример: 14:30"
            )
            return

        # Проверяем рабочее время (9:00-22:00)
        try:
            delivery_time = datetime.strptime(time_str, "%H:%M").time()
            if not (time(9, 0) <= delivery_time <= time(22, 0)):
                await message.answer(
                    "❌ Время доставки возможно только с 09:00 до 22:00. "
                    "Пожалуйста, выберите другое время."
                )
                return
        except ValueError:
            pass  # Если время не распарсилось, пропускаем эту проверку

        # Получаем выбранную дату из состояния
        data = await state.get_data()
        date_str = data.get('delivery_date')

        # Проверяем, что выбранное время не в прошлом
        if not self.is_valid_datetime_combination(date_str, time_str):
            await message.answer(
                "❌ Выбрано прошедшее время. Пожалуйста, выберите будущее время."
            )
            return

        await state.update_data(delivery_time=time_str)

        await message.answer(
            "📍 Отправьте адрес доставки:\n"
            "• Геолокацию через кнопку ниже\n"
            "• Или ссылку на Яндекс/Google карты",
            reply_markup=get_location_keyboard()
        )
        await state.set_state(OrderStates.waiting_for_address)

    async def process_delivery_address(self, message: types.Message, state: FSMContext):
        if message.location:
            address = f"Геолокация: {message.location.latitude}, {message.location.longitude}"
        else:
            address = message.text

        await state.update_data(delivery_address=address)

        # Подготовка итогового заказа
        user_id = message.from_user.id
        user_info = db.get_user(user_id)
        cart_items = db.get_user_cart(user_id)
        data = await state.get_data()

        order_text = "📋 Ваш заказ:\n\n"
        total = 0

        for item in cart_items:
            item_total = item["price"] * item["quantity"]
            total += item_total
            order_text += f"• {item['name']}: {item['quantity']} {item['unit']} × {item['price']}сум = {item_total}сум\n"

        order_text += f"\n💰 Итого: {total}сум\n"
        order_text += f"📅 Дата доставки: {data['delivery_date']}\n"
        order_text += f"🕐 Время доставки: {data['delivery_time']}\n"
        order_text += f"📍 Адрес: {address}\n\n"
        order_text += "Подтвердить заказ?"

        await message.answer(order_text, reply_markup=get_confirm_order_keyboard())
        await state.set_state(OrderStates.confirming_order)

    async def confirm_order(self, callback: types.CallbackQuery, state: FSMContext):
        user_id = callback.from_user.id
        user_info = db.get_user(user_id)
        cart_items = db.get_user_cart(user_id)
        data = await state.get_data()

        if not user_info:
            await callback.answer("❌ Ошибка: не удалось найти информацию о пользователе", show_alert=True)
            return

        # Рассчитываем общую сумму
        total = sum(item["price"] * item["quantity"] for item in cart_items)

        # Сохраняем заказ в базу данных
        order_id = db.create_order(
            user_id, total, data['delivery_date'],
            data['delivery_time'], data['delivery_address'], cart_items
        )

        # Формирование сообщения для админской группы
        admin_message = "🆕 <b>НОВЫЙ ЗАКАЗ!</b>\n\n"
        admin_message += f"👤 <b>От:</b> @{callback.from_user.username or 'Нет username'}"
        admin_message += f" ({user_info.get('name', 'Имя не указано')})\n"
        admin_message += f"📱 <b>Телефон:</b> {user_info.get('phone', 'Не указан')}\n\n"

        admin_message += "<b>🛒 Список товаров:</b>\n"
        for item in cart_items:
            item_total = item["price"] * item["quantity"]
            admin_message += f"• {item['name']}: {item['quantity']} {item['unit']} × {item['price']}сум = {item_total}сум\n"

        # Добавляем локацию, если это координаты
        location = data['delivery_address']
        if location.startswith("Геолокация:"):
            try:
                # Извлекаем координаты из строки
                coords = location.replace("Геолокация:", "").strip().split(",")
                lat = coords[0].strip()
                lon = coords[1].strip()
                location_url = f"https://www.google.com/maps?q={lat},{lon}"
                admin_message += f"\n📍 <b>Локация:</b> <a href='{location_url}'>Открыть на карте</a>\n"
            except:
                admin_message += f"\n📍 <b>Локация:</b> {location}\n"
        else:
            admin_message += f"\n📍 <b>Адрес:</b> {location}\n"

        admin_message += f"\n💰 <b>Сумма к оплате:</b> {total}сум\n"
        admin_message += f"\n📅 <b>Дата и время доставки:</b> {data['delivery_date']} в {data['delivery_time']}"

        try:
            # Отправляем сообщение в группу админов
            await self.bot.send_message(
                chat_id=ADMIN_GROUP_ID,
                text=admin_message,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления в группу: {e}")

        await callback.message.edit_text(
            "✅ <b>Заказ успешно оформлен!</b>\n\n"
            "Мы свяжемся с вами для подтверждения.\n"
            "Спасибо за покупку! 😊",
            parse_mode='HTML'
        )

        await callback.message.answer(
            "Вы вернулись в главное меню.",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()

    async def cancel_order(self, callback: types.CallbackQuery, state: FSMContext):
        await callback.message.edit_text("❌ Заказ отменен")
        await callback.message.answer(
            "Вы вернулись в главное меню.",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()

    # ===== CALLBACK QUERY HANDLERS =====
    async def back_to_categories_callback(self, callback: types.CallbackQuery, state: FSMContext):
        await callback.message.edit_text(
            "Выберите категорию товаров:",
            reply_markup=get_categories_keyboard()
        )
        await state.set_state(ShoppingStates.selecting_category)

    async def view_cart_inline(self, callback: types.CallbackQuery, state: FSMContext):
        user_id = callback.from_user.id
        cart_items = db.get_user_cart(user_id)

        if not cart_items:
            await callback.answer("Ваша корзина пуста", show_alert=True)
        else:
            cart_text = "🛍️ Ваша корзина:\n\n"
            total = 0

            for item in cart_items:
                item_total = item["price"] * item["quantity"]
                total += item_total
                cart_text += f"• {item['name']}: {item['quantity']} {item['unit']} × {item['price']}сум = {item_total}сум\n"

            cart_text += f"\n💰 Итого: {total}сум"

            await callback.message.edit_text(cart_text, reply_markup=get_cart_inline_keyboard())
            await state.set_state(ShoppingStates.viewing_cart)

    async def start_checkout_inline(self, callback: types.CallbackQuery, state: FSMContext):
        await callback.message.answer(
            "📅 Введите дату доставки (в формате ДД.ММ.ГГГГ):",
            reply_markup=types.ReplyKeyboardRemove()
        )
        await state.set_state(OrderStates.waiting_for_date)

    async def clear_cart(self, callback: types.CallbackQuery):
        user_id = callback.from_user.id
        db.clear_cart(user_id)

        await callback.answer("🗑 Корзина очищена", show_alert=True)
        await callback.message.edit_text(
            "Корзина очищена. Выберите категорию товаров:",
            reply_markup=get_categories_keyboard()
        )

    # ===== UNKNOWN MESSAGES =====
    async def unknown_message(self, message: types.Message):
        user_id = message.from_user.id
        user = db.get_user(user_id)

        if not user:
            await message.answer(
                "Пожалуйста, начните с команды /start для регистрации",
                reply_markup=types.ReplyKeyboardRemove()
            )
        else:
            await message.answer(
                "Используйте кнопки меню для навигации",
                reply_markup=get_main_menu_keyboard()
            )
