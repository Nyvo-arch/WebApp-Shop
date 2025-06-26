from fastapi import APIRouter, Request, Query
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import json, os

from app.services.data_loader import load_json
from app.routes.cart import _load_cart

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

RULES_PATH = "app/storage/user_rules.json"


def load_rules() -> dict:
    return (
        json.load(open(RULES_PATH, "r", encoding="utf-8"))
        if os.path.exists(RULES_PATH)
        else {}
    )

@router.get("/ligovckij-prospekt/news/{index}")
def news_detail(request: Request, index: int, user_id: str = ""):
    news  = load_json("app/storage/news.json")
    cart  = _load_cart(user_id)
    if 0 <= index < len(news):
        return templates.TemplateResponse(
            "news_detail.html",
            {
                "request": request,
                "news":    news[index],
                "cart_count": len(cart),
                "user_id": user_id,
            },
        )
    return RedirectResponse("/ligovckij-prospekt/")

@router.get("/ligovckij-prospekt/product/{product_id}")
def product_detail(
    request: Request,
    product_id: str,
    user_id: str = "",
    modal: bool = Query(False),
):
    products = load_json("app/storage/products.json")
    cart     = _load_cart(user_id)

    for p in products:
        if str(p["id"]) == str(product_id):

            rule     = load_rules().get(str(user_id), {})
            extra    = rule.get("extra", 0)
            discount = rule.get("discount", 0)
            if extra or discount:
                p = p.copy()
                p["price"] = round(
                    p["price"] * (1 + extra / 100) * (1 - discount / 100)
                )

            tmpl = "product_modal.html" if modal else "product_detail.html"
            return templates.TemplateResponse(
                tmpl,
                {
                    "request": request,
                    "product": p,
                    "user_id": user_id,
                    "cart_count": len(cart),
                },
            )

    return RedirectResponse("/ligovckij-prospekt/")
