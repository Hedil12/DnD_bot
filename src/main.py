import os, vertexai, logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from vertexai.preview import reasoning_engines
from tools import manage_character_sheet, roll_dice, archive_lore, load_session_state, save_session_state
from database import get_engine, Base, SessionLocal, Character, GameSave
from memory import get_summary, update_summary

# 1. 🛡️ SECURITY: LOGGING & TOKEN REDACTION
load_dotenv()
TELE_TOKEN = os.getenv("teleAPI")

class RedactTokenFilter(logging.Filter):
    def filter(self, record):
        if TELE_TOKEN and isinstance(record.msg, str):
            record.msg = record.msg.replace(TELE_TOKEN, "[REDACTED_TOKEN]")
        return True

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("dnd_bot.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)
logger.addFilter(RedactTokenFilter())

# Mute noisy library logs that leak URLs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

# 2. DATABASE SYNC
engine = get_engine()
Base.metadata.create_all(bind=engine)

# 3. VERTEX AI AGENT SETUP
vertexai.init(project=os.getenv("GCP_PROJECT_ID"), location=os.getenv("GCP_REGION"))

dm_instruction = """You are a professional Dungeon Master. 
1. Use 'manage_character_sheet' for HP/Gold changes.
2. If players act, describe the outcome based on 'roll_dice'.
3. Always refer to the 'Current Campaign Summary' for continuity."""

dm_agent = reasoning_engines.LangchainAgent(
    model="gemini-2.0-flash-lite",
    system_instruction=dm_instruction,
    tools=[manage_character_sheet, roll_dice, archive_lore, load_session_state, save_session_state],
)

# --- COMMANDS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✨ **Welcome to the Realm.** ✨\n\n"
        "1. Join lobby: `/lobby [Name]`\n"
        "2. Start story: `/start_game`",
        parse_mode="Markdown"
    )

async def lobby(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    user_name = " ".join(context.args) if context.args else update.effective_user.first_name
    
    db = SessionLocal()
    char = db.query(Character).filter_by(user_id=user_id, chat_id=chat_id).first()
    if not char:
        db.add(Character(user_id=user_id, chat_id=chat_id, name=user_name, stats={"hp": 20, "gold": 10}))
        db.commit()
        await update.message.reply_text(f"⚔️ {user_name} joined the lobby!")
    else:
        await update.message.reply_text(f"🛡️ {char.name}, you're already here.")
    db.close()

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    db = SessionLocal()
    players = db.query(Character).filter_by(chat_id=chat_id).all()
    
    if not players:
        await update.message.reply_text("⚠️ Use /lobby to join first.")
        return

    player_list = ", ".join([p.name for p in players])
    # ✅ FIX: Use .query() instead of .run()
    response = dm_agent.query(input=f"The party is {player_list}. Start an epic D&D intro.")
    
    update_summary(chat_id, response["output"])
    await update.message.reply_text(f"🎭 **BEGIN** 🎭\n\n{response['output']}")
    db.close()

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    
    db = SessionLocal()
    char = db.query(Character).filter_by(user_id=user_id, chat_id=chat_id).first()
    
    if not char:
        await update.message.reply_text("❌ Join the lobby first!")
        return

    campaign_summary = get_summary(chat_id) or "The adventure has just begun."
    
    try:
        # ✅ FIX: Use .query() for LangchainAgent
        response = dm_agent.query(input=f"Summary: {campaign_summary}\nPlayer ({char.name}): {update.message.text}")
        await update.message.reply_text(response["output"])
    except Exception as e:
        logger.error(f"Gameplay Error: {e}")
        await update.message.reply_text("⚠️ The DM is thinking too hard. Try again.")
    finally:
        db.close()

async def delete_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    db = SessionLocal()
    db.query(Character).filter_by(chat_id=chat_id).delete()
    db.query(GameSave).filter_by(chat_id=chat_id).delete()
    db.commit()
    db.close()
    await update.message.reply_text("💥 Reset complete.")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELE_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("lobby", lobby))
    app.add_handler(CommandHandler("start_game", start_game))
    app.add_handler(CommandHandler("delete_save", delete_save))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_messages))
    logger.info("🤖 Bot live and redacted.")
    app.run_polling()