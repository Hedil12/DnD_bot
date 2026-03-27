# memory.py
from database import SessionLocal, GameSave
import logging

def get_summary(chat_id):
    db = SessionLocal()
    save = db.query(GameSave).filter_by(chat_id=chat_id).first()
    logging.info(f"🔍 Retrieved game summary for {chat_id}: {save.summary if save else 'No summary found'}")
    db.close()
    if save and save.summary:
        return save.summary
    return "The journey has just begun. The players are at the start of their quest."

def update_summary(chat_id, new_summary):
    db = SessionLocal()
    save = db.query(GameSave).filter_by(chat_id=chat_id).first()
    if not save:
        save = GameSave(chat_id=chat_id, summary=new_summary)
        db.add(save)
        logging.info(f"📜 New game save created for {chat_id}")
    else:
        save.summary = new_summary
        logging.info(f"📜 Game summary updated for {chat_id}")
    db.commit()
    db.close()