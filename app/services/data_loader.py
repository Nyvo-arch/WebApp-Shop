import json
import os

def load_json(path):
    if not os.path.exists(path):
        return {} if path.endswith(".json") else []
    with open(path, encoding='utf-8') as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
