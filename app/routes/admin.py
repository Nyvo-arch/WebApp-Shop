from typing import Optional

from fastapi import APIRouter, Request, Form, UploadFile, File, Query
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.services.data_loader import load_json, save_json
from uuid import uuid4
import config, os

router     = APIRouter()
templates  = Jinja2Templates(directory="app/templates")
ADMIN_PATH = "/ligovckij-prospekt/__admin_hidden_qwErTY456"

CAT_PATH   = "app/storage/categories.json"
RULES_PATH = "app/storage/user_rules.json"

os.makedirs("app/storage", exist_ok=True)


def save_uploaded(f: UploadFile, prefix: str, folder: str) -> str:
    ext  = os.path.splitext(f.filename)[-1]
    name = f"{prefix}_{uuid4().hex[:8]}{ext}"
    path = f"app/static/{folder}/{name}"
    with open(path, "wb") as fp:
        fp.write(f.file.read())
    return f"/static/{folder}/{name}"


def is_admin(uid: str) -> bool:
    return str(uid) == str(config.ADMIN_TELEGRAM_ID)

def load_cats() -> list:
    return load_json(CAT_PATH) if os.path.exists(CAT_PATH) else [
        "одноразки", "жидкости", "под-системы", "аксессуары"
    ]


def save_cats(cats: list):
    save_json(CAT_PATH, cats)

def load_rules() -> dict:
    return load_json(RULES_PATH) if os.path.exists(RULES_PATH) else {}


def save_rules(data: dict):
    save_json(RULES_PATH, data)

@router.get(ADMIN_PATH)
def admin_panel(request: Request, user_id: str = "", search_uid: str = ""):
    if not is_admin(user_id):
        return RedirectResponse("/ligovckij-prospekt/")

    products   = load_json("app/storage/products.json")
    news_raw   = load_json("app/storage/news.json")
    orders     = load_json("app/storage/orders.json")
    schedule   = load_json("app/storage/schedule.json")
    categories = load_cats()

    rules      = load_rules()
    user_rule  = rules.get(str(search_uid), {}) if search_uid else {}

    news = [{"index": i, **n} for i, n in enumerate(news_raw)]
    return templates.TemplateResponse("admin.html", {
        "request":    request,
        "user_id":    user_id,
        "products":   products,
        "news":       news,
        "orders":     orders,
        "categories": categories,
        "schedule":   schedule,
        "search_uid": search_uid,
        "user_rule":  user_rule
    })

@router.post("/ligovckij-prospekt/admin/set-user-rule")
def set_user_rule(
    user_id:    str            = Form(...),
    target_uid: str            = Form(...),
    ban:        Optional[str]  = Form(None),
    extra:      Optional[str]  = Form(None),
    discount:   Optional[str]  = Form(None),
):
    if not is_admin(user_id):
        return RedirectResponse("/ligovckij-prospekt/")

    rules = load_rules()
    rule  = rules.get(str(target_uid), {})

    rule["ban"] = bool(ban)

    if extra and extra.strip():
        try:
            rule["extra"] = max(0, min(100, int(extra)))
        except ValueError:
            pass
    else:
        rule.pop("extra", None)

    if discount and discount.strip():
        try:
            rule["discount"] = max(0, min(100, int(discount)))
        except ValueError:
            pass
    else:
        rule.pop("discount", None)

    rules[str(target_uid)] = rule
    save_rules(rules)

    return RedirectResponse(
        f"{ADMIN_PATH}?user_id={user_id}&search_uid={target_uid}", 302
    )

@router.post("/ligovckij-prospekt/admin/add-category")
def add_category(user_id: str = Form(...), name: str = Form(...)):
    if not is_admin(user_id):
        return RedirectResponse("/ligovckij-prospekt/")
    cats = load_cats()
    if name and name not in cats:
        cats.append(name)
        save_cats(cats)
    return RedirectResponse(f"{ADMIN_PATH}?user_id={user_id}", 302)


@router.post("/ligovckij-prospekt/admin/rename-category")
def rename_category(user_id: str = Form(...), old: str = Form(...), new: str = Form(...)):
    if not is_admin(user_id):
        return RedirectResponse("/ligovckij-prospekt/")
    cats = load_cats()
    if old in cats and new and new not in cats:
        cats[cats.index(old)] = new
        save_cats(cats)
    return RedirectResponse(f"{ADMIN_PATH}?user_id={user_id}", 302)


@router.get("/ligovckij-prospekt/admin/delete-category")
def delete_category(user_id: str = Query(...), name: str = Query(...)):
    if not is_admin(user_id):
        return RedirectResponse("/ligovckij-prospekt/")
    cats = [c for c in load_cats() if c != name]
    save_cats(cats)
    return RedirectResponse(f"{ADMIN_PATH}?user_id={user_id}", 302)

@router.post("/ligovckij-prospekt/admin/add-product")
async def add_product(
    user_id: str = Form(...),
    title: str = Form(...),
    category: str = Form(...),
    price: int = Form(...),
    description: str = Form(...),
    old_price: str = Form(""),
    image: UploadFile = File(...),
    flavors: str = Form("")
):
    if not is_admin(user_id):
        return RedirectResponse("/ligovckij-prospekt/")

    img_path = save_uploaded(image, "product", "products")
    products = load_json("app/storage/products.json")

    products.append({
        "id": str(uuid4())[:8],
        "title": title,
        "category": category,
        "price": price,
        "old_price": int(old_price) if old_price.strip() else None,
        "description": description,
        "image": img_path,
        "flavors": [f.strip() for f in flavors.split(",") if f.strip()]
    })
    save_json("app/storage/products.json", products)

    cats = load_cats()
    if category not in cats:
        cats.append(category)
        save_cats(cats)

    return RedirectResponse(f"{ADMIN_PATH}?user_id={user_id}", 302)

@router.post("/ligovckij-prospekt/admin/edit-product")
async def edit_product(
    user_id: str = Form(...),
    product_id: str = Form(...),
    title: str = Form(...),
    category: str = Form(...),
    price: int = Form(...),
    old_price: str = Form(""),
    description: str = Form(...),
    flavors: str = Form(""),
    image: UploadFile = File(None)
):
    if not is_admin(user_id):
        return RedirectResponse("/ligovckij-prospekt/")

    products = load_json("app/storage/products.json")
    for p in products:
        if str(p["id"]) == str(product_id):
            p.update({
                "title": title,
                "category": category,
                "price": price,
                "old_price": int(old_price) if old_price.strip() else None,
                "description": description,
                "flavors": [f.strip() for f in flavors.split(",") if f.strip()]
            })
            if image:
                p["image"] = save_uploaded(image, "product", "products")
            break
    save_json("app/storage/products.json", products)
    return RedirectResponse(f"{ADMIN_PATH}?user_id={user_id}", 302)

@router.post("/ligovckij-prospekt/admin/add-news")
async def add_news(
    user_id: str = Form(...),
    title: str = Form(...),
    text:  str = Form(...),
    cover: UploadFile = File(...),
    image: UploadFile = File(...)
):
    if not is_admin(user_id):
        return RedirectResponse("/ligovckij-prospekt/")

    cover_path = save_uploaded(cover, "cover", "news")
    img_path   = save_uploaded(image, "news",  "news")

    news = load_json("app/storage/news.json")
    news.insert(0, {
        "title": title,
        "text":  text,
        "cover": cover_path,
        "image": img_path
    })
    save_json("app/storage/news.json", news)
    return RedirectResponse(f"{ADMIN_PATH}?user_id={user_id}", 302)

@router.get("/ligovckij-prospekt/admin/delete-product")
def delete_product(id: str = Query(...), user_id: str = Query(...)):
    if not is_admin(user_id):
        return RedirectResponse("/ligovckij-prospekt/")

    products = [p for p in load_json("app/storage/products.json") if str(p["id"]) != str(id)]
    save_json("app/storage/products.json", products)
    return RedirectResponse(f"{ADMIN_PATH}?user_id={user_id}", 302)


@router.get("/ligovckij-prospekt/admin/delete-news")
def delete_news(index: int = Query(...), user_id: str = Query(...)):
    if not is_admin(user_id):
        return RedirectResponse("/ligovckij-prospekt/")

    news = load_json("app/storage/news.json")
    if 0 <= index < len(news):
        news.pop(index)
        save_json("app/storage/news.json", news)
    return RedirectResponse(f"{ADMIN_PATH}?user_id={user_id}", 302)

@router.post("/ligovckij-prospekt/admin/set-schedule")
def set_schedule(
    user_id: str = Form(...),
    pickup_times: str = Form(""),
    delivery_times: str = Form(""),
):
    if not is_admin(user_id):
        return RedirectResponse("/ligovckij-prospekt/")

    schedule = {
        "pickup":   [t.strip() for t in pickup_times.split(",") if t.strip()],
        "delivery": [t.strip() for t in delivery_times.split(",") if t.strip()],
    }
    save_json("app/storage/schedule.json", schedule)
    return RedirectResponse(f"{ADMIN_PATH}?user_id={user_id}", 302)
