import os
from google.cloud.sql.connector import Connector, IPTypes
import sqlalchemy
from sqlalchemy.orm import sessionmaker, declarative_base

def get_engine():
    # Initialize Cloud SQL Connector
    connector = Connector()
    def getconn():
        conn = connector.connect(
            os.getenv("INSTANCE_CONNECTION_NAME"), # e.g. "project:region:instance"
            "pg8000",
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            db=os.getenv("DB_NAME"),
            ip_type=IPTypes.PUBLIC  # Or PRIVATE if using VPC
        )
        return conn

    engine = sqlalchemy.create_engine(
        "postgresql+pg8000://",
        creator=getconn,
    )
    return engine

Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())

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
    save_data = sqlalchemy.Column(sqlalchemy.JSON) # The "Snapshot" of the world
    last_saved = sqlalchemy.Column(sqlalchemy.DateTime, server_default=sqlalchemy.func.now())