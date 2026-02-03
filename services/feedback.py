from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta

from core.models import FeedbackStatus

from infrastructure.repositories import SqlAlchemyFeedbackTaskRepository, SqlAlchemyUserRepository
from infrastructure.telegram_adapter import TelegramAdapter


CHECK_TEXT = "👋 Привіт! Минуло кілька днів як ваше замовлення готове. Ви вже встигли його забрати?"
NO_TEXT = "Ой, ваші речі вже сумують за вами! 🧥 Чекаємо в робочий час."
RATING_PROMPT = "Чудово! Як вам якість нашої роботи? Оцініть, будь ласка:"


@dataclass(frozen=True)
class FeedbackButtons:
    yes: str = "✅ Так, забрав(ла)"
    no: str = "❌ Ще ні"


def pickup_keyboard() -> dict:
    return {"keyboard": [[{"text": FeedbackButtons.yes}], [{"text": FeedbackButtons.no}]], "resize_keyboard": True}


def rating_keyboard() -> dict:
    return {
        "keyboard": [[{"text": "1"}, {"text": "2"}, {"text": "3"}, {"text": "4"}, {"text": "5"}]],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }


def shift_to_monday_morning(dt: datetime, hour: int = 10) -> datetime:
    if dt.weekday() == 5:  # Saturday
        return datetime.combine(dt.date() + timedelta(days=2), time(hour=hour))
    if dt.weekday() == 6:  # Sunday
        return datetime.combine(dt.date() + timedelta(days=1), time(hour=hour))
    return dt


def schedule_after_hours(base: datetime, hours: int) -> datetime:
    scheduled = base + timedelta(hours=hours)
    return shift_to_monday_morning(scheduled)


class FeedbackService:
    def __init__(
        self,
        user_repo: SqlAlchemyUserRepository,
        feedback_repo: SqlAlchemyFeedbackTaskRepository,
        telegram: TelegramAdapter,
        admin_ids: set[str],
        maps_url: str | None = None,
    ):
        self.user_repo = user_repo
        self.feedback_repo = feedback_repo
        self.telegram = telegram
        self.admin_ids = admin_ids
        self.maps_url = maps_url

    def schedule_feedback_for_user(self, user_id: int, created_at: datetime | None = None) -> None:
        now = created_at or datetime.now()
        scheduled_for = schedule_after_hours(now, 48)
        self.feedback_repo.create_task(
            user_id=user_id,
            created_at=now,
            scheduled_for=scheduled_for,
            status=FeedbackStatus.PENDING,
        )

    def process_feedback_queue(self, now: datetime | None = None) -> int:
        current = now or datetime.now()
        due = self.feedback_repo.get_due_tasks(current)
        sent_count = 0
        for task in due:
            user = self.user_repo.get_user_by_db_id(task.user_id)
            if not user:
                self.feedback_repo.update_task(task.id, status=FeedbackStatus.CANCELLED)
                continue
            ok = self.telegram.send_message(
                user.telegram_id, CHECK_TEXT, reply_markup=pickup_keyboard(), parse_mode=None
            )
            if ok:
                next_time = schedule_after_hours(current, 36)
                self.feedback_repo.update_task(
                    task.id,
                    status=FeedbackStatus.ASKING_PICKUP,
                    scheduled_for=next_time,
                )
                sent_count += 1
        return sent_count

    def process_queue(self, now: datetime | None = None) -> int:
        return self.process_feedback_queue(now=now)

    def handle_pickup_response(self, telegram_id: str, response_text: str, now: datetime | None = None) -> None:
        user = self.user_repo.get_user_by_id(telegram_id)
        if not user or user.id is None:
            return
        task = self.feedback_repo.get_latest_task_for_user(
            user.id, statuses=[FeedbackStatus.PENDING, FeedbackStatus.ASKING_PICKUP]
        )
        if not task:
            return

        current = now or datetime.now()
        if response_text == FeedbackButtons.no:
            attempts = task.pickup_attempts + 1
            if attempts >= 3:
                self.feedback_repo.update_task(task.id, status=FeedbackStatus.CANCELLED, pickup_attempts=attempts)
            else:
                next_time = schedule_after_hours(current, 36)
                self.feedback_repo.update_task(
                    task.id,
                    status=FeedbackStatus.ASKING_PICKUP,
                    scheduled_for=next_time,
                    pickup_attempts=attempts,
                )
            self.telegram.send_message(telegram_id, NO_TEXT, parse_mode=None)
            return

        if response_text == FeedbackButtons.yes:
            self.feedback_repo.update_task(task.id, status=FeedbackStatus.COMPLETED)
            self.telegram.send_message(telegram_id, RATING_PROMPT, reply_markup=rating_keyboard(), parse_mode=None)

    def handle_rating(self, telegram_id: str, score: int) -> None:
        user = self.user_repo.get_user_by_id(telegram_id)
        if not user or user.id is None:
            return
        task = self.feedback_repo.get_latest_task_for_user(user.id, statuses=[FeedbackStatus.COMPLETED])
        if not task:
            return

        if score == 5:
            if self.maps_url:
                markup = {"inline_keyboard": [[{"text": "🗺️ Google Maps", "url": self.maps_url}]]}
            else:
                markup = None
            self.telegram.send_message(
                telegram_id,
                "Дякуємо! 😍 Ми дуже раді! Будемо вдячні за відгук у Google Maps.",
                reply_markup=markup,
                parse_mode=None,
            )
            return
        if score == 4:
            self.telegram.send_message(telegram_id, "Дякуємо! Ми будемо старатися ще краще. 🙌", parse_mode=None)
            return

        if 1 <= score <= 3:
            self.telegram.send_message(telegram_id, "Нам прикро. 😔 Власник зв'яжеться з вами.", parse_mode=None)
            for admin_id in self.admin_ids:
                self.telegram.send_message(
                    admin_id,
                    f"🚨 Negative Feedback! User {telegram_id} rated {score} stars.",
                    parse_mode=None,
                )
