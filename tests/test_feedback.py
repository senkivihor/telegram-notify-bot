from datetime import datetime, timedelta

from core.models import FeedbackStatus

from infrastructure import repositories
from infrastructure.database import Base, FeedbackTaskORM, UserORM
from infrastructure.repositories import SqlAlchemyFeedbackTaskRepository, SqlAlchemyUserRepository

from services.feedback import (
    CHECK_TEXT,
    FeedbackButtons,
    FeedbackService,
    rating_keyboard,
    schedule_after_hours,
)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class DummyTelegram:
    def __init__(self):
        self.messages = []

    def send_message(self, chat_id, text, reply_markup=None, parse_mode=None):
        self.messages.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})
        return True


def make_session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def seed_user(session_factory, telegram_id="100") -> int:
    with session_factory() as session:
        user = UserORM(phone_number="+380000000000", name="Test", telegram_id=telegram_id)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user.id


def test_scheduler_sends_check_message(monkeypatch):
    session_factory = make_session_factory()
    monkeypatch.setattr(repositories, "SessionLocal", session_factory)

    user_repo = SqlAlchemyUserRepository()
    feedback_repo = SqlAlchemyFeedbackTaskRepository()
    telegram = DummyTelegram()
    service = FeedbackService(user_repo, feedback_repo, telegram, admin_ids=set())

    user_id = seed_user(session_factory, telegram_id="777")
    past = datetime(2026, 2, 1, 9, 0, 0)
    feedback_repo.create_task(
        user_id=user_id,
        created_at=past - timedelta(days=1),
        scheduled_for=past,
        status=FeedbackStatus.PENDING,
    )

    sent = service.process_feedback_queue(now=past)

    assert sent == 1
    assert telegram.messages
    assert telegram.messages[0]["text"] == CHECK_TEXT

    with session_factory() as session:
        task = session.query(FeedbackTaskORM).first()
        assert task.status == FeedbackStatus.ASKING_PICKUP
        assert task.scheduled_for > past


def test_weekend_logic_shifts_to_monday():
    thursday = datetime(2026, 2, 5, 9, 0, 0)  # Thursday
    scheduled = schedule_after_hours(thursday, 48)

    assert scheduled.weekday() == 0  # Monday
    assert scheduled.hour == 10


def test_no_click_reschedules(monkeypatch):
    session_factory = make_session_factory()
    monkeypatch.setattr(repositories, "SessionLocal", session_factory)

    user_repo = SqlAlchemyUserRepository()
    feedback_repo = SqlAlchemyFeedbackTaskRepository()
    telegram = DummyTelegram()
    service = FeedbackService(user_repo, feedback_repo, telegram, admin_ids=set())

    user_id = seed_user(session_factory, telegram_id="555")
    now = datetime(2026, 2, 3, 10, 0, 0)
    feedback_repo.create_task(
        user_id=user_id,
        created_at=now - timedelta(days=3),
        scheduled_for=now - timedelta(hours=1),
        status=FeedbackStatus.ASKING_PICKUP,
    )

    service.handle_pickup_response("555", FeedbackButtons.no, now=now)

    with session_factory() as session:
        task = session.query(FeedbackTaskORM).first()
        assert task.pickup_attempts == 1
        assert task.status == FeedbackStatus.ASKING_PICKUP
        assert task.scheduled_for > now


def test_yes_click_shows_rating(monkeypatch):
    session_factory = make_session_factory()
    monkeypatch.setattr(repositories, "SessionLocal", session_factory)

    user_repo = SqlAlchemyUserRepository()
    feedback_repo = SqlAlchemyFeedbackTaskRepository()
    telegram = DummyTelegram()
    service = FeedbackService(user_repo, feedback_repo, telegram, admin_ids=set())

    user_id = seed_user(session_factory, telegram_id="999")
    now = datetime(2026, 2, 3, 12, 0, 0)
    feedback_repo.create_task(
        user_id=user_id,
        created_at=now - timedelta(days=3),
        scheduled_for=now - timedelta(hours=1),
        status=FeedbackStatus.PENDING,
    )

    service.handle_pickup_response("999", FeedbackButtons.yes, now=now)

    assert telegram.messages
    assert telegram.messages[-1]["text"] == "Чудово! Як вам якість нашої роботи? Оцініть, будь ласка:"
    assert telegram.messages[-1]["reply_markup"] == rating_keyboard()

    with session_factory() as session:
        task = session.query(FeedbackTaskORM).first()
        assert task.status == FeedbackStatus.COMPLETED
