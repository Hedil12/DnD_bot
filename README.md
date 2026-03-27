# ⚔️ Agentic D&D Bot: Vertex AI & Google Cloud Integration

A professional-grade **AI Dungeon Master** built on Google Cloud Platform (GCP). This bot utilizes **Vertex AI (Gemini)** for agentic reasoning and **Cloud SQL (PostgreSQL)** for persistent game state management, providing a seamless TTRPG experience directly within Telegram.

---

## ☁️ Cloud Architecture & Tech Stack

*   **AI Engine:** `Vertex AI` (Gemini 2.0 Flash lite) — Leverages advanced function calling for agentic tool use.
*   **Database:** `Google Cloud SQL` (PostgreSQL) — Centralized storage for characters, campaign states, and chat logs.
*   **Orchestration:** `Vertex AI SDK` .
*   **Interface:** `python-telegram-bot` (Asynchronous).
*   **Infrastructure:** Designed for deployment on `Google Cloud Run` or `Compute Engine`.

---

## 🤖 Agentic Tooling & Logic

The bot operates as an **Autonomous Agent**. When a player acts, the Gemini model determines if it needs to call a specific Python tool:

*   **🎲 Dice Engine:** Calculates rolls ($d20, d12, etc.$) based on situational difficulty.
*   **📖 Context Manager:** Periodically summarizes long-form adventures to stay within token limits.
*   **💾 Postgres CRUD:** A robust backend to Create, Read, Update, and Delete character data and campaign progress.

---

## 🎮 Game Flow & Session Handling

The bot intelligently distinguishes between **Private** (1-on-1) and **Public** (Group) chats to manage game sessions effectively.

### **Core Commands**
*   **`/start`**: Initializes the connection. The bot detects the `ChatType` (Private vs. Group) and sets up the environment accordingly.
*   **`/join`**: Registers the user into the active database session. If in a group chat, it links the user to that specific Group ID.

### **Message Handling & Persistence**
Every interaction is processed through a multi-layered pipeline:
1.  **Ingestion:** Incoming messages are captured and identified by User ID and Chat ID.
2.  **Logging:** System-level logs track API latency, tool-calling success, and errors for debugging.
3.  **Database Sync:** Game events (e.g., "Found a rusty sword") are saved to PostgreSQL immediately to ensure no data loss if the bot restarts.
4.  **AI Response:** Gemini generates the narrative based on the retrieved DB context.

---

## ⚡ Performance & Optimization

*   **Token Efficiency:** Implemented a "Sliding Window" context approach. By storing previous interactions in PostgreSQL, we only feed the most relevant "summaries" back to Vertex AI, significantly reducing costs.
*   **Connection Pooling:** Optimized database hits using SQLAlchemy to handle multiple concurrent users without exhausting Cloud SQL resources.
*   **Structured Logging:** Comprehensive logs are maintained to monitor the "Chain of Thought" of the AI agent, ensuring the DM logic remains consistent.

---

## ⚙️ Configuration (GCP)

To run this project, ensure the following environment variables are set:
*   `GOOGLE_APPLICATION_CREDENTIALS`: Path to your GCP Service Account JSON.
*   `PROJECT_ID`: Your Google Cloud Project ID.
*   `DB_HOST`: Your Cloud SQL Public/Private IP.
*   `TELEGRAM_TOKEN`: Your bot token from BotFather.