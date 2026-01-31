from core.interfaces import IUserRepository
from core.models import UserDTO

from infrastructure.database import SessionLocal, UserORM


class SqlAlchemyUserRepository(IUserRepository):
    def __init__(self):
        # We use a session factory to create a new DB session for every request
        self._session_factory = SessionLocal

    def save_or_update_user(self, phone_number: str, name: str, telegram_id: str) -> None:
        with self._session_factory() as session:
            # 1. Try to find existing user by phone
            user = session.query(UserORM).filter_by(phone_number=phone_number).first()

            if user:
                # Update existing
                user.name = name
                user.telegram_id = telegram_id
            else:
                # Create new
                new_user = UserORM(phone_number=phone_number, name=name, telegram_id=telegram_id)
                session.add(new_user)

            # Commit changes to DB
            session.commit()

    def get_user_by_phone(self, phone_number: str) -> UserDTO | None:
        with self._session_factory() as session:
            user = session.query(UserORM).filter_by(phone_number=phone_number).first()

            if user:
                # Convert Database Object (ORM) -> Data Transfer Object (DTO)
                return UserDTO(
                    phone_number=user.phone_number,
                    name=user.name,
                    telegram_id=user.telegram_id,
                )
            return None

    def get_user_by_id(self, telegram_id: str) -> UserDTO | None:
        with self._session_factory() as session:
            user = session.query(UserORM).filter_by(telegram_id=telegram_id).first()

            if user:
                return UserDTO(
                    phone_number=user.phone_number,
                    name=user.name,
                    telegram_id=user.telegram_id,
                )
            return None

    def get_user(self, telegram_id: str) -> UserDTO | None:
        """Alias for compatibility with welcome flow logic."""
        return self.get_user_by_id(telegram_id)

    def count_all_users(self) -> int:
        with self._session_factory() as session:
            return session.query(UserORM).count()

    def get_all_user_ids(self) -> list[str]:
        with self._session_factory() as session:
            rows = session.query(UserORM.telegram_id).all()
            return [str(row[0]) for row in rows if row[0] is not None]
