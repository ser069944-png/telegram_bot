import telebot
from telebot import types

# === НАСТРОЙКИ ===
TOKEN = "8053853718:AAHNSXSBl-9ZiIXLgu_haLAxgXhbMJ4ZS4Y"  # токен бота от BotFather
ADMIN_ID = 5524525568             # твой Telegram ID (ты уже дал его)

# Реквизиты (ОБЯЗАТЕЛЬНО ЗАМЕНИ на свои!)
SBP_DETAILS = "Реквизиты для СБП:\n2202 2067 8021 1236"
SBER_DETAILS = "Реквизиты для Сбербанка:\n2202 2067 8021 1236 / Пополнение"
ALFA_DETAILS = "Реквизиты для Альфа-Банка:\n2200 1513 2992 5569 / Пополнение"

# Доступные суммы пополнения (на СТИМ)
AMOUNTS = [100, 150, 200, 250, 300, 350, 400, 450,
           500, 550, 600, 650, 700, 750, 800, 900, 950, 1000]

COMMISSION = 40  # комиссия всегда +40 рублей

bot = telebot.TeleBot(TOKEN)

# === ПАМЯТЬ В БОТЕ (ПРОСТАЯ) ===
user_states = {}      # user_id -> {step, amount, pay_amount, payment_method}
orders = {}           # order_id -> dict с заявкой
next_order_id = 1     # простой счётчик заявок


# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def get_payment_text(method: str) -> str:
    """Текст с реквизитами по способу оплаты."""
    if method == "sbp":
        return SBP_DETAILS
    if method == "sber":
        return SBER_DETAILS
    if method == "alfa":
        return ALFA_DETAILS
    return "Способ оплаты не найден. Напиши оператору."


def create_amount_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    # по 3 кнопки в ряд
    row = []
    for i, amount in enumerate(AMOUNTS, start=1):
        pay_amount = amount + COMMISSION
        btn = types.InlineKeyboardButton(
            text=f"{amount} ₽ (к оплате {pay_amount} ₽)",
            callback_data=f"amount_{amount}"
        )
        row.append(btn)
        if i % 3 == 0:
            keyboard.row(*row)
            row = []
    if row:
        keyboard.row(*row)
    return keyboard


def create_payment_method_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("СБП", callback_data="pay_sbp"),
        types.InlineKeyboardButton("Сбер", callback_data="pay_sber"),
        types.InlineKeyboardButton("Альфа", callback_data="pay_alfa"),
    )
    return keyboard


# === ОБРАБОТЧИКИ КОМАНД ===

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message: telebot.types.Message):
    text = (
        "👋 Привет! Это магазин по пополнению Steam.\n\n"
        "💸 *Правила и комиссия:*\n"
        "— Ты выбираешь сумму, на которую нужно пополнить Steam (100–1000₽).\n"
        f"— К любой сумме добавляется фиксированная комиссия *+{COMMISSION}₽*.\n"
        "— Например: хочешь, чтобы на Steam пришло 100₽ → оплачиваешь 140₽.\n\n"
        "Чтобы начать пополнение, нажми кнопку ниже 👇"
    )

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("💰 Пополнить Steam")
    btn2 = types.KeyboardButton("ℹ️ Помощь")
    keyboard.add(btn1, btn2)

    bot.send_message(
        message.chat.id,
        text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )


@bot.message_handler(commands=['admin'])
def admin_panel(message: telebot.types.Message):
    """Простая админ-панель, доступна только тебе."""
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ У тебя нет доступа к админ-панели.")
        return

    opened = [o for o in orders.values() if o["status"] == "new"]
    txt = "🛠 Админ-панель\n\n"
    txt += f"Всего заявок: {len(orders)}\n"
    txt += f"Новых (не обработанных): {len(opened)}\n\n"
    txt += "Новые заявки ты также получаешь автоматически в ЛС при создании.\n"
    txt += "Для управления используй кнопки под заявками."

    bot.send_message(message.chat.id, txt)


# === ОСНОВНОЕ МЕНЮ (ТЕКСТОВЫЕ КНОПКИ) ===

@bot.message_handler(func=lambda m: m.text == "ℹ️ Помощь")
def help_message(message: telebot.types.Message):
    bot.reply_to(
        message,
        "Если есть вопросы по оплате или задержке пополнения — просто напиши сюда.\n"
        "Оператор увидит сообщение и ответит тебе."
    )


@bot.message_handler(func=lambda m: m.text == "💰 Пополнить Steam")
def start_topup(message: telebot.types.Message):
    """Показываем выбор суммы."""
    kb = create_amount_keyboard()
    bot.send_message(
        message.chat.id,
        "Выбери сумму, на которую нужно пополнить Steam.\n"
        f"К каждой сумме будет добавлено +{COMMISSION}₽ комиссии:",
        reply_markup=kb
    )


# === CALLBACK: ВЫБОР СУММЫ ===

@bot.callback_query_handler(func=lambda call: call.data.startswith("amount_"))
def handle_amount(call: telebot.types.CallbackQuery):
    user_id = call.from_user.id
    amount_str = call.data.split("_")[1]

    try:
        amount = int(amount_str)
    except ValueError:
        bot.answer_callback_query(call.id, "Ошибка суммы.")
        return

    pay_amount = amount + COMMISSION

    # сохраняем состояние пользователя
    user_states[user_id] = {
        "step": "amount_chosen",
        "amount": amount,
        "pay_amount": pay_amount,
        "payment_method": None,
    }

    text = (
        f"Ты выбрал пополнить Steam на *{amount}₽*.\n"
        f"К оплате с комиссией: *{pay_amount}₽* (+{COMMISSION}₽).\n\n"
        "Теперь выбери способ оплаты:"
    )
    kb = create_payment_method_keyboard()

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=text,
        parse_mode="Markdown",
        reply_markup=kb
    )
    bot.answer_callback_query(call.id)


# === CALLBACK: ВЫБОР СПОСОБА ОПЛАТЫ ===

@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
def handle_payment_method(call: telebot.types.CallbackQuery):
    user_id = call.from_user.id
    state = user_states.get(user_id)

    if not state or state.get("step") != "amount_chosen":
        bot.answer_callback_query(call.id, "Сначала выбери сумму через /start.")
        return

    method_key = call.data.split("_")[1]  # sbp / sber / alfa
    state["payment_method"] = method_key
    state["step"] = "waiting_order_details"

    details_text = get_payment_text(method_key)

    text = (
        f"💳 Ты выбрал способ оплаты: *{method_key.upper()}*.\n\n"
        f"{details_text}\n\n"
        "⚠️ После того как оплатишь, ОДНИМ сообщением напиши сюда:\n"
        "1️⃣ Логин или ссылку на профиль Steam\n"
        "2️⃣ Сумму, которую пополнял\n"
        "3️⃣ Способ оплаты (СБП / Сбер / Альфа)\n\n"
        "По этому сообщению будет создана заявка оператору."
    )

    bot.send_message(
        call.message.chat.id,
        text,
        parse_mode="Markdown"
    )
    bot.answer_callback_query(call.id)


# === СОЗДАНИЕ ЗАЯВКИ ПОСЛЕ ОПЛАТЫ ===

@bot.message_handler(content_types=['text'])
def handle_text(message: telebot.types.Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text

    # Если это не команды и не кнопки — смотрим состояние
    if text in ("💰 Пополнить Steam", "ℹ️ Помощь") or text.startswith("/"):
        # Эти случаи уже ловятся выше / командами
        return

    state = user_states.get(user_id)

    # Если пользователь на шаге ожидания данных — создаём заявку
    if state and state.get("step") == "waiting_order_details":
        global next_order_id

        order_id = next_order_id
        next_order_id += 1

        amount = state["amount"]
        pay_amount = state["pay_amount"]
        method = state["payment_method"]

        order = {
            "id": order_id,
            "user_id": user_id,
            "chat_id": chat_id,
            "username": message.from_user.username,
            "amount": amount,
            "pay_amount": pay_amount,
            "method": method,
            "details": text,   # то, что написал человек (логин, оплата и т.п.)
            "status": "new",
        }
        orders[order_id] = order

        # Очищаем состояние
        user_states[user_id] = {"step": None}

        # Подтверждение пользователю
        bot.reply_to(
            message,
            f"✅ Заявка №{order_id} создана.\n"
            "Оператор проверит оплату и пополнит твой Steam.\n\n"
            "Как только пополнение будет выполнено, ты получишь уведомление от бота."
        )

        # Отправляем заявку админу
        try:
            admin_text = (
                f"🆕 *Новая заявка №{order_id}*\n\n"
                f"👤 Пользователь: @{order['username']} (ID: {order['user_id']})\n"
                f"💰 На Steam: {amount}₽\n"
                f"💳 К оплате: {pay_amount}₽ (+{COMMISSION}₽ комиссия)\n"
                f"📦 Способ оплаты: {method.upper()}\n"
                f"📝 Детали:\n{text}\n\n"
                "Выбери действие:"
            )

            kb = types.InlineKeyboardMarkup()
            kb.add(
                types.InlineKeyboardButton(
                    "✅ Отметить как выполнено",
                    callback_data=f"admin_done_{order_id}"
                ),
                types.InlineKeyboardButton(
                    "❌ Отменить заявку",
                    callback_data=f"admin_cancel_{order_id}"
                )
            )

            bot.send_message(
                ADMIN_ID,
                admin_text,
                parse_mode="Markdown",
                reply_markup=kb
            )
        except Exception:
            # если админу не получилось отправить (например, он не писал боту)
            pass

    else:
        # Просто любое другое сообщение вне процесса — отвечаем мягко
        bot.reply_to(
            message,
            "Я тебя понял 👍\n\n"
            "Если хочешь пополнить Steam — нажми /start и затем кнопку "
            "«💰 Пополнить Steam»."
        )


# === CALLBACK: КНОПКИ АДМИНА ПО ЗАЯВКАМ ===

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_done_") or call.data.startswith("admin_cancel_"))
def handle_admin_actions(call: telebot.types.CallbackQuery):
    user_id = call.from_user.id

    if not is_admin(user_id):
        bot.answer_callback_query(call.id, "❌ Нет доступа.")
        return

    parts = call.data.split("_")
    action = parts[1]   # done / cancel
    try:
        order_id = int(parts[2])
    except ValueError:
        bot.answer_callback_query(call.id, "Ошибка ID заявки.")
        return

    order = orders.get(order_id)
    if not order:
        bot.answer_callback_query(call.id, "Заявка не найдена.")
        return

    if action == "done":
        order["status"] = "done"
        bot.answer_callback_query(call.id, f"Заявка №{order_id} помечена как выполнена.")

        # Сообщаем пользователю
        try:
            bot.send_message(
                order["chat_id"],
                f"✅ Твоя заявка №{order_id} выполнена.\n"
                "Пополнение Steam должно уже прийти. Проверь баланс."
            )
        except Exception:
            pass

        # Обновляем сообщение админу
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )

    elif action == "cancel":
        order["status"] = "canceled"
        bot.answer_callback_query(call.id, f"Заявка №{order_id} отменена.")

        try:
            bot.send_message(
                order["chat_id"],
                f"❌ Твоя заявка №{order_id} была отменена оператором.\n"
                "Если считаешь, что это ошибка — напиши сюда."
            )
        except Exception:
            pass

        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )


print("Бот запущен...")
bot.infinity_polling()
