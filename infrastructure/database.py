import os

from core.models import FeedbackStatus

from sqlalchemy import Column, DateTime, Enum as SAEnum, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool


# Connect to DB
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bot.db")

_is_sqlite_memory = DATABASE_URL.startswith("sqlite:///:memory:")
_is_postgres = DATABASE_URL.startswith("postgresql")

if _is_sqlite_memory:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    # Enable pre_ping so stale pooled connections are recycled after DB restarts/SSL idle timeouts.
    connect_args = (
        {
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        }
        if _is_postgres
        else {}
    )
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=1800, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class UserORM(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String, unique=True, index=True, nullable=False)
    name = Column(String)
    telegram_id = Column(String, unique=True, nullable=False)


class FeedbackTaskORM(Base):
    __tablename__ = "feedback_tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False)
    scheduled_for = Column(DateTime, nullable=False, index=True)
    status = Column(SAEnum(FeedbackStatus, name="feedback_status", native_enum=False), nullable=False)
    pickup_attempts = Column(Integer, nullable=False, default=0)


def init_db():
    Base.metadata.create_all(bind=engine)
