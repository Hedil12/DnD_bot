# tools.py
import os, json, random, threading
from smolagents import tool

file_lock = threading.Lock()
DB_PATH = "dnd_state.json"

def _load_db():
    if not os.path.exists(DB_PATH):
        with open(DB_PATH, "w") as f:
            json.dump({"characters": {}, "campaign": {"history_summary": "The adventure begins..."}, "settings": {"max_memory": 10}}, f)
    with open(DB_PATH, "r") as f:
        return json.load(f)

def _save_db(data):
    with open(DB_PATH, "w") as f:
        json.dump(data, f, indent=4)

@tool
def manage_character(action: str, name: str, attribute: str = None, value: str = None) -> str:
    """Manages player character sheets (HP, Gold, Inventory)."""
    with file_lock:
        data = _load_db()
        chars = data.get("characters", {})
        if action == "create":
            chars[name] = {"hp": 20, "gold": 10, "inventory": "Basic Gear"}
        elif action == "read":
            if name not in chars: return "No character found."
            c = chars[name]
            return f"{name}: HP {c['hp']}, Gold {c['gold']}, Items: {c['inventory']}"
        elif action == "update" and name in chars:
            chars[name][attribute] = value
        _save_db(data)
    return f"Character {name} {action}ed."

@tool
def manage_campaign(action: str, key: str = "history_summary", value: str = None) -> str:
    """Stores/Reads world notes. Use key='history_summary' for the main story arc."""
    with file_lock:
        data = _load_db()
        if action == "update":
            data["campaign"][key] = value
            _save_db(data)
            return "World record updated."
        return data["campaign"].get(key, "No notes found.")

@tool
def roll_dice(dice: str) -> str:
    """Rolls dice (e.g., 'd20')."""
    try:
        res = random.randint(1, int(dice.lower().replace("d", "")))
        return f"🎲 Result: {res}"
    except: return "Error: Use 'd20'."