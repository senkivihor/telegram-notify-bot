from infrastructure import repositories
from infrastructure.database import Base, UserORM
from infrastructure.repositories import SqlAlchemyUserRepository

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def make_session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def test_save_or_update_updates_existing_user(monkeypatch):
    session_factory = make_session_factory()
    monkeypatch.setattr(repositories, "SessionLocal", session_factory)
    repo = SqlAlchemyUserRepository()

    with session_factory() as session:
        session.add(UserORM(phone_number="+1", name="Old", telegram_id="1"))
        session.commit()

    repo.save_or_update_user(phone_number="+1", name="New", telegram_id="2")

    with session_factory() as session:
        user = session.query(UserORM).filter_by(phone_number="+1").one()
        assert user.name == "New"
        assert user.telegram_id == "2"
        assert session.query(UserORM).count() == 1


def test_get_user_by_phone_none(monkeypatch):
    session_factory = make_session_factory()
    monkeypatch.setattr(repositories, "SessionLocal", session_factory)
    repo = SqlAlchemyUserRepository()

    result = repo.get_user_by_phone("+404")

    assert result is None


def test_get_user_by_phone_returns_dto(monkeypatch):
    session_factory = make_session_factory()
    monkeypatch.setattr(repositories, "SessionLocal", session_factory)
    repo = SqlAlchemyUserRepository()

    with session_factory() as session:
        session.add(UserORM(phone_number="+7", name="Jane", telegram_id="77"))
        session.commit()

    result = repo.get_user_by_phone("+7")

    assert result is not None
    assert result.phone_number == "+7"
    assert result.name == "Jane"
    assert result.telegram_id == "77"
