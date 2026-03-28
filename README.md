# ⚔️ Agentic D&D Bot: Vertex AI & Google Cloud Integration

A professional-grade **AI Dungeon Master** built on Google Cloud Platform (GCP). This bot utilizes **Vertex AI (Gemini 2.0 Flash Lite)** for agentic reasoning and **Cloud SQL (PostgreSQL)** for persistent game state management, providing a highly responsive TTRPG experience directly within Telegram.

---

## ☁️ Cloud Architecture & Tech Stack

*   **AI Engine:** `Vertex AI` (Gemini 2.0 Flash Lite) — Optimized for low-latency agentic tool use and high-efficiency function calling.
*   **Database:** `Google Cloud SQL` (PostgreSQL) — Centralized storage for characters, campaign states, and structured logs.
*   **Orchestration:** `Vertex AI SDK`.
*   **Interface:** `python-telegram-bot` (Asynchronous).
*   **Infrastructure:** Designed for scalable deployment on `Google Cloud Run`.

---

## 🤖 Agentic Tooling & Logic

The bot operates as an **Autonomous Agent**. When a player acts, the Gemini model determines which local Python tools to trigger to maintain game integrity:

*   **🎲 Dice Engine:** Executes cryptographic-safe rolls ($d20, d12, etc.$) based on story difficulty.
*   **📖 Context Manager:** Periodically summarizes long-form adventures to stay within token limits and maintain "world memory."
*   **💾 Postgres CRUD:** A robust backend to Create, Read, Update, and Delete character data and campaign progress in real-time.

---

## 🎮 Game Flow & Multi-Slot Persistence

The bot intelligently manages session states, distinguishing between **Private** (Solo) and **Public** (Group) chats to ensure data isolation.

### **Core Commands**
*   **`/start`**: Initializes the bot and detects `ChatType`. In group settings, it initializes the lobby.
*   **`/join`**: Registers a user into the active session. **Supports mid-game joining**, where the AI narratively introduces the new player to the current scene.
*   **`/stats`**: Fetches a live view of character attributes, inventory, and status directly from PostgreSQL.
*   **`/help`**: A context-aware guide that displays available commands based on the current game state.

### **3-Slot Save System**
To support multiple adventures, the bot provides **3 dedicated save slots** per Chat ID.
*   Users can switch between different campaigns without data loss.
*   Preloading logic allows the "Dungeon Master" to resume specific story arcs across different sessions.

---

## ⚡ Performance & Optimization

*   **Token Efficiency:** Implemented a "Sliding Window" context approach. By storing interactions in PostgreSQL, we only feed the most relevant summaries back to Gemini, significantly reducing latency and costs.
*   **Connection Pooling:** Optimized database hits using **SQLAlchemy** to handle concurrent players across multiple groups without exhausting Cloud SQL resources.
*   **Hybrid Session Logic:** Differentiates between "Lobby" and "Active" states, ensuring the AI only begins storytelling once the party is ready.
*   **Structured Logging:** Comprehensive system logs track API latency and "Chain of Thought" reasoning to debug the DM's decision-making process.

---

## ⚙️ Configuration (GCP)

To run this project, ensure the following environment variables are set:
*   `GOOGLE_APPLICATION_CREDENTIALS`: Path to your GCP Service Account JSON.
*   `PROJECT_ID`: Your Google Cloud Project ID.
*   `DB_HOST`: Your Cloud SQL Public/Private IP.
*   `TELEGRAM_TOKEN`: Your bot token from BotFather.

---