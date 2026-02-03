from datetime import datetime

from core.interfaces import IUserRepository
from core.models import FeedbackStatus, FeedbackTaskDTO, UserDTO

from infrastructure.database import FeedbackTaskORM, SessionLocal, UserORM


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
                    id=user.id,
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
                    id=user.id,
                )
            return None

    def get_user_by_db_id(self, user_id: int) -> UserDTO | None:
        with self._session_factory() as session:
            user = session.query(UserORM).filter_by(id=user_id).first()

            if user:
                return UserDTO(
                    phone_number=user.phone_number,
                    name=user.name,
                    telegram_id=user.telegram_id,
                    id=user.id,
                )
            return None

    # Compatibility alias for welcome flow
    def get_user(self, telegram_id: str) -> UserDTO | None:
        return self.get_user_by_id(telegram_id)

    def count_all_users(self) -> int:
        with self._session_factory() as session:
            return session.query(UserORM).count()

    def get_all_user_ids(self) -> list[str]:
        with self._session_factory() as session:
            rows = session.query(UserORM.telegram_id).all()
            return [str(row[0]) for row in rows if row[0] is not None]


class SqlAlchemyFeedbackTaskRepository:
    def __init__(self):
        self._session_factory = SessionLocal

    def create_task(
        self,
        user_id: int,
        created_at: datetime,
        scheduled_for: datetime,
        status: FeedbackStatus,
    ) -> FeedbackTaskDTO:
        with self._session_factory() as session:
            task = FeedbackTaskORM(
                user_id=user_id,
                created_at=created_at,
                scheduled_for=scheduled_for,
                status=status,
                pickup_attempts=0,
            )
            session.add(task)
            session.commit()
            session.refresh(task)
            return FeedbackTaskDTO(
                id=task.id,
                user_id=task.user_id,
                created_at=task.created_at,
                scheduled_for=task.scheduled_for,
                status=task.status,
                pickup_attempts=task.pickup_attempts,
            )

    def get_due_tasks(self, now: datetime) -> list[FeedbackTaskDTO]:
        with self._session_factory() as session:
            rows = (
                session.query(FeedbackTaskORM)
                .filter(FeedbackTaskORM.status.in_([FeedbackStatus.PENDING, FeedbackStatus.ASKING_PICKUP]))
                .filter(FeedbackTaskORM.scheduled_for <= now)
                .order_by(FeedbackTaskORM.scheduled_for.asc())
                .all()
            )
            return [
                FeedbackTaskDTO(
                    id=row.id,
                    user_id=row.user_id,
                    created_at=row.created_at,
                    scheduled_for=row.scheduled_for,
                    status=row.status,
                    pickup_attempts=row.pickup_attempts,
                )
                for row in rows
            ]

    def get_latest_task_for_user(
        self, user_id: int, statuses: list[FeedbackStatus] | None = None
    ) -> FeedbackTaskDTO | None:
        with self._session_factory() as session:
            query = session.query(FeedbackTaskORM).filter(FeedbackTaskORM.user_id == user_id)
            if statuses:
                query = query.filter(FeedbackTaskORM.status.in_(statuses))
            row = query.order_by(FeedbackTaskORM.created_at.desc()).first()
            if not row:
                return None
            return FeedbackTaskDTO(
                id=row.id,
                user_id=row.user_id,
                created_at=row.created_at,
                scheduled_for=row.scheduled_for,
                status=row.status,
                pickup_attempts=row.pickup_attempts,
            )

    def update_task(
        self,
        task_id: int,
        status: FeedbackStatus | None = None,
        scheduled_for: datetime | None = None,
        pickup_attempts: int | None = None,
    ) -> None:
        with self._session_factory() as session:
            task = session.query(FeedbackTaskORM).filter(FeedbackTaskORM.id == task_id).first()
            if not task:
                return
            if status is not None:
                task.status = status
            if scheduled_for is not None:
                task.scheduled_for = scheduled_for
            if pickup_attempts is not None:
                task.pickup_attempts = pickup_attempts
            session.commit()
