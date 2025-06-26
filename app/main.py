from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import json, os, config

from app.routes import pages
from app.routes import cart
from app.routes import admin
from app.routes import shop
from app.routes import orders

app = FastAPI()

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

RULES_PATH = "app/storage/user_rules.json"

def load_rules() -> dict:
    return json.load(open(RULES_PATH, "r", encoding="utf-8")) \
           if os.path.exists(RULES_PATH) else {}

def is_banned(uid: str) -> bool:
    if not uid or str(uid) == str(config.ADMIN_TELEGRAM_ID):
        return False
    return bool(load_rules().get(str(uid), {}).get("ban"))

@app.middleware("http")
async def block_banned_users(request: Request, call_next):
    uid = (request.cookies.get("user_id")
           or request.headers.get("X-User-ID")
           or request.query_params.get("user_id"))

    if is_banned(uid):
        return templates.TemplateResponse(
            "banned.html",
            {"request": request},
            status_code=403
        )

    return await call_next(request)

app.include_router(pages.router)
app.include_router(cart.router)
app.include_router(admin.router)
app.include_router(shop.router)
app.include_router(orders.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
