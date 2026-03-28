# ⚔️ Agentic D&D Bot: Vertex AI & Google Cloud Integration

A professional-grade **AI Dungeon Master** built on Google Cloud Platform (GCP). This bot utilizes **Vertex AI (Gemini 2.0 Flash Lite)** for agentic reasoning and **Cloud SQL (PostgreSQL)** for persistent game state management, providing a highly responsive TTRPG experience directly within Telegram.

---

## ☁️ Cloud Architecture & Tech Stack

* **AI Engine:** `Vertex AI` (Gemini 2.0 Flash Lite) — Optimized for low-latency agentic tool use and high-efficiency function calling.
* **Database:** `Google Cloud SQL` (PostgreSQL) — Centralized storage for characters, campaign states, and structured logs.
* **Orchestration:** `Vertex AI SDK`.
* **Interface:** `python-telegram-bot` (Asynchronous).
* **Infrastructure:** Designed for scalable deployment on `Google Cloud Run`.

---

## 🤖 Agentic Tooling & Logic

The bot operates as an **Autonomous Agent**. When a player acts, the Gemini model determines which local Python tools to trigger:

* **🎲 Dice Engine:** Executes cryptographic-safe rolls ($d20, d12, etc.$) based on story difficulty.
* **📖 Context Manager:** Periodically summarizes long-form adventures to maintain "world memory."
* **💾 Postgres CRUD:** A robust backend to Create, Read, Update, and Delete character data and campaign progress in real-time.

---

## 🎮 Game Flow & Multi-Slot Persistence

### **Core Commands**
* **`/start`**: Initializes the bot and detects `ChatType` (Private vs. Group).
* **`/join`**: Registers a user into the active session. **Supports mid-game joining**, where the AI narratively introduces the new player.
* **`/stats`**: Fetches a live view of character attributes and inventory from PostgreSQL.
* **`/help`**: Context-aware guide displaying available commands based on the game state.

### **3-Slot Save System**
* Provides **3 dedicated save slots** per Chat ID (distinguishes between Solo and Group play).
* Users can switch between campaigns or preload specific story arcs without data loss.

---

## 🚀 Setup & Installation

### **1. Environment Configuration**
Create a `.env` file in the root directory. **Ensure this file is added to your `.gitignore` before pushing to GitHub.**
```env
TELEGRAM_TOKEN=your_bot_father_token
PROJECT_ID=your_gcp_project_id
DB_HOST=your_cloud_sql_ip