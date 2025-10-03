import sqlite3
import io
from typing import Optional, Tuple, Union
from PIL import Image, ImageOps, UnidentifiedImageError

# Поддерживаемые форматы изображений
SUPPORTED_IMAGE_TYPES = {
    'image/jpeg': 'JPEG',
    'image/png': 'PNG',
    'image/webp': 'WEBP',
    'image/gif': 'GIF'
}


def save_product_image(db_path: str, product_id: int, image_data: bytes) -> bool:
    """Сохраняет изображение товара в базу данных"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('UPDATE products SET image = ? WHERE id = ?', (image_data, product_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Ошибка при сохранении изображения: {e}")
        return False


def get_product_image(db_path: str, product_id: int) -> Optional[bytes]:
    """Получает изображение товара из базы данных"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT image FROM products WHERE id = ?', (product_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result and result[0] else None
    except Exception as e:
        print(f"Ошибка при получении изображения: {e}")
        return None


def process_image(
        image_data: bytes,
        max_size: Tuple[int, int] = (1200, 1200),
        quality: int = 85
) -> bytes:
    """
    Обрабатывает изображение: изменяет размер и оптимизирует
    Возвращает обработанные байты изображения в формате JPEG
    """
    try:
        # Открываем изображение
        image = Image.open(io.BytesIO(image_data))

        # Конвертируем в RGB, если это необходимо (для PNG с прозрачностью)
        if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1])
            image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')

        # Изменяем размер с сохранением пропорций
        image.thumbnail(max_size, Image.Resampling.LANCZOS)

        # Сохраняем в буфер
        output = io.BytesIO()
        image.save(output, format='JPEG', quality=quality, optimize=True)

        return output.getvalue()

    except UnidentifiedImageError:
        print("Ошибка: Невозможно определить формат изображения")
        raise
    except Exception as e:
        print(f"Ошибка при обработке изображения: {e}")
        raise
