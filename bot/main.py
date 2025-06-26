import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    CallbackQuery,
    ForceReply,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)

import config

logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=config.TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()
ADMIN_ID = int(config.ADMIN_TELEGRAM_ID)
BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE = BASE_DIR / "app" / "storage"
STORAGE.mkdir(parents=True, exist_ok=True)

USERS_PATH   = STORAGE / "users.json"
ORDERS_PATH  = STORAGE / "orders.json"
COURIERS_PATH = STORAGE / "couriers.json"
RULES_PATH   = STORAGE / "user_rules.json"

def _load_json(path: Path, default):
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return default

def _save_json(path: Path, data):
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_banned(uid: int | str) -> bool:
    rules: Dict[str, Dict] = _load_json(RULES_PATH, {})
    return bool(rules.get(str(uid), {}).get("ban"))

async def save_user_profile(user: types.User):
    users: Dict[str, Dict] = _load_json(USERS_PATH, {})

    photo_url = ""
    try:
        photos = await bot.get_user_profile_photos(user.id, limit=1)
        if photos.total_count:
            file_id = photos.photos[0][0].file_id
            file = await bot.get_file(file_id)
            tg_url = (
                f"https://api.telegram.org/file/bot{config.TELEGRAM_BOT_TOKEN}/{file.file_path}"
            )
            photo_url = tg_url
    except Exception as e:
        logging.warning(f"Не смог получить аватар {user.id}: {e}")

    users[str(user.id)] = {
        "id":        user.id,
        "username":  user.username or "",
        "full_name": user.full_name or "",
        "avatar":    photo_url,
    }
    _save_json(USERS_PATH, users)

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    uid = message.from_user.id

    await save_user_profile(message.from_user)

    if is_banned(uid):
        await message.answer(
            "⛔️ Вы заблокированы администрацией.\n"
            "Если считаете, что это ошибка, свяжитесь с поддержкой.\n\n"
            "Подробнее: "
        )
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛍 Открыть приложение",
                    web_app=WebAppInfo(url=f"https://vape-spb.store/ligovckij-prospekt/?user_id={uid}"),
                )
            ],
            [
                InlineKeyboardButton(
                    text="📞 Связаться с менеджером",
                    url="https://t.me/",
                )
            ],
        ]
    )

    await message.answer(
        "<b>Добро пожаловать в VAPE SHOP 💨</b>\n"
        "Нажмите «Открыть приложение», чтобы посмотреть каталог 🛒",
        reply_markup=kb,
    )

SECRET_ADMIN_PATH = "/__admin_hidden_qwErTY456"

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("⛔️ Нет доступа.")
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="🛠 Админ-панель",
                web_app=WebAppInfo(
                    url=f"https://vape-spb.store/ligovckij-prospekt{SECRET_ADMIN_PATH}?user_id={ADMIN_ID}"
                ),
            )
        ]]
    )
    await message.answer("👋", reply_markup=kb)

PAGE_SIZE = 10
COMMENT_STATE: Dict[int, Tuple[str, int]] = {}  # uid → (order_id, page)

def build_order_text(order: Dict) -> str:
    return (
        f"<b>Заказ {order['id']}</b>\n"
        f"Создан: {order['created']}\n"
        f"Сумма: <b>{order['total']}₽</b>\n"
        f"Статус: {order.get('status', 'new')}\n"
        f"Курьер: {order.get('courier_name') or '—'}\n"
        f"Комментарий: {order.get('courier_comment') or '—'}"
    )

def build_order_kb(order: Dict, page: int, uid: str) -> InlineKeyboardMarkup | None:
    status = order.get("status") or "new"
    order_id = order["id"]
    buttons: List[InlineKeyboardButton] = []

    courier_id = str(order.get("courier_id", "")) if order.get("courier_id") else ""

    if status == "new":
        buttons.append(
            InlineKeyboardButton(text="✅ Взять",
                                 callback_data=f"take:{order_id}:{page}")
        )
    elif status == "taken" and courier_id == uid:
        buttons.extend([
            InlineKeyboardButton(text="🚫 Отказаться",
                                 callback_data=f"refuse:{order_id}:{page}"),
            InlineKeyboardButton(text="💬 Коммент",
                                 callback_data=f"comment:{order_id}:{page}"),
            InlineKeyboardButton(text="✅ Завершить",
                                 callback_data=f"done:{order_id}:{page}"),
        ])

    if not buttons:
        return None

    keyboard = [[buttons[0]], [buttons[1], buttons[2]]] if len(buttons) > 2 else [buttons]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@dp.message(Command("add_courier"))
async def add_courier(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return
    if not command.args:
        return await message.answer("Используйте:\n/add_courier 123456789")
    uid = command.args.strip().split()[0]
    cur = _load_json(COURIERS_PATH, [])
    if uid not in cur:
        cur.append(uid)
        _save_json(COURIERS_PATH, cur)
    await message.answer(f"✅ Курьер {uid} добавлен.")

@dp.message(Command("del_courier"))
async def del_courier(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return
    if not command.args:
        return await message.answer("Используйте:\n/del_courier 123456789")
    uid = command.args.strip().split()[0]
    cur = _load_json(COURIERS_PATH, [])
    if uid in cur:
        cur.remove(uid)
        _save_json(COURIERS_PATH, cur)
    await message.answer(f"🚫 Курьер {uid} удалён.")

@dp.message(Command("courier"))
async def courier_menu(message: types.Message):
    uid = str(message.from_user.id)
    cur = _load_json(COURIERS_PATH, [])
    if uid not in cur and message.from_user.id != ADMIN_ID:
        return await message.answer("⛔️ Доступ только для курьеров.")
    await send_orders_page(message.chat.id, 0)

async def send_orders_page(chat_id: int, page: int):
    orders = _load_json(ORDERS_PATH, [])
    active = [o for o in orders if o.get("status") != "done"]

    def dt(o):
        return datetime.strptime(o["created"], "%d.%m.%Y %H:%M")

    active.sort(key=dt, reverse=True)

    slice_ = active[page * PAGE_SIZE: (page + 1) * PAGE_SIZE]
    if not slice_:
        return await bot.send_message(chat_id, "Нет активных заказов.")

    rows = [
        [
            InlineKeyboardButton(
                text=f'📦 {o["id"]} • {o["total"]}₽',
                callback_data=f"order:{o['id']}:{page}",
            )
        ]
        for o in slice_
    ]

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("« Назад", callback_data=f"page:{page - 1}"))
    if (page + 1) * PAGE_SIZE < len(active):
        nav.append(InlineKeyboardButton("Вперёд »", callback_data=f"page:{page + 1}"))
    if nav:
        rows.append(nav)

    await bot.send_message(
        chat_id, "Активные заказы:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )

@dp.callback_query(F.data.startswith("page:"))
async def cb_page(call: CallbackQuery):
    await call.answer()
    await call.message.delete()
    await send_orders_page(call.message.chat.id, int(call.data.split(":")[1]))

@dp.callback_query(F.data.startswith("order:"))
async def cb_order(call: CallbackQuery):
    await call.answer()
    order_id, page = call.data.split(":")[1:3]
    await show_order_details(call.message, order_id, int(page), call.from_user.id)

async def show_order_details(
        msg: types.Message,
        order_id: str,
        page: int,
        user_id: int,
        *,
        edit: bool = False,
):
    orders = _load_json(ORDERS_PATH, [])
    order = next((o for o in orders if str(o["id"]) == str(order_id)), None)
    if not order:
        if edit:
            return await msg.delete()
        return await msg.answer("Заказ не найден.")

    text = build_order_text(order)
    kb = build_order_kb(order, page, str(user_id))

    try:
        if edit:
            await msg.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        else:
            await msg.answer(text, reply_markup=kb)
    except Exception as e:
        logging.error(f"Ошибка при редактировании сообщения: {e}")
        if edit:
            await msg.delete()
            await bot.send_message(msg.chat.id, text, reply_markup=kb)

async def update_status(call: CallbackQuery, new_status: str, notice: str):
    await call.answer()
    order_id, page = call.data.split(":")[1:3]
    uid = str(call.from_user.id)
    usern = f"@{call.from_user.username}" if call.from_user.username else str(uid)

    orders = _load_json(ORDERS_PATH, [])
    order = next((o for o in orders if str(o["id"]) == str(order_id)), None)
    if not order:
        return await call.message.answer("Заказ не найден.")

    current = order.get("status") or "new"
    current_courier = str(order.get("courier_id", "")) if order.get("courier_id") else ""

    if new_status == "taken" and current != "new":
        return await call.message.answer("Уже взял другой курьер.")
    if new_status in ("new", "done") and current_courier != uid:
        return await call.message.answer("Этот заказ не ваш.")

    order["status"] = new_status
    if new_status == "new":
        order["courier_id"] = None
        order["courier_name"] = ""
    else:
        order["courier_id"] = uid
        order["courier_name"] = usern

    _save_json(ORDERS_PATH, orders)

    await call.message.answer(f"{notice} ({order_id})")
    await bot.send_message(
        ADMIN_ID, f"🚚 {usern} {notice.lower()}:\nЗаказ {order_id}"
    )

    await show_order_details(call.message, order_id, int(page), call.from_user.id, edit=True)

@dp.callback_query(F.data.startswith("take:"))
async def cb_take(call: CallbackQuery):
    await update_status(call, "taken", "Вы взяли заказ")

@dp.callback_query(F.data.startswith("refuse:"))
async def cb_refuse(call: CallbackQuery):
    await update_status(call, "new", "Вы отказались от заказа")

@dp.callback_query(F.data.startswith("done:"))
async def cb_done(call: CallbackQuery):
    await update_status(call, "done", "Вы завершили заказ")

@dp.callback_query(F.data.startswith("comment:"))
async def cb_comment(call: CallbackQuery):
    await call.answer()
    order_id, page = call.data.split(":")[1:3]
    COMMENT_STATE[call.from_user.id] = (order_id, int(page))
    await call.message.answer(
        "Напишите комментарий:", reply_markup=ForceReply(selective=True)
    )

@dp.message(
    F.reply_to_message.func(lambda m: m and m.text.startswith("Напишите комментарий:"))
)
async def save_comment(message: types.Message):
    state = COMMENT_STATE.pop(message.from_user.id, None)
    if not state:
        return
    order_id, page = state
    comment = message.text.strip()

    orders = _load_json(ORDERS_PATH, [])
    for o in orders:
        if str(o["id"]) == str(order_id):
            o["courier_comment"] = comment
            break
    _save_json(ORDERS_PATH, orders)

    usern = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else str(message.from_user.id)
    )
    await bot.send_message(
        ADMIN_ID, f"💬 {usern} добавил комментарий к {order_id}:\n{comment}"
    )
    await message.answer("Комментарий сохранён.")
    await show_order_details(message, order_id, page, message.from_user.id)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")
