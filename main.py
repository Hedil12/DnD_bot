import os, json, random
import threading, logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from smolagents import CodeAgent, OpenAIModel, tool

# 1. --- SETUP & KEYS ---
load_dotenv()
GEMINI_KEY = os.getenv("geminiAPI")
TELEGRAM_TOKEN = os.getenv("teleAPI")
TELEGRAM_URL = os.getenv("teleURL")
file_lock = threading.Lock()

# Configure logging to both a file and the console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_debug.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# This keeps track of who is actually playing in a group
# { chat_id: [user_id1, user_id2] }
active_parties = {} # { chat_id: [user_ids] }
ready_players = {}  # { chat_id: [user_ids] }
agent_memory_limit = 10 # Number of steps before summarizing

# 2. --- IMPORT TOOLS ---
from tools import manage_character, manage_campaign, roll_dice

# 3. --- AGENT CONFIG ---
model = OpenAIModel(
    model_id="gemini-2.5-flash-lite",
    api_base="https://generativelanguage.googleapis.com/v1beta/openai/",
    api_key=GEMINI_KEY
)

# This prompt forces the "Lite" model to be more creative and less robotic
DM_SYSTEM_PROMPT = (
    "You are an expert, atmospheric Dungeon Master. "
    "Rules for your narration: "
    "1. Use sensory details: Describe the smell of rot, the chill of the wind, or the flickering torchlight. "
    "2. Be proactive: If a player succeeds at a roll, describe their heroics. If they fail, describe the tension. "
    "3. Use your tools: Always check 'manage_campaign' at the start of a quest to remember where the players are. "
    "4. Engagement: Always end your response with a question or a prompt for the players to act."
)

agent = CodeAgent(
    tools=[manage_campaign, manage_character, roll_dice], 
    model=model,
    max_step=3,
    instructions=DM_SYSTEM_PROMPT,
    )

# 4. --- COMMAND HANDLERS (The missing pieces) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initial greeting and deep-link setup."""
    chat_type = update.message.chat.type
    user = update.message.from_user
    
    if chat_type == "private":
        await update.message.reply_text(f"Welcome to your private quarters, {user.first_name}. I can show you your stats here.")
    else:
        keyboard = [[InlineKeyboardButton("📝 My Private Stats", url=f"https://{TELEGRAM_URL}?start=setup")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "⚔️ **The Quest Awaits!**\n\n1. Type /join to enter the party.\n2. Type /ready when you are prepared.\n3. Type /start_quest to begin!",
            reply_markup=reply_markup, parse_mode='Markdown'
        )

async def start_quest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggers the AI to check campaign info and narrate the opening."""
    chat_id = update.effective_chat.id
    
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    # We explicitly tell the AI to check the campaign notes first
    prompt = (
        "The party is ready! First, use 'manage_campaign' to see if there are existing world notes. "
        "Then, narrate a dramatic scene for the party. If no notes exist, invent a starting location "
        "and save the Villain's name 'Lord Malakor' to the campaign notes."
    )
    
    response = agent.run(prompt)
    await update.message.reply_text(response)

async def ready_up(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Marks a player as ready."""
    chat_id = update.effective_chat.id
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name

    if chat_id not in ready_players: ready_players[chat_id] = []
    
    if user_id in active_parties.get(chat_id, []):
        if user_id not in ready_players[chat_id]:
            ready_players[chat_id].append(user_id)
            ready_count = len(ready_players[chat_id])
            total_count = len(active_parties[chat_id])
            await update.message.reply_text(f"👍 {user_name} is ready! ({ready_count}/{total_count} players ready)")
        else:
            await update.message.reply_text("You are already marked as ready.")
    else:
        await update.message.reply_text("You must /join the party first!")

async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name

    if chat_id not in active_parties: active_parties[chat_id] = []

    if user_id not in active_parties[chat_id]:
        active_parties[chat_id].append(user_id)
        agent.run(f"Create a character for {user_name}.")
        await update.message.reply_text(f"✨ {user_name} has joined the party! The DM is watching...")
    else:
        await update.message.reply_text("You're already in!")

async def get_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reads the current campaign summary from the JSON file."""
    chat_id = update.effective_chat.id
    
    # Check if the player is in the active party
    user_id = update.message.from_user.id
    if chat_id not in active_parties or user_id not in active_parties[chat_id]:
        await update.message.reply_text("You must /join the party to see the scrolls of history.")
        return

    # Read from the tool directly
    # Note: manage_campaign(action="read") returns the history_summary by default
    current_story = manage_campaign(action="read", key="history_summary")
    
    if current_story:
        formatted_summary = (
            "📖 **The Story So Far** 📖\n"
            "--------------------------\n"
            f"{current_story}\n"
            "--------------------------\n"
            "*What will you do next, adventurers?*"
        )
        await update.message.reply_text(formatted_summary, parse_mode='Markdown')
    else:
        await update.message.reply_text("The scrolls are blank... Your journey has just begun!")

# --- 5. MESSAGE HANDLER ---

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    player_name = update.message.from_user.first_name

    # --- AUTO-SUMMARIZE LOGIC ---
    # Check if the AI's internal 'steps' (memory) are getting too long
    if len(agent.memory.steps) >= agent_memory_limit:
        logging.info("Memory limit reached. Summarizing and pruning...")
        # Step 1: Force the AI to write a summary to the JSON file
        agent.run("System: Memory is full. Summarize the current situation and quest progress using manage_campaign(action='update', key='history_summary').")
        # Step 2: Clear the old chat history to save tokens
        agent.memory.steps = agent.memory.steps[-2:] # Keep only the last exchange for immediate context

    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        # We inject the current 'History Summary' into the prompt so the AI always knows the plot
        summary = manage_campaign(action="read", key="history_summary")
        full_prompt = f"Context: {summary}\nPlayer {player_name}: {user_text}"
        
        response = agent.run(full_prompt)
        await update.message.reply_text(response)
        
    except Exception as e:
        await update.message.reply_text("The DM is dazed... (Rate Limit). Try again in a moment!")

# --- 5. MAIN ---
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start)) # Make sure these are defined!
    app.add_handler(CommandHandler("join", join_game))
    app.add_handler(CommandHandler("ready", ready_up))
    app.add_handler(CommandHandler("start_quest", start_quest))
    app.add_handler(CommandHandler("summary", get_summary))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_msg))
    print("🚀 Campaign-Ready Bot is Online!")
    app.run_polling()