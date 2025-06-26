from typing import Optional

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from app.services.data_loader import load_json

templates = Jinja2Templates(directory="app/templates")
router    = APIRouter()

RULES_PATH = "app/storage/user_rules.json"
def load_rules() -> dict:
    import os, json
    return json.load(open(RULES_PATH, "r", encoding="utf-8")) if os.path.exists(RULES_PATH) else {}

@router.get("/ligovckij-prospekt/")
def main(request: Request, user_id: str = ""):
    products = load_json("app/storage/products.json")

    rule     = load_rules().get(str(user_id), {})
    extra    = rule.get("extra", 0)
    discount = rule.get("discount", 0)

    if extra or discount:
        k = (1 + extra / 100) * (1 - discount / 100)
        for p in products:
            p["price"] = round(p["price"] * k)

    news_raw = load_json("app/storage/news.json")
    news     = [{"index": i, **n} for i, n in enumerate(news_raw)]

    return templates.TemplateResponse("index.html", {
        "request": request,
        "products": products,
        "news": news,
        "user_id": user_id,
    })
