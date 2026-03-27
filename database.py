import os
from dotenv import load_dotenv
from google.cloud.sql.connector import Connector, IPTypes
import sqlalchemy
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. LOAD DOTENV FIRST
load_dotenv()

# 2. FORCE SET THE ENV VAR IN PYTHON (Safety Hack)
# This ensures Google's internal library sees the file even if .env is acting up
if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
else:
    print("❌ ERROR: GOOGLE_APPLICATION_CREDENTIALS not found in .env")

def get_engine():
    # The Connector() looks at os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
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
# This triggers the engine creation
engine = get_engine() 
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Models ---
class Character(Base):
    __tablename__ = "characters"
    user_id = sqlalchemy.Column(sqlalchemy.String, primary_key=True)
    name = sqlalchemy.Column(sqlalchemy.String)
    stats = sqlalchemy.Column(sqlalchemy.JSON) # {"hp": 20, "gold": 10}

class CampaignLore(Base):
    __tablename__ = "campaign_lore"
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    content = sqlalchemy.Column(sqlalchemy.Text)

class Party(Base):
    __tablename__ = "parties"
    chat_id = sqlalchemy.Column(sqlalchemy.String, primary_key=True) # Group Chat ID
    leader_id = sqlalchemy.Column(sqlalchemy.String)
    is_active = sqlalchemy.Column(sqlalchemy.Boolean, default=False)
    players = sqlalchemy.Column(sqlalchemy.JSON) # List of user_ids: ["123", "456"]

class GameSave(Base):
    __tablename__ = "game_saves"
    chat_id = sqlalchemy.Column(sqlalchemy.String, primary_key=True)
    summary = sqlalchemy.Column(sqlalchemy.Text, default="The journey begins...")
    last_saved = sqlalchemy.Column(sqlalchemy.DateTime, server_default=sqlalchemy.func.now())