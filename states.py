from aiogram.fsm.state import State, StatesGroup

class RegistrationStates(StatesGroup):
    waiting_for_phone = State()
    waiting_for_name = State()

class ShoppingStates(StatesGroup):
    viewing_catalog = State()
    selecting_category = State()
    selecting_product = State()
    selecting_quantity = State()
    viewing_cart = State()

class OrderStates(StatesGroup):
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_address = State()
    confirming_order = State()


class AdminStates(StatesGroup):
    waiting_for_password = State()
    admin_menu = State()
    adding_product_name = State()
    adding_product_price = State()
    adding_product_quantity = State()
    adding_product_category = State()
    adding_product_photo = State()
    editing_product = State()
    deleting_product = State()
    editing_product_select_field = State()
    editing_product_name = State()
    editing_product_price = State()
    editing_product_quantity = State()
    editing_product_category = State()
    editing_product_photo = State()
