import os
from dotenv import load_dotenv
from google.cloud.sql.connector import Connector, IPTypes
import sqlalchemy
from sqlalchemy import Column, String, Integer, JSON, Text, DateTime, Boolean, func
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. LOAD DOTENV FIRST
load_dotenv()

# 2. FORCE SET THE ENV VAR IN PYTHON
if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
else:
    print("❌ ERROR: GOOGLE_APPLICATION_CREDENTIALS not found in .env")

def get_engine():
    connector = Connector() 
    
    def getconn():
        conn = connector.connect(
            os.getenv("INSTANCE_CONNECTION_NAME"),
            "pg8000",
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            db=os.getenv("DB_NAME"),
            ip_type=IPTypes.PUBLIC
        )
        return conn

    engine = sqlalchemy.create_engine(
        "postgresql+pg8000://",
        creator=getconn,
    )
    return engine

Base = declarative_base()
engine = get_engine() 
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Models ---

class Character(Base):
    __tablename__ = "characters"
    # Added id as primary key so one user can have multiple characters in different chats
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String)
    chat_id = Column(String)  # ✅ FIXED: Added missing chat_id
    name = Column(String)
    stats = Column(JSON)      # {"hp": 20, "gold": 10}

class CampaignLore(Base):
    __tablename__ = "campaign_lore"
    id = Column(Integer, primary_key=True)
    chat_id = Column(String) # Good to track which chat this lore belongs to
    content = Column(Text)

class Party(Base):
    __tablename__ = "parties"
    chat_id = Column(String, primary_key=True)
    leader_id = Column(String)
    is_active = Column(Boolean, default=False)
    players = Column(JSON)    # ["123", "456"]

class GameSave(Base):
    __tablename__ = "game_saves"
    chat_id = Column(String, primary_key=True)
    summary = Column(Text, default="The journey begins...")
    last_saved = Column(DateTime, server_default=func.now())