import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from models import Base

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "cybercafe_db")
DB_USER = os.getenv("DB_USER", "cybercafe_admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "changeme123")

DATABASE_URL = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db():
    """Create all tables defined in models.py"""
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully.")


def get_db():
    """Yields a DB session, closes it after use"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()