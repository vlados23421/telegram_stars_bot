import asyncio
import random
import logging
from datetime import datetime
import aiohttp
import sqlite3
import os
import json

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

# ============ КОНФИГ ============
BOT_TOKEN = "ТВОЙ_ТОКЕН_ОТ_BOTFATHER"
ADMIN_ID = 123456789  # ТВОЙ TELEGRAM ID (узнай у @userinfobot)
XROCKET_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBJZCI6IjMwMDM4NCIsImp0aSI6ImFwcDozMDAzODQ6ZDZiZDZjNmEtZGRmMy00OWZjLThiMGYtMTQ1ODdhMzc4OGZkIiwiaWF0IjoxNzg4MTk5ODAzfQ.rCUj5jRWFyRMA3xxs5h9fij6K4an7SX7VFnjqVeIVzk"

# ============ БАЗА ДАННЫХ ============
def init_db():
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            username TEXT,
            first_name TEXT,
            coins INTEGER DEFAULT 100,
            stars INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица кейсов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            emoji TEXT,
            price_coins INTEGER,
            price_stars INTEGER,
            is_admin BOOLEAN DEFAULT 0,
            category TEXT,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    
    # Таблица предметов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            image_url TEXT,
            case_id INTEGER,
            rarity TEXT,
            weight REAL DEFAULT 1.0,
            FOREIGN KEY(case_id) REFERENCES cases(id)
        )
    ''')
    
    # Инвентарь пользователя
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item_id INTEGER,
            received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_withdrawn BOOLEAN DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(item_id) REFERENCES items(id)
        )
    ''')
    
    # Заявки на вывод
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS withdraw_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item_id INTEGER,
            screenshot_url TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(item_id) REFERENCES items(id)
        )
    ''')
    
    # Добавляем кейсы и предметы
    cursor.execute("SELECT COUNT(*) FROM cases")
    if cursor.fetchone()[0] == 0:
        # Дешёвые кейсы
        cursor.execute("INSERT INTO cases (name, description, emoji, price_coins, category) VALUES (?, ?, ?, ?, ?)",
                      ("Базовый", "Обычные стикеры и смайлики", "📦", 50, "cheap"))
        cursor.execute("INSERT INTO cases (name, description, emoji, price_coins, category) VALUES (?, ?, ?, ?, ?)",
                      ("Ларчик", "Случайный промокод", "🎁", 100, "cheap"))
        cursor.execute("INSERT INTO cases (name, description, emoji, price_coins, category) VALUES (?, ?, ?, ?, ?)",
                      ("Сундучок удачи", "Набор мемов и гифок", "🧰", 150, "cheap"))
        
        # Средние кейсы
        cursor.execute("INSERT INTO cases (name, description, emoji, price_coins, category) VALUES (?, ?, ?, ?, ?)",
                      ("Кибер-бокс", "Эксклюзивный стикерпак", "💻", 300, "mid"))
        cursor.execute("INSERT INTO cases (name, description, emoji, price_coins, category) VALUES (?, ?, ?, ?, ?)",
                      ("Магический артефакт", "Редкий значок", "🔮", 450, "mid"))
        cursor.execute("INSERT INTO cases (name, description, emoji, price_coins, category) VALUES (?, ?, ?, ?, ?)",
                      ("Космический рейс", "Уникальная аватарка", "🚀", 600, "mid"))
        
        # Дорогие кейсы
        cursor.execute("INSERT INTO cases (name, description, emoji, price_coins, category) VALUES (?, ?, ?, ?, ?)",
                      ("Золотой трон", "Гарантированный редкий предмет", "👑", 1000, "expensive"))
        cursor.execute("INSERT INTO cases (name, description, emoji, price_coins, category) VALUES (?, ?, ?, ?, ?)",
                      ("Легенда", "Очень редкий анимированный стикер", "⭐", 1800, "expensive"))
        cursor.execute("INSERT INTO cases (name, description, emoji, price_coins, category) VALUES (?, ?, ?, ?, ?)",
                      ("Божественный дар", "Мифический предмет", "✨", 2500, "expensive"))
        
        # Административные кейсы (за звёзды)
        cursor.execute("INSERT INTO cases (name, description, emoji, price_stars, is_admin, category) VALUES (?, ?, ?, ?, ?, ?)",
                      ("Тайная комната", "Супер-редкие предметы", "🚪", 25, 1, "admin"))
        cursor.execute("INSERT INTO cases (name, description, emoji, price_stars, is_admin, category) VALUES (?, ?, ?, ?, ?, ?)",
                      ("Изумрудный сундук", "Гарантированный подарок", "💎", 25, 1, "admin"))
        
        # Предметы для кейсов
        # Базовый (case_id = 1)
        cursor.execute("INSERT INTO items (name, case_id, rarity, weight) VALUES (?, ?, ?, ?)",
                      ("😊 Стикер-смайлик", 1, "common", 10))
        cursor.execute("INSERT INTO items (name, case_id, rarity, weight) VALUES (?, ?, ?, ?)",
                      ("🎯 Промокод 50₽", 1, "rare", 2))
        cursor.execute("INSERT INTO items (name, case_id, rarity, weight) VALUES (?, ?, ?, ?)",
                      ("🌟 5 звёзд", 1, "rare", 1))
        
        # Ларчик (case_id = 2)
        cursor.execute("INSERT INTO items (name, case_id, rarity, weight) VALUES (?, ?, ?, ?)",
                      ("🎮 Промокод 100₽", 2, "rare", 3))
        cursor.execute("INSERT INTO items (name, case_id, rarity, weight) VALUES (?, ?, ?, ?)",
                      ("🌟 10 звёзд", 2, "epic", 1))
        cursor.execute("INSERT INTO items (name, case_id, rarity, weight) VALUES (?, ?, ?, ?)",
                      ("🎨 Стикерпак", 2, "rare", 2))
        
        # Сундучок удачи (case_id = 3)
        cursor.execute("INSERT INTO items (name, case_id, rarity, weight) VALUES (?, ?, ?, ?)",
                      ("🖼️ Мем-гифка", 3, "common", 5))
        cursor.execute("INSERT INTO items (name, case_id, rarity, weight) VALUES (?, ?, ?, ?)",
                      ("🎁 Промокод 50₽", 3, "rare", 2))
        
        # Кибер-бокс (case_id = 4)
        cursor.execute("INSERT INTO items (name, case_id, rarity, weight) VALUES (?, ?, ?, ?)",
                      ("🔥 Эксклюзивный стикерпак", 4, "epic", 2))
        cursor.execute("INSERT INTO items (name, case_id, rarity, weight) VALUES (?, ?, ?, ?)",
                      ("💎 50 звёзд", 4, "legendary", 1))
        cursor.execute("INSERT INTO items (name, case_id, rarity, weight) VALUES (?, ?, ?, ?)",
                      ("🎯 Промокод 200₽", 4, "rare", 3))
        
        # Магический артефакт (case_id = 5)
        cursor.execute("INSERT INTO items (name, case_id, rarity, weight) VALUES (?, ?, ?, ?)",
                      ("🔮 Редкий значок", 5, "epic", 2))
        cursor.execute("INSERT INTO items (name, case_id, rarity, weight) VALUES (?, ?, ?, ?)",
                      ("🌟 20 звёзд", 5, "rare", 3))
        
        # Космический рейс (case_id = 6)
        cursor.execute("INSERT INTO items (name, case_id, rarity, weight) VALUES (?, ?, ?, ?)",
                      ("🪐 Уникальная аватарка", 6, "epic", 2))
        cursor.execute("INSERT INTO items (name, case_id, rarity, weight) VALUES (?, ?, ?, ?)",
                      ("💎 30 звёзд", 6, "epic", 1))
        
        # Золотой трон (case_id = 7)
        cursor.execute("INSERT INTO items (name, case_id, rarity, weight) VALUES (?, ?, ?, ?)",
                      ("👑 Редкий скин", 7, "legendary", 1))
        cursor.execute("INSERT INTO items (name, case_id, rarity, weight) VALUES (?, ?, ?, ?)",
                      ("🎁 Промокод 500₽", 7, "epic", 2))
        cursor.execute("INSERT INTO items (name, case_id, rarity, weight) VALUES (?, ?, ?, ?)",
                      ("💎 100 звёзд", 7, "legendary", 1))
        
        # Легенда (case_id = 8)
        cursor.execute("INSERT INTO items (name, case_id, rarity, weight) VALUES (?, ?, ?, ?)",
                      ("⭐ Анимированный стикер", 8, "legendary", 1))
        cursor.execute("INSERT INTO items (name, case_id, rarity, weight) VALUES (?, ?, ?, ?)",
                      ("🔥 VIP-статус на месяц", 8, "legendary", 1))
        cursor.execute("INSERT INTO items (name, case_id, rarity, weight) VALUES (?, ?, ?, ?)",
                      ("🎁 Промокод 1000₽", 8, "epic", 2))
        
        # Божественный дар (case_id = 9)
        cursor.execute("INSERT INTO items (name, case_id, rarity, weight) VALUES (?, ?, ?, ?)",
                      ("✨ Мифический скин", 9, "mythical", 1))
        cursor.execute("INSERT INTO items (name, case_id, rarity, weight) VALUES (?, ?, ?, ?)",
                      ("👑 VIP-статус на год", 9, "mythical", 1))
        
        # Тайная комната (case_id = 10)
        cursor.execute("INSERT INTO items (name, case_id, rarity, weight) VALUES (?, ?, ?, ?)",
                      ("🎁 Промокод 2000₽", 10, "legendary", 1))
        cursor.execute("INSERT INTO items (name, case_id, rarity, weight) VALUES (?, ?, ?, ?)",
                      ("💎 200 звёзд", 10, "legendary", 1))
        
        # Изумрудный сундук (case_id = 11)
        cursor.execute("INSERT INTO items (name, case_id, rarity, weight) VALUES (?, ?, ?, ?)",
                      ("💎 Эксклюзивный подарок", 11, "mythical", 1))
        cursor.execute("INSERT INTO items (name, case_id, rarity, weight) VALUES (?, ?, ?, ?)",
                      ("🎁 Промокод 5000₽", 11, "mythical", 1))
    
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect('bot.db')
    conn.row_factory = sqlite3.Row
    return conn

# ============ КЛАВИАТУРЫ ============
def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎰 Кейсы")],
            [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="💰 Пополнить")],
            [KeyboardButton(text="🎁 Инвентарь"), KeyboardButton(text="📤 Вывести")],
        ],
        resize_keyboard=True
    )

def categories_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📦 Дешёвые (50-150💰)", callback_data="cat_cheap")],
            [InlineKeyboardButton(text="📦 Средние (300-600💰)", callback_data="cat_mid")],
            [InlineKeyboardButton(text="📦 Дорогие (1000-2500💰)", callback_data="cat_expensive")],
            [InlineKeyboardButton(text="⭐ Административные (25⭐)", callback_data="cat_admin")],
        ]
    )

def case_buttons(cases):
    kb = []
    for case in cases:
        if case['is_admin']:
            price = f"{case['price_stars']}⭐"
        else:
            price = f"{case['price_coins']}💰"
        kb.append([InlineKeyboardButton(
            text=f"{case['emoji']} {case['name']} ({price})",
            callback_data=f"open_{case['id']}"
        )])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_cases")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def item_buttons(user_item_id, item_name):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📦 В инвентарь", callback_data=f"take_{user_item_id}")],
            [InlineKeyboardButton(text="📤 Вывести", callback_data=f"withdraw_{user_item_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
        ]
    )

def withdraw_admin_buttons(request_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{request_id}")],
            [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{request_id}")]
        ]
    )

def withdraw_items_buttons(items):
    kb = []
    for user_item_id, item_name in items[:10]:
        kb.append([InlineKeyboardButton(
            text=f"📤 {item_name}",
            callback_data=f"witem_{user_item_id}"
        )])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def topup_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💵 100 монет = 1$", callback_data="topup_100")],
            [InlineKeyboardButton(text="💵 500 монет = 4$", callback_data="topup_500")],
            [InlineKeyboardButton(text="💵 1000 монет = 7$", callback_data="topup_1000")],
            [InlineKeyboardButton(text="💵 5000 монет = 30$", callback_data="topup_5000")],
        ]
    )

# ============ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ============
def get_random_item(items):
    total = sum(item['weight'] for item in items)
    r = random.uniform(0, total)
    current = 0
    for item in items:
        current += item['weight']
        if r <= current:
            return item
    return items[0]

async def create_xrocket_invoice(user_id: int, amount: int):
    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {XROCKET_TOKEN}"}
        data = {
            "amount": amount,
            "currency": "USD",
            "description": f"Пополнение монет для {user_id}",
            "payload": str(user_id)
        }
        try:
            async with session.post("https://api.xrocket.me/v1/invoice", json=data, headers=headers) as resp:
                result = await resp.json()
                return result.get("invoice_url")
        except Exception as e:
            print(f"Ошибка xRocket: {e}")
            return None

# ============ ОСНОВНОЙ БОТ ============
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ---- СТАРТ ----
@dp.message(Command("start"))
async def cmd_start(message: Message):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (message.from_user.id,)).fetchone()
    
    if not user:
        conn.execute(
            "INSERT INTO users (telegram_id, username, first_name) VALUES (?, ?, ?)",
            (message.from_user.id, message.from_user.username, message.from_user.first_name)
        )
        conn.commit()
    
    conn.close()
    
    await message.answer(
        f"🎮 Привет, {message.from_user.first_name}!\n\n"
        f"Добро пожаловать в мир кейсов!\n"
        f"Открывай кейсы, получай подарки и выводи их!\n\n"
        f"Используй меню ниже 👇",
        reply_markup=main_menu()
    )

# ---- ПРОФИЛЬ ----
@dp.message(F.text == "👤 Профиль")
async def profile(message: Message):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (message.from_user.id,)).fetchone()
    
    items_count = conn.execute("SELECT COUNT(*) FROM user_items WHERE user_id = ? AND is_withdrawn = 0", (user['id'],)).fetchone()[0]
    
    await message.answer(
        f"👤 *Профиль*\n\n"
        f"💰 Монет: {user['coins']}\n"
        f"⭐ Звёзд: {user['stars']}\n"
        f"🎁 Предметов: {items_count}\n"
        f"🆔 ID: {user['telegram_id']}",
        parse_mode="Markdown"
    )
    conn.close()

# ---- КЕЙСЫ ----
@dp.message(F.text == "🎰 Кейсы")
async def show_categories(message: Message):
    await message.answer("📦 Выбери категорию кейсов:", reply_markup=categories_menu())

@dp.callback_query(F.data.startswith("cat_"))
async def show_cases(callback: CallbackQuery):
    category = callback.data.split("_")[1]
    conn = get_db()
    
    if category == "admin":
        cases = conn.execute("SELECT * FROM cases WHERE is_admin = 1 AND is_active = 1").fetchall()
    else:
        cases = conn.execute("SELECT * FROM cases WHERE category = ? AND is_active = 1", (category,)).fetchall()
    
    conn.close()
    
    if not cases:
        await callback.answer("В этой категории пока нет кейсов!")
        return
    
    await callback.message.edit_text(
        f"📦 *{category.upper()} кейсы*\n\nВыбери кейс для открытия:",
        parse_mode="Markdown",
        reply_markup=case_buttons(cases)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("open_"))
async def open_case(callback: CallbackQuery):
    case_id = int(callback.data.split("_")[1])
    conn = get_db()
    
    user = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (callback.from_user.id,)).fetchone()
    case = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    
    if not user or not case:
        await callback.answer("Ошибка!")
        conn.close()
        return
    
    # Проверка валюты
    if case['is_admin']:
        if user['stars'] < case['price_stars']:
            await callback.answer(f"❌ Нужно {case['price_stars']} звёзд! У тебя {user['stars']}", show_alert=True)
            conn.close()
            return
        new_stars = user['stars'] - case['price_stars']
        conn.execute("UPDATE users SET stars = ? WHERE id = ?", (new_stars, user['id']))
    else:
        if user['coins'] < case['price_coins']:
            await callback.answer(f"❌ Нужно {case['price_coins']} монет! У тебя {user['coins']}", show_alert=True)
            conn.close()
            return
        new_coins = user['coins'] - case['price_coins']
        conn.execute("UPDATE users SET coins = ? WHERE id = ?", (new_coins, user['id']))
    
    # Выбор предмета
    items = conn.execute("SELECT * FROM items WHERE case_id = ?", (case_id,)).fetchall()
    selected = get_random_item(items)
    
    # Сохраняем в инвентарь
    conn.execute(
        "INSERT INTO user_items (user_id, item_id) VALUES (?, ?)",
        (user['id'], selected['id'])
    )
    user_item_id = conn.lastrowid
    conn.commit()
    conn.close()
    
    rarity_emoji = {"common": "⬜", "rare": "🟦", "epic": "🟪", "legendary": "🟧", "mythical": "🟥"}
    
    await callback.message.answer_photo(
        selected['image_url'] or "https://via.placeholder.com/300/1a1a2e/ffffff?text=🎁",
        caption=f"🎉 *{case['emoji']} {case['name']}*\n\n"
               f"⭐ Предмет: *{selected['name']}*\n"
               f"🔹 Редкость: {rarity_emoji.get(selected['rarity'], '⬜')} {selected['rarity'].upper()}\n\n"
               f"Что делаем с предметом?",
        parse_mode="Markdown",
        reply_markup=item_buttons(user_item_id, selected['name'])
    )
    await callback.answer()

# ---- ИНВЕНТАРЬ ----
@dp.message(F.text == "🎁 Инвентарь")
async def inventory(message: Message):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (message.from_user.id,)).fetchone()
    
    items = conn.execute(
        "SELECT ui.id, i.name FROM user_items ui JOIN items i ON ui.item_id = i.id "
        "WHERE ui.user_id = ? AND ui.is_withdrawn = 0",
        (user['id'],)
    ).fetchall()
    
    conn.close()
    
    if not items:
        await message.answer("📭 У тебя пока нет предметов! Открой кейс 🎰")
        return
    
    text = "🎁 *Твой инвентарь:*\n\n"
    for idx, item in enumerate(items[:10], 1):
        text += f"{idx}. {item['name']} (ID: {item['id']})\n"
    
    if len(items) > 10:
        text += f"\n... и ещё {len(items)-10} предметов"
    
    await message.answer(text, parse_mode="Markdown")

# ---- ВЫВОД ----
@dp.message(F.text == "📤 Вывести")
async def withdraw_menu(message: Message):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (message.from_user.id,)).fetchone()
    
    items = conn.execute(
        "SELECT ui.id, i.name FROM user_items ui JOIN items i ON ui.item_id = i.id "
        "WHERE ui.user_id = ? AND ui.is_withdrawn = 0",
        (user['id'],)
    ).fetchall()
    
    conn.close()
    
    if not items:
        await message.answer("📭 У тебя нет предметов для вывода!")
        return
    
    items_list = [(item['id'], item['name']) for item in items]
    await message.answer("Выбери предмет для вывода:", reply_markup=withdraw_items_buttons(items_list))

@dp.callback_query(F.data.startswith("witem_"))
async def withdraw_item(callback: CallbackQuery):
    user_item_id = int(callback.data.split("_")[1])
    conn = get_db()
    
    user_item = conn.execute(
        "SELECT * FROM user_items WHERE id = ?",
        (user_item_id,)
    ).fetchone()
    
    if not user_item:
        await callback.answer("Предмет не найден!")
        conn.close()
        return
    
    item = conn.execute("SELECT * FROM items WHERE id = ?", (user_item['item_id'],)).fetchone()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_item['user_id'],)).fetchone()
    
    # Создаём заявку
    conn.execute(
        "INSERT INTO withdraw_requests (user_id, item_id, screenshot_url) VALUES (?, ?, ?)",
        (user['id'], item['id'], "pending")
    )
    request_id = conn.lastrowid
    conn.commit()
    conn.close()
    
    # Отправляем админу
    await bot.send_message(
        ADMIN_ID,
        f"📦 *Новая заявка на вывод!*\n\n"
        f"👤 Пользователь: @{user['username'] or user['first_name']}\n"
        f"🆔 ID: {user['telegram_id']}\n"
        f"🎁 Предмет: {item['name']}\n"
        f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        parse_mode="Markdown",
        reply_markup=withdraw_admin_buttons(request_id)
    )
    
    await callback.message.answer("✅ Заявка отправлена админу! Ожидай решения.")
    await callback.answer()

# ---- ПОПОЛНЕНИЕ ----
@dp.message(F.text == "💰 Пополнить")
async def topup(message: Message):
    await message.answer(
        "💰 *Пополнение баланса*\n\n"
        "Выбери сумму для пополнения:\n"
        "Оплата проходит через криптовалюту (xRocket)",
        parse_mode="Markdown",
        reply_markup=topup_menu()
    )

@dp.callback_query(F.data.startswith("topup_"))
async def process_topup(callback: CallbackQuery):
    amount = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    url = await create_xrocket_invoice(user_id, amount)
    
    if url:
        await callback.message.answer(
            f"💳 *Оплата*\n\n"
            f"Сумма: {amount} монет\n"
            f"Перейди по ссылке для оплаты:\n{url}\n\n"
            f"После оплаты монеты зачислятся автоматически!",
            parse_mode="Markdown"
        )
    else:
        await callback.answer("❌ Ошибка создания платежа! Попробуй позже.", show_alert=True)
    await callback.answer()

# ---- АДМИН ----
@dp.callback_query(F.data.startswith("approve_"))
async def approve_withdraw(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Только для админа!", show_alert=True)
        return
    
    request_id = int(callback.data.split("_")[1])
    conn = get_db()
    
    request = conn.execute("SELECT * FROM withdraw_requests WHERE id = ?", (request_id,)).fetchone()
    if not request:
        await callback.answer("Заявка не найдена!")
        conn.close()
        return
    
    conn.execute("UPDATE withdraw_requests SET status = 'approved' WHERE id = ?", (request_id,))
    conn.execute("UPDATE user_items SET is_withdrawn = 1 WHERE id = ?", (request['item_id'],))
    conn.commit()
    
    user = conn.execute("SELECT * FROM users WHERE id = ?", (request['user_id'],)).fetchone()
    conn.close()
    
    await bot.send_message(user['telegram_id'], "✅ Твоя заявка на вывод одобрена! Свяжись с админом для получения подарка.")
    await callback.message.edit_caption(f"✅ ОДОБРЕНО\n\n{callback.message.caption}")
    await callback.answer()

@dp.callback_query(F.data.startswith("reject_"))
async def reject_withdraw(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Только для админа!", show_alert=True)
        return
    
    request_id = int(callback.data.split("_")[1])
    conn = get_db()
    
    request = conn.execute("SELECT * FROM withdraw_requests WHERE id = ?", (request_id,)).fetchone()
    if not request:
        await callback.answer("Заявка не найдена!")
        conn.close()
        return
    
    conn.execute("UPDATE withdraw_requests SET status = 'rejected' WHERE id = ?", (request_id,))
    conn.commit()
    
    user = conn.execute("SELECT * FROM users WHERE id = ?", (request['user_id'],)).fetchone()
    conn.close()
    
    await bot.send_message(user['telegram_id'], "❌ Твоя заявка на вывод отклонена.")
    await callback.message.edit_caption(f"❌ ОТКЛОНЕНО\n\n{callback.message.caption}")
    await callback.answer()

# ---- НАЗАД ----
@dp.callback_query(F.data == "back_cases")
async def back_cases(callback: CallbackQuery):
    await callback.message.edit_text("📦 Выбери категорию кейсов:", reply_markup=categories_menu())
    await callback.answer()

@dp.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("Главное меню:", reply_markup=main_menu())
    await callback.answer()

# ---- ЗАПУСК ----
async def main():
    init_db()
    print("✅ Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
