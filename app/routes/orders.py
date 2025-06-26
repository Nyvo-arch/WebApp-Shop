from datetime import datetime
import os
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from aiogram import Bot
from app.services.data_loader import load_json, save_json
from app.routes.cart import _load_cart, _save_cart
import config

router    = APIRouter()
templates = Jinja2Templates(directory="app/templates")

ORD_PATH   = "app/storage/orders.json"
RULES_PATH = "app/storage/user_rules.json"
SCHED_PATH = "app/storage/schedule.json"
USERS_PATH = "app/storage/users.json"
os.makedirs("app/storage", exist_ok=True)

bot   = Bot(token=config.TELEGRAM_BOT_TOKEN)
ADMIN = config.ADMIN_TELEGRAM_ID

def orders_load() -> list:
    return load_json(ORD_PATH) if os.path.exists(ORD_PATH) else []


def orders_save(data: list):
    save_json(ORD_PATH, data)


def load_rules() -> dict:
    return load_json(RULES_PATH) if os.path.exists(RULES_PATH) else {}


def load_schedule() -> dict:
    return load_json(SCHED_PATH) if os.path.exists(SCHED_PATH) else {"pickup": [], "delivery": []}

@router.get("/ligovckij-prospekt/checkout")
def checkout_form(request: Request, user_id: str = ""):
    if not _load_cart(user_id):
        return RedirectResponse(f"/ligovckij-prospekt/cart?user_id={user_id}", status_code=302)

    return templates.TemplateResponse(
        "checkout.html",
        {
            "request": request,
            "user_id": user_id,
            "schedule": load_schedule(),
        },
    )

@router.post("/ligovckij-prospekt/checkout")
async def checkout(
    user_id: str = Form(...),
    name: str = Form(...),
    phone: str = Form(...),
    address: str = Form(...),
    comment: str = Form(""),
    delivery_type: str = Form(...),
    delivery_option: str = Form(""),
    station: str = Form(""),
    time: str = Form(...),
):
    cart = _load_cart(user_id)
    if not cart:
        return RedirectResponse(f"/ligovckij-prospekt/cart?user_id={user_id}", status_code=302)

    products = {p["id"]: p for p in load_json("app/storage/products.json")}

    rule = load_rules().get(str(user_id), {})

    if rule.get("ban"):
        return RedirectResponse(f"/ligovckij-prospekt/?user_id={user_id}", status_code=302)

    extra     = rule.get("extra", 0) or 0
    discount  = rule.get("discount", 0) or 0

    items: list[dict] = []
    total: int = 0
    for key, qty in cart.items():
        prod_id, _, flavor = key.partition(":")
        prod = products.get(prod_id)
        if not prod:
            continue

        base_price = prod["price"]
        real_price = round(base_price * (1 + extra / 100) * (1 - discount / 100))

        items.append({
            "title": prod["title"],
            "flavor": flavor or None,
            "qty": qty,
            "price": real_price,
        })
        total += real_price * qty

    order_id = str(len(orders_load()) + 1)
    created  = datetime.now().strftime("%d.%m.%Y %H:%M")

    order = {
        "id": order_id,
        "user_id": user_id,
        "items": items,
        "total": total,
        # данные клиента
        "name": name,
        "phone": phone,
        "address": address,
        "customer_comment": comment,
        # служебное
        "created": created,
        "delivery_type": delivery_type,
        "delivery_option": delivery_option,
        "station": station,
        "time": time,
        # для курьера
        "status": "new",
        "courier_id": None,
        "courier_name": "",
        "courier_comment": "",
    }

    data = orders_load()
    data.append(order)
    orders_save(data)
    users = load_json(USERS_PATH)
    username = users.get(str(user_id), {}).get("username")

    summary_lines = [
        f"📦 <b>Новый заказ №{order_id}</b> ({created})",
        *(f"• {i['title']} ×{i['qty']}" + (f" ({i['flavor']})" if i['flavor'] else "") for i in items),
        f"<b>Сумма: {total} ₽</b>",
        f"ID клиента: <code>{user_id}</code>",
        f"Username: @{username}" if username else "Username: —",
        f"Имя: {name}",
        f"Телефон: {phone}",
        f"Адрес: {address}",
        f"Комментарий: {comment or '-'}",
        "",
        "Тип: " + ("Доставка" if delivery_type == "delivery" else "Самовывоз"),
        f"Метро: {station}" if delivery_type == "delivery" else "Самовывоз",
        f"Когда: {time}",
        (f"Вариант: {delivery_option.replace('_', ' ')}" if delivery_type == "delivery" else ""),
        "",
        f"Наценка: {extra}%  Скидка: {discount}%" if (extra or discount) else "",
    ]

    try:
        await bot.send_message(ADMIN, "\n".join(filter(None, summary_lines)), parse_mode="HTML")
    except Exception:
        pass
    try:
        buyer_msg = "\n".join([
            f"🧾 <b>Ваш заказ №{order_id} оформлен!</b>",
            f"🛍️ <b>Сумма:</b> {total} ₽",
            f"📦 <b>Тип:</b> {'Доставка' if delivery_type == 'delivery' else 'Самовывоз'}",
            f"📅 <b>Когда:</b> {time}",
            f"📍 <b>Адрес:</b> {address}" if delivery_type == "delivery" else f"📍 <b>Точка самовывоза:</b> {station}",
            "",
            "Мы свяжемся с вами для подтверждения. Спасибо за заказ ❤️"
        ])
        await bot.send_message(user_id, buyer_msg, parse_mode="HTML")
    except Exception:
        pass
    _save_cart(user_id, {})

    return RedirectResponse(f"/ligovckij-prospekt/account?user_id={user_id}", status_code=302)

@router.get("/ligovckij-prospekt/account")
def account(request: Request, user_id: str = ""):
    user_orders = [o for o in orders_load() if str(o["user_id"]) == str(user_id)]
    users = load_json(USERS_PATH) if os.path.exists(USERS_PATH) else {}
    user = users.get(str(user_id), {})

    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "orders": user_orders,
            "user_id": user_id,
            "user": user,
        },
    )
