import os, vertexai, logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from vertexai.preview import reasoning_engines
from tools import manage_character_sheet, roll_dice, archive_lore, load_session_state, save_session_state
from database import get_engine, Base, SessionLocal, Party, Character

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

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main game loop - with terminal progress tracking."""
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    user_text = update.message.text

    # 1. Track incoming message in terminal
    logger.info(f"📬 [Chat: {chat_id}] Message from Player {user_id}: {user_text}")
    
    db = SessionLocal()
    try:
        party = db.query(Party).filter_by(chat_id=chat_id).first()
        
        # Check if the player is part of the game
        if party and user_id in party.players:
            print(f"🎲 DM is processing turn for Player {user_id}...") 
            
            # Load context
            history = load_session_state(chat_id)
            
            # 2. Track AI Start
            logger.info(f"🤖 Sending to Gemini for Chat {chat_id}...")
            
            # Pass context to Gemini
            response = dm_agent.run(f"Context: {history}\nPlayer ({user_id}): {user_text}")
            
            # 3. Track AI Success
            logger.info(f"✅ Gemini responded successfully.")
            await update.message.reply_text(response.content)
        else:
            logger.warning(f"⚠️ Unauthorized message from {user_id} in chat {chat_id}")

    except Exception as e:
        # 4. Critical Error Logging
        logger.error(f"💥 CRITICAL ERROR in handle_messages: {e}", exc_info=True)
        await update.message.reply_text("⚠️ The weave of magic is flickering. (Internal Server Error)")
    
    finally:
        db.close()
        logger.info(f"🔌 Database connection closed for {chat_id}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(os.getenv("teleAPI")).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_messages))
    app.run_polling()