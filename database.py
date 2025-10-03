import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_name="shop_bot.db"):
        self.db_name = db_name
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                registered_at TEXT NOT NULL
            )
        ''')

        # Таблица категорий
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                emoji TEXT
            )
        ''')

        # Таблица товаров
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                unit TEXT NOT NULL,
                category_id INTEGER,
                image BLOB,
                FOREIGN KEY (category_id) REFERENCES categories (id)
            )
        ''')

        # Таблица корзин
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS carts (
                user_id INTEGER,
                product_id INTEGER,
                quantity INTEGER NOT NULL,
                PRIMARY KEY (user_id, product_id),
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
        ''')

        # Таблица заказов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                total_amount REAL NOT NULL,
                delivery_date TEXT NOT NULL,
                delivery_time TEXT NOT NULL,
                delivery_address TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')

        # Таблица элементов заказа
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS order_items (
                order_id INTEGER,
                product_id INTEGER,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders (id),
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
        ''')

        # Добавляем стандартные категории если их нет
        default_categories = [
            ("Фрукты", "🍎"),
            ("Овощи", "🥕"),
            ("Ягоды", "🍓"),
            ("Молочка", "🥛")
        ]

        cursor.executemany('''
            INSERT OR IGNORE INTO categories (name, emoji) VALUES (?, ?)
        ''', default_categories)

        conn.commit()
        conn.close()
        logger.info("База данных инициализирована")

    def get_connection(self):
        return sqlite3.connect(self.db_name)

    # === USER METHODS ===
    def get_user(self, user_id: int) -> Optional[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, name, phone FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        if user:
            return {"user_id": user[0], "name": user[1], "phone": user[2]}
        return None

    def add_user(self, user_id: int, name: str, phone: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, name, phone, registered_at) 
            VALUES (?, ?, ?, ?)
        ''', (user_id, name, phone, datetime.now().isoformat()))
        conn.commit()
        conn.close()

    # === CATEGORY METHODS ===
    def get_categories(self) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, emoji FROM categories')
        categories = cursor.fetchall()
        conn.close()
        return [{"id": cat[0], "name": f"{cat[1]} {cat[2]}", "raw_name": cat[1]} for cat in categories]

    # === PRODUCT METHODS ===
    def get_products_by_category(self, category_id: int) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, price, quantity, unit, image 
            FROM products WHERE category_id = ?
        ''', (category_id,))
        products = cursor.fetchall()
        conn.close()
        return [{"id": p[0], "name": p[1], "price": p[2], "quantity": p[3], "unit": p[4], "image": p[5]} for p in
                products]

    def get_product(self, product_id: int) -> Optional[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, price, quantity, unit, image FROM products WHERE id = ?', (product_id,))
        product = cursor.fetchone()
        conn.close()
        if product:
            return {"id": product[0], "name": product[1], "price": product[2], "quantity": product[3],
                    "unit": product[4], "image": product[5]}
        return None

    def add_product(self, name: str, price: float, quantity: int, category_id: int, image_data: bytes = None) -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO products (name, price, quantity, unit, category_id, image)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, price, quantity, "кг", category_id, image_data))
        product_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return product_id

    def delete_product(self, product_id: int) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    def get_all_products(self) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.id, p.name, p.price, p.quantity, p.unit, c.name 
            FROM products p 
            JOIN categories c ON p.category_id = c.id
        ''')
        products = cursor.fetchall()
        conn.close()
        return [{"id": p[0], "name": p[1], "price": p[2], "quantity": p[3], "unit": p[4], "category": p[5]} for p in
                products]

    # === CART METHODS ===
    def get_user_cart(self, user_id: int) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.id, p.name, p.price, p.unit, c.quantity 
            FROM carts c 
            JOIN products p ON c.product_id = p.id 
            WHERE c.user_id = ?
        ''', (user_id,))
        cart_items = cursor.fetchall()
        conn.close()
        return [{"id": item[0], "name": item[1], "price": item[2], "unit": item[3], "quantity": item[4]} for item in
                cart_items]

    def add_to_cart(self, user_id: int, product_id: int, quantity: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO carts (user_id, product_id, quantity) 
            VALUES (?, ?, ?)
        ''', (user_id, product_id, quantity))
        conn.commit()
        conn.close()

    def clear_cart(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM carts WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()

    # === ORDER METHODS ===
    def create_order(self, user_id: int, total_amount: float, delivery_date: str,
                     delivery_time: str, delivery_address: str, cart_items: List[Dict]) -> int:
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO orders (user_id, total_amount, delivery_date, delivery_time, delivery_address, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, total_amount, delivery_date, delivery_time, delivery_address, datetime.now().isoformat()))

        order_id = cursor.lastrowid

        for item in cart_items:
            cursor.execute('''
                INSERT INTO order_items (order_id, product_id, quantity, price)
                VALUES (?, ?, ?, ?)
            ''', (order_id, item["id"], item["quantity"], item["price"]))

        # Очищаем корзину
        cursor.execute('DELETE FROM carts WHERE user_id = ?', (user_id,))

        conn.commit()
        conn.close()
        return order_id