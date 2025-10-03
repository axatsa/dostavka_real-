import logging
from aiogram import types, F
from aiogram.fsm.context import FSMContext

from database import Database
from keyboards import *
from states import AdminStates

logger = logging.getLogger(__name__)

db = Database()


class AdminHandlers:
    def __init__(self, bot):
        self.bot = bot

    # ДОБАВЬТЕ ЭТОТ МЕТОД
    async def cmd_admin(self, message: types.Message, state: FSMContext):
        await message.answer("🔐 Введите пароль администратора:")
        await state.set_state(AdminStates.waiting_for_password)

    # Остальные методы остаются без изменений...
    async def check_admin_password(self, message: types.Message, state: FSMContext):
        ADMIN_PASSWORD = "admin123"

        if message.text == ADMIN_PASSWORD:
            await message.answer(
                "✅ Вы вошли в админ-панель!",
                reply_markup=get_admin_keyboard()
            )
            await state.set_state(AdminStates.admin_menu)
        else:
            await message.answer(
                "❌ Неверный пароль!",
                reply_markup=get_main_menu_keyboard()
            )
            await state.clear()

    async def start_add_product(self, message: types.Message, state: FSMContext):
        await message.answer("Введите название товара:")
        await state.set_state(AdminStates.adding_product_name)

    async def show_all_products(self, message: types.Message):
        products = db.get_all_products()
        text = "📋 Все товары:\n\n"

        for product in products:
            text += f"ID: {product['id']}\n"
            text += f"Название: {product['name']}\n"
            text += f"Цена: {product['price']}сум/{product['unit']}\n"
            text += f"Количество: {product['quantity']}\n"
            text += f"Категория: {product['category']}\n"
            text += "─" * 20 + "\n"

        await message.answer(text)

    async def exit_admin(self, message: types.Message, state: FSMContext):
        await message.answer(
            "Вы вышли из админ-панели",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()

    async def process_product_name(self, message: types.Message, state: FSMContext):
        await state.update_data(new_product_name=message.text)
        await message.answer("Введите цену товара (в суммах):")
        await state.set_state(AdminStates.adding_product_price)

    async def process_product_price(self, message: types.Message, state: FSMContext):
        try:
            price = float(message.text)
            await state.update_data(new_product_price=price)
            await message.answer("Введите доступное количество:")
            await state.set_state(AdminStates.adding_product_quantity)
        except ValueError:
            await message.answer("❌ Введите корректную цену (число в суммах)")

    async def process_product_quantity(self, message: types.Message, state: FSMContext):
        try:
            quantity = int(message.text)
            await state.update_data(new_product_quantity=quantity)

            await message.answer("Выберите категорию:", reply_markup=get_categories_admin_keyboard())
            await state.set_state(AdminStates.adding_product_category)
        except ValueError:
            await message.answer("❌ Введите корректное количество (целое число)")

    async def process_product_category(self, message: types.Message, state: FSMContext):
        category_name_with_emoji = message.text
        categories = db.get_categories()

        # Находим ID категории по имени с эмодзи
        category_id = None
        for cat in categories:
            if cat["name"] == category_name_with_emoji:
                category_id = cat["id"]
                break

        if not category_id:
            await message.answer("❌ Неверная категория!")
            return

        await state.update_data(new_product_category=category_id)
        await message.answer(
            "📷 Отправьте фото товара (или отправьте 'пропустить' чтобы добавить без фото):",
            reply_markup=get_skip_photo_keyboard()
        )
        await state.set_state(AdminStates.adding_product_photo)

    async def skip_photo(self, message: types.Message, state: FSMContext):
        await self.add_product_to_db(message, state, None)

    async def process_product_photo(self, message: types.Message, state: FSMContext):
        try:
            # Получаем файл с наилучшим качеством
            photo = message.photo[-1] if message.photo else None
            
            if not photo:
                await message.answer("❌ Пожалуйста, отправьте изображение")
                return
                
            file = await self.bot.get_file(photo.file_id)
            
            # Проверяем тип файла
            file_extension = file.file_path.split('.')[-1].lower()
            if file_extension not in ['jpg', 'jpeg', 'png', 'webp', 'gif']:
                await message.answer(
                    "❌ Поддерживаются только изображения в формате JPG, PNG, WEBP или GIF"
                )
                return
                
            # Скачиваем файл
            photo_bytes = await self.bot.download_file(file.file_path)
            
            # Обрабатываем изображение
            from image_utils import process_image
            processed_image = process_image(
                photo_bytes.read(),
                max_size=(1200, 1200),
                quality=85
            )
            
            await self.add_product_to_db(message, state, processed_image)
            
        except Exception as e:
            print(f"Ошибка при обработке фото: {e}")
            await message.answer(
                "❌ Произошла ошибка при обработке изображения. "
                "Попробуйте отправить другое изображение."
            )

    async def add_product_to_db(self, message: types.Message, state: FSMContext, image_data):
        data = await state.get_data()

        product_id = db.add_product(
            data["new_product_name"],
            data["new_product_price"],
            data["new_product_quantity"],
            data["new_product_category"],
            image_data
        )

        await message.answer(
            f"✅ Товар успешно добавлен!\n\n"
            f"Название: {data['new_product_name']}\n"
            f"Цена: {data['new_product_price']}сум\n"
            f"Количество: {data['new_product_quantity']} кг\n"
            f"ID товара: {product_id}",
            reply_markup=get_admin_keyboard()
        )
        await state.set_state(AdminStates.admin_menu)

    async def start_edit_product(self, message: types.Message, state: FSMContext):
        await message.answer("Введите ID товара для редактирования:")
        await state.set_state(AdminStates.editing_product)

    async def process_edit_product(self, message: types.Message, state: FSMContext):
        try:
            product_id = int(message.text)
            product = db.get_product(product_id)

            if not product:
                await message.answer("❌ Товар с таким ID не найден!")
                return

            await state.update_data(editing_product_id=product_id)

            await message.answer(
                f"Товар для редактирования:\n"
                f"ID: {product['id']}\n"
                f"Название: {product['name']}\n"
                f"Цена: {product['price']}\n"
                f"Количество: {product['quantity']}\n\n"
                f"Что хотите изменить?",
                reply_markup=get_edit_product_keyboard()
            )

        except ValueError:
            await message.answer("❌ Введите корректный ID (число)")

    async def start_delete_product(self, message: types.Message, state: FSMContext):
        await message.answer("Введите ID товара для удаления:")
        await state.set_state(AdminStates.deleting_product)

    async def process_delete_product(self, message: types.Message, state: FSMContext):
        try:
            product_id = int(message.text)
            product = db.get_product(product_id)

            if not product:
                await message.answer("❌ Товар с таким ID не найден!")
                return

            success = db.delete_product(product_id)

            if success:
                await message.answer(
                    f"✅ Товар '{product['name']}' успешно удален!",
                    reply_markup=get_admin_keyboard()
                )
            else:
                await message.answer(
                    "❌ Ошибка при удалении товара!",
                    reply_markup=get_admin_keyboard()
                )

            await state.set_state(AdminStates.admin_menu)

        except ValueError:
            await message.answer("❌ Введите корректный ID (число)")

    # admin.py - замените методы редактирования товаров
    async def start_edit_product(self, message: types.Message, state: FSMContext):
        await message.answer("Введите ID товара для редактирования:")
        await state.set_state(AdminStates.editing_product)

    async def process_edit_product(self, message: types.Message, state: FSMContext):
        try:
            product_id = int(message.text)
            product = db.get_product(product_id)

            if not product:
                await message.answer("❌ Товар с таким ID не найден!")
                return

            # Сохраняем ID товара для редактирования
            await state.update_data(editing_product_id=product_id)

            # Показываем информацию о товаре и клавиатуру выбора поля
            await message.answer(
                f"📦 Товар для редактирования:\n"
                f"ID: {product['id']}\n"
                f"Название: {product['name']}\n"
                f"Цена: {product['price']}сум\n"
                f"Количество: {product['quantity']}\n\n"
                f"Что хотите изменить?",
                reply_markup=get_edit_product_keyboard()
            )

            await state.set_state(AdminStates.editing_product_select_field)

        except ValueError:
            await message.answer("❌ Введите корректный ID (число)")

    # ДОБАВЬТЕ ЭТИ НОВЫЕ МЕТОДЫ ДЛЯ РЕДАКТИРОВАНИЯ КОНКРЕТНЫХ ПОЛЕЙ:

    async def process_edit_field_selection(self, message: types.Message, state: FSMContext):
        data = await state.get_data()
        product_id = data.get("editing_product_id")
        product = db.get_product(product_id)

        if not product:
            await message.answer("❌ Товар не найден!")
            await state.set_state(AdminStates.admin_menu)
            return

        field = message.text.lower()

        if field == "название":
            await message.answer("Введите новое название товара:", reply_markup=types.ReplyKeyboardRemove())
            await state.set_state(AdminStates.editing_product_name)

        elif field == "цена":
            await message.answer("Введите новую цену товара (в суммах):", reply_markup=types.ReplyKeyboardRemove())
            await state.set_state(AdminStates.editing_product_price)

        elif field == "количество":
            await message.answer("Введите новое количество товара:", reply_markup=types.ReplyKeyboardRemove())
            await state.set_state(AdminStates.editing_product_quantity)

        elif field == "категория":
            await message.answer("Выберите новую категорию:", reply_markup=get_categories_admin_keyboard())
            await state.set_state(AdminStates.editing_product_category)

        elif field == "фото":
            await message.answer(
                "📷 Отправьте новое фото товара (или 'пропустить' чтобы удалить текущее фото):",
                reply_markup=get_skip_photo_keyboard()
            )
            await state.set_state(AdminStates.editing_product_photo)

        elif field == "🔙 назад":
            await message.answer("Возврат в админ-меню", reply_markup=get_admin_keyboard())
            await state.set_state(AdminStates.admin_menu)

        else:
            await message.answer("❌ Неизвестное поле. Выберите из списка.")

    async def process_edit_product_name(self, message: types.Message, state: FSMContext):
        data = await state.get_data()
        product_id = data.get("editing_product_id")

        new_name = message.text
        self.update_product_field(product_id, "name", new_name)

        await message.answer(
            f"✅ Название товара обновлено на: {new_name}",
            reply_markup=get_admin_keyboard()
        )
        await state.set_state(AdminStates.admin_menu)

    async def process_edit_product_price(self, message: types.Message, state: FSMContext):
        try:
            new_price = float(message.text)
            data = await state.get_data()
            product_id = data.get("editing_product_id")

            self.update_product_field(product_id, "price", new_price)

            await message.answer(
                f"✅ Цена товара обновлена на: {new_price}сум",
                reply_markup=get_admin_keyboard()
            )
            await state.set_state(AdminStates.admin_menu)
        except ValueError:
            await message.answer("❌ Введите корректную цену (число)")

    async def process_edit_product_quantity(self, message: types.Message, state: FSMContext):
        try:
            new_quantity = int(message.text)
            data = await state.get_data()
            product_id = data.get("editing_product_id")

            self.update_product_field(product_id, "quantity", new_quantity)

            await message.answer(
                f"✅ Количество товара обновлено на: {new_quantity}",
                reply_markup=get_admin_keyboard()
            )
            await state.set_state(AdminStates.admin_menu)
        except ValueError:
            await message.answer("❌ Введите корректное количество (целое число)")

    async def process_edit_product_category(self, message: types.Message, state: FSMContext):
        category_name_with_emoji = message.text
        categories = db.get_categories()

        # Находим ID категории по имени с эмодзи
        category_id = None
        for cat in categories:
            if cat["name"] == category_name_with_emoji:
                category_id = cat["id"]
                break

        if not category_id:
            await message.answer("❌ Неверная категория!")
            return

        data = await state.get_data()
        product_id = data.get("editing_product_id")

        self.update_product_field(product_id, "category_id", category_id)

        await message.answer(
            f"✅ Категория товара обновлена на: {category_name_with_emoji}",
            reply_markup=get_admin_keyboard()
        )
        await state.set_state(AdminStates.admin_menu)

    async def process_edit_product_photo(self, message: types.Message, state: FSMContext):
        data = await state.get_data()
        product_id = data.get("editing_product_id")

        if message.text == "пропустить":
            # Удаляем фото
            self.update_product_field(product_id, "image", None)
            await message.answer(
                "✅ Фото товара удалено",
                reply_markup=get_admin_keyboard()
            )
        elif message.photo:
            # Получаем самое большое изображение
            photo = message.photo[-1]
            file = await self.bot.get_file(photo.file_id)
            photo_bytes = await self.bot.download_file(file.file_path)

            self.update_product_field(product_id, "image", photo_bytes.read())
            await message.answer(
                "✅ Фото товара обновлено",
                reply_markup=get_admin_keyboard()
            )
        else:
            await message.answer("❌ Отправьте фото или нажмите 'пропустить'")
            return

        await state.set_state(AdminStates.admin_menu)

    def update_product_field(self, product_id: int, field: str, value):
        """Обновляет конкретное поле товара в базе данных"""
        conn = db.get_connection()
        cursor = conn.cursor()

        if value is None:
            cursor.execute(f'UPDATE products SET {field} = NULL WHERE id = ?', (product_id,))
        else:
            cursor.execute(f'UPDATE products SET {field} = ? WHERE id = ?', (value, product_id))

        conn.commit()
        conn.close()

    # ... остальные методы без изменений ...
