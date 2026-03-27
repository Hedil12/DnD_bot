# Create a quick file named sync.py
from database import engine, Base
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
print("✅ Database wiped and synced with new columns!")