import asyncio
import random
import logging
from datetime import datetime
from io import BytesIO

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text, select

from PIL import Image, ImageDraw, ImageFont
import aiohttp
import os

# ============ КОНФИГ ============
BOT_TOKEN = "ТВОЙ_ТОКЕН_ОТ_BOTFATHER"
ADMIN_ID = 123456789  # ТВОЙ TELEGRAM ID (узнай у @userinfobot)
XROCKET_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBJZCI6IjMwMDM4NCIsImp0aSI6ImFwcDozMDAzODQ6ZDZiZDZjNmEtZGRmMy00OWZjLThiMGYtMTQ1ODdhMzc4OGZkIiwiaWF0IjoxNzg4MTk5ODAzfQ.rCUj5jRWFyRMA3xxs5h9fij6K4an7SX7VFnjqVeIVzk"

# ============ БАЗА ДАННЫХ ============
Base = declarative_base()
engine = create_async_engine("sqlite+aiosqlite:///bot.db", echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String)
    first_name = Column(String)
    coins = Column(Integer, default=100)
    stars = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

class Case(Base):
    __tablename__ = 'cases'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    emoji = Column(String, default="📦")
    price_coins = Column(Integer)
    price_stars = Column(Integer)
    is_admin = Column(Boolean, default=False)
    category = Column(String)

class Item(Base):
    __tablename__ = 'items'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    image_url = Column(String)
    case_id = Column(Integer, ForeignKey('cases.id'))
    rarity = Column(String, default="common")
    weight = Column(Float, default=1.0)

class UserItem(Base):
    __tablename__ = 'user_items'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    item_id = Column(Integer, ForeignKey('items.id'))
    received_at = Column(DateTime, default=datetime.utcnow)
    is_withdrawn = Column(Boolean, default=False)

class WithdrawRequest(Base):
    __tablename__ = 'withdraw_requests'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    item_id = Column(Integer, ForeignKey('items.id'))
    screenshot_url = Column(String)
    status = Column(String, default='pending')
    created_at = Column(DateTime, default=datetime.utcnow)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSessionLocal() as session:
        count = await session.execute(select(Case))
        if not count.scalars().first():
            await seed_data(session)

async def seed_data(session: AsyncSession):
    cases = [
        Case(name="Базовый", description="Обычные стикеры", emoji="📦", price_coins=50, category="cheap"),
        Case(name="Ларчик", description="Случайный промокод", emoji="🎁", price_coins=100, category="cheap"),
        Case(name="Сундучок удачи", description="Набор мемов", emoji="🧰", price_coins=150, category="cheap"),
        Case(name="Кибер-бокс", description="Эксклюзивный стикерпак", emoji="💻", price_coins=300, category="mid"),
        Case(name="Магический артефакт", description="Редкий значок", emoji="🔮", price_coins=450, category="mid"),
        Case(name="Космический рейс", description="Уникальная аватарка", emoji="🚀", price_coins=600, category="mid"),
        Case(name="Золотой трон", description="Гарантированный редкий предмет", emoji="👑", price_coins=1000, category="expensive"),
        Case(name="Легенда", description="Очень редкий стикер", emoji="⭐", price_coins=1800, category="expensive"),
        Case(name="Божественный дар", description="Мифический предмет", emoji="✨", price_coins=2500, category="expensive"),
        Case(name="Тайная комната", description="Супер-редкие предметы", emoji="🚪", price_stars=25, is_admin=True, category="admin"),
        Case(name="Изумрудный сундук", description="Гарантированный подарок", emoji="💎", price_stars=25, is_admin=True, category="admin"),
    ]
    session.add_all(cases)
    await session.commit()

    items = [
        Item(name="😊 Стикер-смайлик", case_id=1, weight=10, rarity="common"),
        Item(name="🎯 Промокод 50₽", case_id=1, weight=2, rarity="rare"),
        Item(name="🎨 Рамка профиля", case_id=5, weight=1, rarity="epic"),
        Item(name="🌟 50 звёзд", case_id=8, weight=1, rarity="legendary"),
        Item(name="🔥 VIP-статус на месяц", case_id=9, weight=1, rarity="mythical"),
        Item(name="🎁 Промокод 1000₽", case_id=10, weight=1, rarity="legendary"),
        Item(name="📱 Эксклюзивный стикер", case_id=4, weight=3, rarity="rare"),
        Item(name="🪐 Космический фон", case_id=6, weight=2, rarity="epic"),
        Item(name="💎 100 звёзд", case_id=7, weight=1, rarity="legendary"),
        Item(name="🎮 Игровой промокод", case_id=11, weight=1, rarity="mythical"),
    ]
    session.add_all(items)
    await session.commit()

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
        if case.is_admin:
            price = f"{case.price_stars}⭐"
        else:
            price = f"{case.price_coins}💰"
        kb.append([InlineKeyboardButton(
            text=f"{case.emoji} {case.name} ({price})",
            callback_data=f"open_{case.id}"
        )])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_cases")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def item_buttons(item_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📦 В инвентарь", callback_data=f"take_{item_id}")],
            [InlineKeyboardButton(text="📤 Вывести", callback_data=f"withdraw_{item_id}")]
        ]
    )

def withdraw_admin_buttons(request_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{request_id}")],
            [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{request_id}")]
        ]
    )

# ============ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ============
def get_random_item(items):
    total = sum(i.weight for i in items)
    r = random.uniform(0, total)
    current = 0
    for item in items:
        current += item.weight
        if r <= current:
            return item
    return items[0]

async def generate_screenshot(item_name, username):
    img = Image.new('RGB', (800, 600), color=(20, 25, 35))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
    except:
        font = ImageFont.load_default()
    
    draw.text((50, 250), f"🎁 {item_name}", font=font, fill=(255, 215, 0))
    draw.text((50, 350), f"👤 {username}", font=font, fill=(200, 200, 200))
    draw.text((50, 450), f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}", font=font, fill=(150, 150, 150))
    
    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf

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
        except:
            return None

# ============ ОСНОВНОЙ БОТ ============
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ---- СТАРТ ----
@dp.message(Command("start"))
async def cmd_start(message: Message):
    async with AsyncSessionLocal() as session:
        user = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = user.scalar_one_or_none()
        if not user:
            user = User(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name
            )
            session.add(user)
            await session.commit()
    
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
    async with AsyncSessionLocal() as session:
        user = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = user.scalar_one()
        
        items_count = await session.execute(select(UserItem).where(UserItem.user_id == user.id))
        items_count = len(items_count.scalars().all())
        
        await message.answer(
            f"👤 *Профиль*\n\n"
            f"💰 Монет: {user.coins}\n"
            f"⭐ Звёзд: {user.stars}\n"
            f"🎁 Предметов: {items_count}\n"
            f"🆔 ID: {user.telegram_id}",
            parse_mode="Markdown"
        )

# ---- КЕЙСЫ ----
@dp.message(F.text == "🎰 Кейсы")
async def show_categories(message: Message):
    await message.answer("📦 Выбери категорию кейсов:", reply_markup=categories_menu())

@dp.callback_query(F.data.startswith("cat_"))
async def show_cases(callback: CallbackQuery):
    category = callback.data.split("_")[1]
    
    async with AsyncSessionLocal() as session:
        if category == "admin":
            cases = await session.execute(select(Case).where(Case.is_admin == True))
        else:
            cases = await session.execute(select(Case).where(Case.category == category))
        cases = cases.scalars().all()
        
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
    
    async with AsyncSessionLocal() as session:
        user = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
        user = user.scalar_one()
        
        case = await session.execute(select(Case).where(Case.id == case_id))
        case = case.scalar_one()
        
        if case.is_admin:
            if user.stars < case.price_stars:
                await callback.answer(f"❌ Нужно {case.price_stars} звёзд! У тебя {user.stars}", show_alert=True)
                return
            user.stars -= case.price_stars
        else:
            if user.coins < case.price_coins:
                await callback.answer(f"❌ Нужно {case.price_coins} монет! У тебя {user.coins}", show_alert=True)
                return
            user.coins -= case.price_coins
        
        items = await session.execute(select(Item).where(Item.case_id == case_id))
        items = items.scalars().all()
        selected = get_random_item(items)
        
        user_item = UserItem(user_id=user.id, item_id=selected.id)
        session.add(user_item)
        await session.commit()
        
        rarity_emoji = {"common": "⬜", "rare": "🟦", "epic": "🟪", "legendary": "🟧", "mythical": "🟥"}
        
        await callback.message.answer_photo(
            selected.image_url or "https://via.placeholder.com/300/1a1a2e/ffffff?text=🎁",
            caption=f"🎉 *{case.emoji} {case.name}*\n\n"
                   f"⭐ Предмет: *{selected.name}*\n"
                   f"🔹 Редкость: {rarity_emoji.get(selected.rarity, '⬜')} {selected.rarity.upper()}\n\n"
                   f"Что делаем с предметом?",
            parse_mode="Markdown",
            reply_markup=item_buttons(user_item.id)
        )
    await callback.answer()

# ---- ИНВЕНТАРЬ ----
@dp.message(F.text == "🎁 Инвентарь")
async def inventory(message: Message):
    async with AsyncSessionLocal() as session:
        user = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = user.scalar_one()
        
        items = await session.execute(
            select(UserItem, Item).join(Item, UserItem.item_id == Item.id)
            .where(UserItem.user_id == user.id, UserItem.is_withdrawn == False)
        )
        items = items.all()
        
        if not items:
            await message.answer("📭 У тебя пока нет предметов! Открой кейс 🎰")
            return
        
        text = "🎁 *Твой инвентарь:*\n\n"
        for user_item, item in items[:10]:
            text += f"• {item.name} (ID: {user_item.id})\n"
        
        if len(items) > 10:
            text += f"\n... и ещё {len(items)-10} предметов"
        
        await message.answer(text, parse_mode="Markdown")

# ---- ВЫВОД ----
@dp.message(F.text == "📤 Вывести")
async def withdraw_menu(message: Message):
    async with AsyncSessionLocal() as session:
        user = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = user.scalar_one()
        
        items = await session.execute(
            select(UserItem, Item).join(Item, UserItem.item_id == Item.id)
            .where(UserItem.user_id == user.id, UserItem.is_withdrawn == False)
        )
        items = items.all()
        
        if not items:
            await message.answer("📭 У тебя нет предметов для вывода!")
            return
        
        kb = InlineKeyboardMarkup(inline_keyboard=[])
        for user_item, item in items[:10]:
            kb.inline_keyboard.append([
                InlineKeyboardButton(text=f"📤 {item.name}", callback_data=f"withdraw_{user_item.id}")
            ])
        kb.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")])
        
        await message.answer("Выбери предмет для вывода:", reply_markup=kb)

@dp.callback_query(F.data.startswith("withdraw_"))
async def withdraw_item(callback: CallbackQuery):
    user_item_id = int(callback.data.split("_")[1])
    
    async with AsyncSessionLocal() as session:
        user_item = await session.execute(
            select(UserItem).where(UserItem.id == user_item_id)
        )
        user_item = user_item.scalar_one()
        
        item = await session.execute(select(Item).where(Item.id == user_item.item_id))
        item = item.scalar_one()
        
        user = await session.execute(select(User).where(User.id == user_item.user_id))
        user = user.scalar_one()
        
        # Генерируем скриншот
        screenshot = await generate_screenshot(item.name, user.username or user.first_name)
        
        # Сохраняем заявку
        request = WithdrawRequest(
            user_id=user.id,
            item_id=item.id,
            screenshot_url="pending"
        )
        session.add(request)
        await session.commit()
        
        # Отправляем админу
        await bot.send_photo(
            ADMIN_ID,
            photo=types.BufferedInputFile(screenshot.getvalue(), filename="withdraw.png"),
            caption=f"📦 *Новая заявка на вывод!*\n\n"
                   f"👤 Пользователь: @{user.username or user.first_name}\n"
                   f"🆔 ID: {user.telegram_id}\n"
                   f"🎁 Предмет: {item.name}\n"
                   f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            parse_mode="Markdown",
            reply_markup=withdraw_admin_buttons(request.id)
        )
        
        await callback.message.answer("✅ Заявка отправлена админу! Ожидай решения.")
    await callback.answer()

# ---- ПОПОЛНЕНИЕ ----
@dp.message(F.text == "💰 Пополнить")
async def topup(message: Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💵 100 монет = 1$", callback_data="topup_100")],
            [InlineKeyboardButton(text="💵 500 монет = 4$", callback_data="topup_500")],
            [InlineKeyboardButton(text="💵 1000 монет = 7$", callback_data="topup_1000")],
            [InlineKeyboardButton(text="💵 5000 монет = 30$", callback_data="topup_5000")],
        ]
    )
    await message.answer(
        "💰 *Пополнение баланса*\n\n"
        "Выбери сумму для пополнения:\n"
        "Оплата проходит через криптовалюту (xRocket)",
        parse_mode="Markdown",
        reply_markup=kb
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
    
    async with AsyncSessionLocal() as session:
        request = await session.execute(select(WithdrawRequest).where(WithdrawRequest.id == request_id))
        request = request.scalar_one()
        request.status = "approved"
        
        user_item = await session.execute(select(UserItem).where(UserItem.id == request.item_id))
        user_item = user_item.scalar_one()
        user_item.is_withdrawn = True
        
        await session.commit()
        
        user = await session.execute(select(User).where(User.id == request.user_id))
        user = user.scalar_one()
        
        await bot.send_message(user.telegram_id, "✅ Твоя заявка на вывод одобрена! Свяжись с админом для получения подарка.")
        await callback.message.edit_caption(f"✅ ОДОБРЕНО\n\n{callback.message.caption}")
    await callback.answer()

@dp.callback_query(F.data.startswith("reject_"))
async def reject_withdraw(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Только для админа!", show_alert=True)
        return
    
    request_id = int(callback.data.split("_")[1])
    
    async with AsyncSessionLocal() as session:
        request = await session.execute(select(WithdrawRequest).where(WithdrawRequest.id == request_id))
        request = request.scalar_one()
        request.status = "rejected"
        await session.commit()
        
        user = await session.execute(select(User).where(User.id == request.user_id))
        user = user.scalar_one()
        
        await bot.send_message(user.telegram_id, "❌ Твоя заявка на вывод отклонена.")
        await callback.message.edit_caption(f"❌ ОТКЛОНЕНО\n\n{callback.message.caption}")
    await callback.answer()

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
    await init_db()
    print("✅ Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
