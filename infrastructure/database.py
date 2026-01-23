import os

from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

# Connect to DB
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bot.db")

_is_sqlite_memory = DATABASE_URL.startswith("sqlite:///:memory:")

if _is_sqlite_memory:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class UserORM(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String, unique=True, index=True, nullable=False)
    name = Column(String)
    telegram_id = Column(String, unique=True, nullable=False)


def init_db():
    Base.metadata.create_all(bind=engine)
