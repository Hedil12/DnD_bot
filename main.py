import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from vertexai.preview import reasoning_engines
from tools import manage_character_sheet, roll_dice, archive_lore, load_session_state, save_session_state
from database import SessionLocal, Party, Character
import vertexai

# Initialize Vertex AI with credentials from .env
vertexai.init(
    project=os.getenv("GCP_PROJECT_ID"), # e.g., "my-dnd-project-123"
    location=os.getenv("GCP_REGION")      # e.g., "us-central1"
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
    """Main game loop - only responds to joined players."""
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    
    db = SessionLocal()
    party = db.query(Party).filter_by(chat_id=chat_id).first()
    
    # Check if the player is part of the game
    if party and user_id in party.players:
        # Pass context to Gemini
        history = load_session_state(chat_id)
        response = dm_agent.run(f"Context: {history}\nPlayer ({user_id}): {update.message.text}")
        await update.message.reply_text(response.content)
    db.close()

if __name__ == "__main__":
    app = ApplicationBuilder().token(os.getenv("TELEGRAM_TOKEN")).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_messages))
    app.run_polling()