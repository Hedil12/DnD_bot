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

dm_instruction = """You are an elite, world-class Dungeon Master. 
Your goal is to provide a high-fantasy, immersive D&D experience.

NARRATION RULES:
1. SENSORY DETAILS: Describe the smells (damp stone, pine needles), sounds (clanking armor, distant howling), and sights (flickering torches, long shadows).
2. TONE: Be mysterious, epic, and slightly dangerous.
3. PACING: After describing a scene, always end with a clear prompt: "What do you do?" or "How do you proceed?"
4. CHARACTER KNOWLEDGE: Refer to players by their names and mention their specific gear or stats.

TECHNICAL RULES:
1. Use 'manage_character_sheet' for any HP or Gold changes.
2. Use 'roll_dice' for any checks (Stealth, Perception, Combat).
3. Read the 'Current Campaign Summary' to ensure the story stays consistent across sessions."""

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
    
    try:
        players = db.query(Character).filter_by(chat_id=chat_id).all()
        if not players:
            await update.message.reply_text("⚠️ The lobby is empty! Everyone should type /lobby first.")
            return

        # 🎭 The "DM Hook" Prompt
        player_names = ", ".join([p.name for p in players])
        opening_query = (
            f"The adventure begins with these heroes: {player_names}. "
            "Write a 2-paragraph cinematic opening scene. Describe the environment's "
            "sights, sounds, and smells. End by asking the party what they do first."
        )
        
        # ✅ Using .query() now that langchain is installed
        response = dm_agent.query(input=opening_query)
        
        # Save this to the database so handle_messages knows the context
        update_summary(chat_id, response["output"])
        
        await update.message.reply_text(f"🎭 **THE CHRONICLES BEGIN** 🎭\n\n{response['output']}")
        
    except Exception as e:
        logger.error(f"🎬 Start Game Error: {e}")
        await update.message.reply_text("⚠️ The mists of time are too thick to peer through (AI Error). Try /start_game again.")
    finally:
        db.close()

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    user_text = update.message.text

    # Log the action without the raw message if you want maximum privacy
    logger.info(f"📥 MSG from {user_id} in {chat_id}")

    db = SessionLocal()
    try:
        character = db.query(Character).filter_by(user_id=user_id, chat_id=chat_id).first()
        if not character:
            await update.message.reply_text("❌ You aren't in this adventure! Use /lobby [Name].")
            return

        campaign_summary = get_summary(chat_id) or "A new group of adventurers stands at the threshold of destiny."
        
        # 🤖 The Core AI Call
        # We pass the summary and the character's current status so the AI knows who is talking
        input_str = f"Summary: {campaign_summary}\nPlayer: {character.name} (Stats: {character.stats})\nAction: {user_text}"
        
        response = dm_agent.query(input=input_str)
        
        # Send the "Dungeon Master" response back to Telegram
        await update.message.reply_text(response["output"])
        
    except Exception as e:
        # This will catch that .run vs .query error specifically
        logger.error(f"💥 Gameplay Error: {type(e).__name__} - {e}")
        await update.message.reply_text("⚠️ The DM is consulting the rulebooks (AI Error). Please try your action again.")
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