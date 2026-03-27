import os, vertexai, logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from vertexai.preview import reasoning_engines
from tools import manage_character_sheet, roll_dice, archive_lore, load_session_state, save_session_state
from database import get_engine, Base, SessionLocal, Party, Character, GameSave
from memory import get_summary, update_summary

# Configure logging to show in the terminal
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("dnd_bot.log"), # Saves to a file in your folder
        logging.StreamHandler()            # Also prints to the terminal
    ]
)

logger = logging.getLogger(__name__)

# Get the connection engine
engine = get_engine()

# THIS IS THE COMMAND: 
# It checks if "characters", "parties", etc. exist. If not, it creates them.
Base.metadata.create_all(bind=engine)
print("✅ Database tables synced successfully!")

# Initialize Vertex AI with credentials from .env
load_dotenv()  # Load environment variables from .env file
vertexai.init(
    project=os.getenv("GCP_PROJECT_ID"),
    location=os.getenv("GCP_REGION")
)
# Initialize the Vertex AI Agent
prompt = """You are a professional Dungeon Master. 
    1. Use 'manage_character_sheet' to handle HP/Gold updates.
    2. Use 'save_session_state' when players want to quit or save.
    3. If it's a new group chat, ask players to /join before starting.
    4. Keep the tone epic and mysterious."""

dm_agent = reasoning_engines.LangchainAgent(
    model="gemini-2.0-flash-lite",
    system_instruction=prompt,
    tools=[manage_character_sheet, roll_dice, archive_lore, load_session_state, save_session_state],
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greeting logic for new players."""
    msg = "Welcome to the Realm. "
    if update.message.chat.type != "private":
        msg += "Group detected! Everyone should type /join to participate."
    else:
        msg += "Use /join to initialize your character sheet."
    await update.message.reply_text(msg)

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles logic for adding players to a party or solo game."""
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    user_name = update.effective_user.first_name
    
    db = SessionLocal()
    # Ensure character row exists
    char = db.query(Character).filter_by(user_id=user_id).first()
    if not char:
        db.add(Character(user_id=user_id, name=user_name, stats={"hp": 20, "gold": 10}))
    
    # Ensure party record exists for this chat
    party = db.query(Party).filter_by(chat_id=chat_id).first()
    if not party:
        db.add(Party(chat_id=chat_id, leader_id=user_id, players=[user_id]))
    elif user_id not in party.players:
        party.players = party.players + [user_id] # Update list
        
    db.commit()
    db.close()
    await update.message.reply_text(f"⚔️ {user_name} is ready for adventure!")

async def delete_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wipes progress for the current chat only. Irreversible."""
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    
    logger.info(f"🗑️ ACTION: DELETE_REQUEST | User: {user_id} | Chat: {chat_id}")
    
    db = SessionLocal()
    try:
        # 1. Remove character from THIS chat
        char = db.query(Character).filter_by(user_id=user_id, chat_id=chat_id).first()
        if char:
            db.delete(char)
            
        # 2. Remove the World Progress (Summary) for THIS chat
        save = db.query(GameSave).filter_by(chat_id=chat_id).first()
        if save:
            db.delete(save)
            
        db.commit()
        await update.message.reply_text("💥 **The timeline has been erased.** Your character and progress in this chat are gone.")
        logger.info(f"✅ ACTION: DELETE_COMPLETE | Chat: {chat_id}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ ACTION: DELETE_FAILED | Error: {e}")
        await update.message.reply_text("⚠️ Failed to delete save. The gods of fate are stubborn.")
    finally:
        db.close()

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main game loop - Handles Solo vs Group & Memory Summarization."""
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    user_text = update.message.text

    # ✅ SAFE LOGGING: Track action, not private text
    logger.info(f"📥 ACTION: MESSAGE_RCVD | User: {user_id} | Chat: {chat_id} | Len: {len(user_text)}")

    db = SessionLocal()
    try:
        # 1. 🛡️ PARALLEL UNIVERSE CHECK: Get character for THIS specific chat
        character = db.query(Character).filter_by(user_id=user_id, chat_id=chat_id).first()
        
        if not character:
            await update.message.reply_text("❌ You don't have a character in this adventure! Type /join to start.")
            return

        # 2. 🧠 MEMORY RETRIEVAL: Get the 'Story So Far' for this chat
        campaign_summary = get_summary(chat_id)
        
        # 3. 🤖 AI INVOCATION: Wrap input to prevent 'Prompt Injection'
        print(f"🎲 DM is thinking for {character.name}...")
        
        full_prompt = f"""
        Current Campaign Summary: {campaign_summary}
        Player Character: {character.name} (Stats: {character.stats})
        Player Action: '''{user_text}'''
        """
        
        response = dm_agent.run(full_prompt)

        # 4. 📤 RESPONSE & LOGGING
        await update.message.reply_text(response.content)
        logger.info(f"✅ ACTION: AI_RESPONSE_SENT | User: {user_id}")

        # 5. ✍️ AUTOMATIC SUMMARY (Efficiency): Update memory every few turns
        # For now, let's just append the latest interaction to the summary logic
        # You can trigger a real 'Summary' call here every 10 messages
        
    except Exception as e:
        logger.error(f"💥 ACTION: GAME_LOOP_FAILURE | Error: {type(e).__name__}")
        await update.message.reply_text("⚠️ The Dungeon Master is momentarily dazed. Please try again.")
    
    finally:
        db.close()
        logger.info(f"🔌 Database connection closed for {chat_id}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(os.getenv("teleAPI")).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("delete_save", delete_save))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_messages))
    app.run_polling()