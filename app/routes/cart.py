from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from app.services.data_loader import load_json, save_json
from typing import List, Optional
import os

router    = APIRouter()
templates = Jinja2Templates(directory="app/templates")

CART_DIR = "app/storage/carts"
os.makedirs(CART_DIR, exist_ok=True)

RULES_PATH = "app/storage/user_rules.json"

def load_rules() -> dict:
    return load_json(RULES_PATH) if os.path.exists(RULES_PATH) else {}

def _cart_path(uid: str) -> str:
    return f"{CART_DIR}/{uid}.json"

def _load_cart(uid: str) -> dict:
    path = _cart_path(uid)
    if os.path.exists(path):
        return load_json(path)
    return {}

def _save_cart(uid: str, data: dict):
    save_json(_cart_path(uid), data)

@router.post("/ligovckij-prospekt/add-to-cart")
def add_to_cart(
    user_id:    str              = Form(...),
    product_id: str              = Form(...),
    flavors:    Optional[List[str]] = Form(None)
):
    if not user_id:
        return {"ok": False, "msg": "no user"}

    cart = _load_cart(user_id)

    if not flavors:
        key = f"{product_id}:"
        cart[key] = cart.get(key, 0) + 1
    else:
        for fl in flavors:
            key = f"{product_id}:{fl}"
            cart[key] = cart.get(key, 0) + 1

    _save_cart(user_id, cart)
    return {"ok": True, "count": sum(cart.values())}

@router.get("/ligovckij-prospekt/cart/count")
def cart_count(user_id: str):
    return {"count": sum(_load_cart(user_id).values())}

@router.get("/ligovckij-prospekt/cart")
def view_cart(request: Request, user_id: str):
    cart_raw = _load_cart(user_id)
    products = load_json("app/storage/products.json")
    pmap     = {p["id"]: p for p in products}

    rule   = load_rules().get(str(user_id), {})
    extra  = rule.get("extra", 0)
    discount = rule.get("discount", 0)

    items, total = [], 0
    for key, qty in cart_raw.items():
        prod_id, _, flavor = key.partition(":")
        prod = pmap.get(prod_id)
        if not prod:
            continue

        price = prod["price"]
        if extra or discount:
            price = round(price * (1 + extra / 100) * (1 - discount / 100))

        subtotal = price * qty
        total   += subtotal
        items.append({
            "key": key,
            "id": prod_id,
            "title": prod["title"],
            "image": prod.get("image", "/static/img/placeholder.jpg"),
            "flavor": flavor or None,
            "qty": qty,
            "price": price,
            "subtotal": subtotal
        })

    return templates.TemplateResponse("cart.html", {
        "request": request,
        "user_id": user_id,
        "items": items,
        "total": total
    })

@router.post("/ligovckij-prospekt/cart/update")
def cart_update(user_id: str = Form(...),
                key: str     = Form(...),
                qty: int     = Form(...)):
    cart = _load_cart(user_id)
    if qty <= 0:
        cart.pop(key, None)
    else:
        cart[key] = qty
    _save_cart(user_id, cart)
    return RedirectResponse(f"/ligovckij-prospekt/cart?user_id={user_id}", 302)

@router.post("/ligovckij-prospekt/cart/clear")
def cart_clear(user_id: str = Form(...)):
    _save_cart(user_id, {})
    return RedirectResponse(f"/ligovckij-prospekt/cart?user_id={user_id}", 302)
