# ⚔️ Agentic D&D Telegram Bot: AI Dungeon Master

A specialized Telegram bot that transforms a Large Language Model (LLM) into an interactive **Dungeon Master**. This project moves beyond simple chat by implementing **Agentic AI**—allowing the model to use specific tools to manage game mechanics, character stats, and campaign progression.

---

## 🤖 The "Agentic" Approach
Unlike a standard chatbot, this bot uses an **Agentic Workflow**. The AI (Gemini / Local LLM) has access to a "Toolbox" of Python functions it can call to interact with the game world.

### 🛠️ Core Agent Tools
* **🎲 Dice Roller:** An automated tool that interprets story context to roll specific dice (e.g., $d20$ for skill checks, $2d8$ for damage).
* **📜 Campaign Manager:** A "Memory" tool that generates and updates story summaries. This allows the AI to stay consistent without needing the entire chat history.
* **👤 Character CRUD:** A dedicated system for managing player sheets (Create, Read, Update, Delete). 
    * *Current State:* Local logging and file-based persistence.
    * *Future State:* Migration to a centralized SQL database.

---

## 🎮 Game Flow & Commands
The bot uses a structured command system to guide the player through the TTRPG (Tabletop Role-Playing Game) experience:

| Command | Purpose |
| :--- | :--- |
| `/start` | Initializes the bot and provides the main menu. |
| `/join_game` | Registers the user and begins the character creation flow. |
| `/ready_up` | Signals the AI that the party is assembled and ready. |
| `/get_summary` | Fetches the current AI-generated "State of the World." |
| `/start_quest` | Prompts the AI Agent to generate the opening narrative encounter. |

---

## ⚡ Optimization & Resource Efficiency
A major focus of this project was **Token Management** and **Cost Reduction**. To ensure the bot remains responsive and inexpensive (especially when using high-parameter APIs), I implemented the following:

* **Context Pruning:** Instead of sending massive chat logs, the bot only sees the **latest summary + the current player input**. This keeps the context window small and prevents "Context Drift."
* **Small Model Compatibility:** Designed to be lightweight enough to run on **0.5B - 3B parameter models** by offloading math and data tracking to local Python logic.
* **Stateless Execution:** By using a local CRUD system for characters, the AI doesn't have to "remember" HP or Gold—it simply "reads" the tool output.

---

## 🛠️ Technical Stack
* **Language:** Python 3.10+
* **AI Integration:** Gemini API (LLM Model), HuggingFace smolagent API (Agentic tool) 
* **Interface:** `python-telegram-bot`
* **Data Handling:** Local JSON/Log-based storage (Transitioning to PostgreSQL or MySQL)

---

## 📈 Roadmap & Learning Journey
This project was born from a desire to see how AI can handle **structured game rules** vs **creative storytelling**. 

- [ ] **Database Integration:** Moving from local logs to a persistent database.
- [ ] **Multi-turn Combat Logic:** Developing a tool specifically for initiative and turn-tracking.
- [ ] **Inventory System:** Implementing a complex tool for item management and weight calculations.
