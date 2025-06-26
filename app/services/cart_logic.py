import json
from app.services.data_loader import load_json, save_json

USERS_PATH = "app/storage/users.json"


def get_cart_by_user(user_id: str) -> dict:
    users = load_json(USERS_PATH)
    return users.get(user_id, {}).get("cart", {})


def save_cart_by_user(user_id: str, cart: dict):
    users = load_json(USERS_PATH)
    if user_id not in users:
        users[user_id] = {}
    users[user_id]["cart"] = cart
    save_json(USERS_PATH, users)


def clear_cart_by_user(user_id: str):
    save_cart_by_user(user_id, {})
