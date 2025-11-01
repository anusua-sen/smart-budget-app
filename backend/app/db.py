from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# Make sure folder exists for database
os.makedirs("backend/data", exist_ok=True)

# Path to your database file
DATABASE_URL = "sqlite:///backend/data/app.db"

# Create engine and session
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
# ✅ Import models *AFTER* Base is defined
from backend.app.models.transaction_model import Transaction
from backend.app.models.budget_model import Budget

# ✅ Create all tables (only needs to run once at startup)
Base.metadata.create_all(bind=engine)
