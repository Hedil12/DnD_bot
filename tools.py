import random
from typing import Annotated
from database import SessionLocal, Character, CampaignLore, GameSave, Party

def manage_character_sheet(
    user_id: str, 
    action: Annotated[str, "'read' or 'update'"], 
    stat: str = None, 
    value: int = None
) -> str:
    """Read or modify player HP, Gold, or Level in the database."""
    db = SessionLocal()
    try:
        char = db.query(Character).filter(Character.user_id == user_id).first()
        if not char: return "Character not found. Use /join first."

        if action == "read":
            return f"{char.name}'s Status: {char.stats}"
        
        if action == "update" and stat in char.stats:
            char.stats[stat] = value
            db.commit()
            return f"Success: {char.name}'s {stat} is now {value}."
    finally:
        db.close()
    return "Invalid action."

def roll_dice(dice: Annotated[str, "e.g., 'd20' or '2d6'"]) -> str:
    """Standard DnD dice rolling tool."""
    parts = dice.lower().split('d')
    count = int(parts[0]) if parts[0] else 1
    sides = int(parts[1])
    results = [random.randint(1, sides) for _ in range(count)]
    return f"🎲 Rolled {dice}: {sum(results)} {results}"

def archive_lore(event_summary: Annotated[str, "A short summary of what just happened"]) -> str:
    """Saves important plot points to the permanent Postgres memory."""
    db = SessionLocal()
    try:
        new_lore = CampaignLore(content=event_summary)
        db.add(new_lore)
        db.commit()
        return "The archives have been updated with this event."
    finally:
        db.close()

def save_session_state(chat_id: str, summary: str) -> str:
    """Saves the current world state into the Postgres GameSave table."""
    db = SessionLocal()
    save = db.query(GameSave).filter_by(chat_id=chat_id).first()
    if not save:
        save = GameSave(chat_id=chat_id, save_data={"summary": summary})
        db.add(save)
    else:
        save.save_data = {"summary": summary}
    db.commit()
    return "Game progress successfully uploaded to the Cloud SQL archives."

def load_session_state(chat_id: str) -> str:
    """Retrieves the last save file to continue the story."""
    db = SessionLocal()
    save = db.query(GameSave).filter_by(chat_id=chat_id).first()
    return save.save_data["summary"] if save else "No previous save found."