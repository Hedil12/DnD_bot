import random
from typing import Annotated
from database import SessionLocal, Character, CampaignLore, GameSave, Party

import random
from typing import Annotated, Optional
from database import SessionLocal, Character, CampaignLore, GameSave

def manage_character_sheet(
    user_id: str, 
    chat_id: str,
    action: Annotated[str, "'read', 'update_stat', or 'add_item'"], 
    stat_name: Optional[str] = None, 
    stat_value: Optional[int] = None,
    item_to_add: Optional[str] = None,
    gold_change: int = 0
) -> str:
    """The primary tool for the DM to interact with player sheets (HP, Gold, Inventory)."""
    db = SessionLocal()
    try:
        # We query by both user and chat to ensure we have the right character for this game
        char = db.query(Character).filter_by(user_id=user_id, chat_id=chat_id).first()
        if not char: 
            return "Character not found. Player must use /lobby first."

        # Make a deep copy to ensure SQLAlchemy detects changes in the JSON field
        current_stats = dict(char.stats)

        # OPTION 1: Just looking at the sheet
        if action == "read":
            return f"Current stats for {char.name}: {current_stats}"
        
        # OPTION 2: Modifying a numeric stat (HP, Level, etc.)
        if action == "update_stat" and stat_name:
            current_stats[stat_name] = stat_value
            char.stats = current_stats
            db.commit()
            return f"Success: {char.name}'s {stat_name} is now {stat_value}."

        # OPTION 3: Adding an item or changing gold
        if action == "add_item":
            if item_to_add:
                if "inventory" not in current_stats:
                    current_stats["inventory"] = []
                current_stats["inventory"].append(item_to_add)
            
            if gold_change != 0:
                current_stats["gold"] = current_stats.get("gold", 0) + gold_change
            
            char.stats = current_stats
            db.commit()
            return f"Updated {char.name}: Added {item_to_add or 'nothing'} and changed gold by {gold_change}."

    except Exception as e:
        return f"Error updating character sheet: {str(e)}"
    finally:
        db.close()
    
    return "Invalid action requested."

def roll_dice(dice: Annotated[str, "e.g., 'd20' or '2d6'"]) -> str:
    """Standard DnD dice rolling tool."""
    parts = dice.lower().split('d')
    count = int(parts[0]) if parts[0] else 1
    sides = int(parts[1])
    results = [random.randint(1, sides) for _ in range(count)]
    return f"🎲 Rolled {dice}: {sum(results)} {results}"

def archive_lore(
    chat_id: str, 
    slot_id: int, 
    event_summary: Annotated[str, "A short, 1-sentence summary of a major plot point (e.g. 'The king was assassinated')"]
) -> str:
    """Saves critical plot points so the DM remembers them in future sessions."""
    db = SessionLocal()
    try:
        new_lore = CampaignLore(
            chat_id=chat_id, 
            slot_id=slot_id, 
            content=event_summary
        )
        db.add(new_lore)
        db.commit()
        return f"Lore archived for Slot {slot_id}: {event_summary}"
    except Exception as e:
        return f"Failed to archive lore: {str(e)}"
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
