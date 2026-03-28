import os, vertexai, logging
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, MessageHandler, filters, ContextTypes
from vertexai.preview import reasoning_engines
from tools import manage_character_sheet, roll_dice, archive_lore, load_session_state, save_session_state
from database import CampaignLore, get_engine, Base, SessionLocal, Character, GameSave
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

TECHNICAL RULES (STRICT COMPLIANCE):
1. USE 'roll_dice' for ANY action with a chance of failure. You MUST interpret the roll result into the narrative (e.g., a low roll means a clumsy attempt).
2. USE 'manage_character_sheet' with 'add_item' whenever a player finds loot or gold.
3. USE 'manage_character_sheet' with 'update_stat' for HP changes or Level-ups.
4. USE 'archive_lore' ONLY for major milestones (killing a boss, moving to a new city, a player death).
5. CONTINUITY: Always check the 'Current Campaign Summary' and 'Lore Archives' provided in your context before describing the current state of the world."""

dm_agent = reasoning_engines.LangchainAgent(
    model="gemini-2.5-flash-lite",
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
    db = SessionLocal()
    
    char = db.query(Character).filter_by(user_id=user_id, chat_id=chat_id).first()
    if not char:
        # Create character
        new_char = Character(user_id=user_id, chat_id=chat_id, name=update.effective_user.first_name)
        db.add(new_char)
        db.commit()
        
        # 📣 Tell the DM someone new is here!
        current_slot = context.chat_data.get('active_slot', 1)
        save = db.query(GameSave).filter_by(chat_id=chat_id, slot_id=current_slot).first()
        
        if save:
            await update.message.reply_text(f"⚔️ {new_char.name} has joined the adventure mid-stride!")
        else:
            await update.message.reply_text(f"🛡️ {new_char.name} is ready in the lobby.")
    db.close()

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Store who started the game so only they can click (Group Setting tip)
    context.user_data['starter_id'] = update.effective_user.id
    
    keyboard = [
        [InlineKeyboardButton("❄️ Slot 1: The Frozen Tundra (Horror)", callback_data='game_1_horror')],
        [InlineKeyboardButton("🏜️ Slot 2: The Gilded Sands (Mystery)", callback_data='game_2_mystery')],
        [InlineKeyboardButton("🌳 Slot 3: The Whispering Woods (Classic)", callback_data='game_3_classic')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("✨ **Select your Universe:**", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # 1. Security: Only the starter can pick (for Group Settings)
    if query.from_user.id != context.user_data.get('starter_id'):
        await query.answer("⚠️ Only the Party Leader can choose the slot!", show_alert=True)
        return

    # 2. Parse the data: "game_1_horror" -> slot=1, theme="horror"
    parts = query.data.split('_')
    slot_id = int(parts[1])
    theme = parts[2]
    
    chat_id = str(query.message.chat_id)
    context.chat_data['active_slot'] = slot_id
    
    db = SessionLocal()
    save = db.query(GameSave).filter_by(chat_id=chat_id, slot_id=slot_id).first()
    
    if not save:
        # 3. Different Prompts for Different Slots
        prompts = {
            "horror": "Start a dark, gothic horror D&D campaign. The air is cold and smells of decay.",
            "mystery": "Start a desert-themed mystery. The party wakes up in an oasis with no memory.",
            "classic": "Start a classic high-fantasy adventure beginning in a bustling tavern."
        }
        
        # Call the DM Agent with the specific theme prompt
        response = dm_agent.query(input=prompts[theme])
        
        # Save to DB
        new_save = GameSave(chat_id=chat_id, slot_id=slot_id, summary=response["output"])
        db.add(new_save)
        db.commit()
        
        await query.edit_message_text(f"🎬 **NEW STORY STARTED**\n\n{response['output']}")
    else:
        await query.edit_message_text(f"💾 **LOADING SLOT {slot_id}...**\n\n{save.summary}")
    
    db.close()

async def view_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    db = SessionLocal()
    
    char = db.query(Character).filter_by(user_id=user_id, chat_id=chat_id).first()
    
    if char:
        stats = char.stats
        inventory = stats.get("inventory", [])
        
        # Format the inventory list into a string
        items_list = "\n".join([f"- {item}" for item in inventory]) if inventory else "- Empty"
        
        msg = (
            f"⚔️ **CHARACTER SHEET: {char.name}**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"❤️ **HP:** {stats.get('hp', 20)}\n"
            f"💰 **Gold:** {stats.get('gold', 0)}\n\n"
            f"🎒 **INVENTORY:**\n{items_list}"
        )
        
        # In Group Settings: Send to PM to avoid cluttering the group
        try:
            await context.bot.send_message(chat_id=user_id, text=msg, parse_mode="Markdown")
            if update.effective_chat.type != "private":
                await update.message.reply_text(f"✅ @{update.effective_user.username}, I've whispered your stats to you.")
        except Exception:
            # Fallback if they haven't started a chat with the bot
            await update.message.reply_text(msg, parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Use `/lobby [name]` to create a character first!")
    db.close()

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    chat_id = str(update.effective_chat.id)
    user_text = update.message.text
    
    # Get the active slot from context (defaults to 1 if not set)
    current_slot = context.chat_data.get('active_slot', 1)

    db = SessionLocal()
    try:
        character = db.query(Character).filter_by(user_id=user_id, chat_id=chat_id).first()
        if not character:
            await update.message.reply_text("❌ You aren't in this adventure! Use /lobby [Name].")
            return

        # 1. Fetch World Summary (The "Current Room/State")
        campaign_summary = get_summary(chat_id, current_slot) or "A fresh journey begins."

        # 2. Fetch Recent Lore (The "History/Memory")
        # We grab the 5 most recent major events to keep the AI focused
        recent_lore = db.query(CampaignLore).filter_by(
            chat_id=chat_id, 
            slot_id=current_slot
        ).order_by(CampaignLore.created_at.desc()).limit(5).all()
        
        # Format the lore into a readable string
        lore_context = " | ".join([f"EVENT: {l.content}" for l in reversed(recent_lore)]) if recent_lore else "No major history yet."

        # 🤖 3. The Enhanced AI Call
        # We now provide: Current State + History + Player Stats + Action
        input_str = (
            f"--- WORLD CONTEXT ---\n"
            f"CURRENT SCENE: {campaign_summary}\n"
            f"RECENT HISTORY: {lore_context}\n\n"
            f"--- PLAYER STATUS ---\n"
            f"ACTIVE PLAYER: {character.name}\n"
            f"STATS/INVENTORY: {character.stats}\n\n"
            f"PLAYER ACTION: {user_text}"
        )
        
        response = dm_agent.query(input=input_str)
        
        await update.message.reply_text(response["output"])
        
    except Exception as e:
        logger.error(f"💥 Gameplay Error: {type(e).__name__} - {e}")
        await update.message.reply_text("⚠️ The DM is consulting the rulebooks. Please try again.")
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

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "✨ **D&D Adventure Guide** ✨\n\n"
        "**Setup Commands:**\n"
        "👤 `/lobby [Name]` - Create your character for this chat.\n"
        "🎬 `/start_game` - Begin the story (Narrative start).\n"
        "🔄 `/reset` - Wipe current progress and start over.\n\n"
        "**Gameplay Commands:**\n"
        "📜 `/stats` - View your HP, Gold, and Items.\n"
        "🎲 `/roll 1d20` - Manually roll dice (or just tell the DM your action).\n"
        "💾 `/save` - Explicitly trigger a 'Hard State' save.\n\n"
        "**Tip:** You don't always need commands! Just talk to the DM like: *'I search the barrel for potions.'*"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELE_TOKEN).build()

    # 1. Register the Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("lobby", lobby))
    app.add_handler(CommandHandler("stats", view_stats))
    app.add_handler(CommandHandler("help", help_command))
    
    # This command now ONLY sends the buttons, it doesn't start the story yet
    app.add_handler(CommandHandler("start_game", start_game))

    # 2. Register the Button Listener (CRITICAL)
    # This handles the clicks from the start_game buttons
    app.add_handler(CallbackQueryHandler(button_handler))

    # 3. Register the Message Handler (The DM Logic)
    # Filters.TEXT & ~Filters.COMMAND means "any text that isn't a /command"
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_messages))

    logger.info("🤖 Bot is live. Waiting for players...")
    app.run_polling()