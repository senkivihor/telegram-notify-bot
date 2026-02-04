from datetime import datetime
from unittest.mock import MagicMock, patch

from core.models import FeedbackStatus, FeedbackTaskDTO, UserDTO

from services.feedback import (
    FeedbackButtons,
    FeedbackService,
    NO_TEXT,
    RATING_PROMPT,
    rating_keyboard,
    schedule_after_hours,
)


def make_service(maps_url: str | None = None, admin_ids: set[str] | None = None):
    user_repo = MagicMock()
    feedback_repo = MagicMock()
    telegram = MagicMock()
    service = FeedbackService(
        user_repo=user_repo,
        feedback_repo=feedback_repo,
        telegram=telegram,
        admin_ids=admin_ids or set(),
        maps_url=maps_url,
    )
    return service, user_repo, feedback_repo, telegram


def test_scheduler_weekend_logic_thursday_to_monday():
    # Arrange
    service, _, feedback_repo, _ = make_service()
    thursday = datetime(2026, 2, 5, 15, 0, 0)  # Thursday

    with patch("services.feedback.datetime") as dt_mock:
        dt_mock.now.return_value = thursday
        dt_mock.combine.side_effect = datetime.combine

        # Act
        service.schedule_feedback_for_user(user_id=1)

    # Assert
    scheduled_for = feedback_repo.create_task.call_args.kwargs["scheduled_for"]
    assert scheduled_for.weekday() == 0  # Monday
    assert scheduled_for.hour == 10


def test_pickup_flow_user_says_yes():
    # Arrange
    service, user_repo, feedback_repo, telegram = make_service()
    user = UserDTO(phone_number="+380000000000", name="Test", telegram_id="777", id=1)
    task = FeedbackTaskDTO(
        id=10,
        user_id=1,
        created_at=datetime(2026, 2, 1, 10, 0, 0),
        scheduled_for=datetime(2026, 2, 3, 10, 0, 0),
        status=FeedbackStatus.ASKING_PICKUP,
        pickup_attempts=0,
    )
    user_repo.get_user_by_id.return_value = user
    feedback_repo.get_latest_task_for_user.return_value = task

    # Act
    service.handle_pickup_response("777", FeedbackButtons.yes, now=datetime(2026, 2, 3, 12, 0, 0))

    # Assert
    feedback_repo.update_task.assert_called_once_with(task.id, status=FeedbackStatus.COMPLETED)
    telegram.send_message.assert_called_once_with(
        "777",
        RATING_PROMPT,
        reply_markup=rating_keyboard(),
        parse_mode=None,
    )


def test_pickup_flow_user_says_no_retry():
    # Arrange
    service, user_repo, feedback_repo, telegram = make_service()
    now = datetime(2026, 2, 3, 10, 0, 0)
    user = UserDTO(phone_number="+380000000000", name="Test", telegram_id="555", id=2)
    task = FeedbackTaskDTO(
        id=11,
        user_id=2,
        created_at=datetime(2026, 2, 1, 10, 0, 0),
        scheduled_for=datetime(2026, 2, 2, 10, 0, 0),
        status=FeedbackStatus.ASKING_PICKUP,
        pickup_attempts=0,
    )
    user_repo.get_user_by_id.return_value = user
    feedback_repo.get_latest_task_for_user.return_value = task

    # Act
    with patch("services.feedback.datetime") as dt_mock:
        dt_mock.now.return_value = now
        dt_mock.combine.side_effect = datetime.combine
        service.handle_pickup_response("555", FeedbackButtons.no)

    # Assert
    expected_next = schedule_after_hours(now, 36)
    feedback_repo.update_task.assert_called_once_with(
        task.id,
        status=FeedbackStatus.ASKING_PICKUP,
        scheduled_for=expected_next,
        pickup_attempts=1,
    )
    telegram.send_message.assert_called_once_with("555", NO_TEXT, parse_mode=None)


def test_pickup_flow_max_retries_reached():
    # Arrange
    service, user_repo, feedback_repo, telegram = make_service()
    user = UserDTO(phone_number="+380000000000", name="Test", telegram_id="999", id=3)
    task = FeedbackTaskDTO(
        id=12,
        user_id=3,
        created_at=datetime(2026, 2, 1, 10, 0, 0),
        scheduled_for=datetime(2026, 2, 2, 10, 0, 0),
        status=FeedbackStatus.ASKING_PICKUP,
        pickup_attempts=2,
    )
    user_repo.get_user_by_id.return_value = user
    feedback_repo.get_latest_task_for_user.return_value = task

    # Act
    service.handle_pickup_response("999", FeedbackButtons.no, now=datetime(2026, 2, 3, 10, 0, 0))

    # Assert
    feedback_repo.update_task.assert_called_once()
    update_kwargs = feedback_repo.update_task.call_args.kwargs
    assert update_kwargs["status"] == FeedbackStatus.CANCELLED
    assert update_kwargs["pickup_attempts"] == 3
    assert "scheduled_for" not in update_kwargs
    telegram.send_message.assert_called_once_with("999", NO_TEXT, parse_mode=None)


def test_rating_high_score_google_maps():
    # Arrange
    maps_url = "https://maps.google.com/?q=example"
    service, user_repo, feedback_repo, telegram = make_service(maps_url=maps_url)
    user = UserDTO(phone_number="+380000000000", name="Test", telegram_id="777", id=4)
    task = FeedbackTaskDTO(
        id=13,
        user_id=4,
        created_at=datetime(2026, 2, 1, 10, 0, 0),
        scheduled_for=datetime(2026, 2, 2, 10, 0, 0),
        status=FeedbackStatus.COMPLETED,
        pickup_attempts=0,
    )
    user_repo.get_user_by_id.return_value = user
    feedback_repo.get_latest_task_for_user.return_value = task

    # Act
    service.handle_rating("777", 5)

    # Assert
    args, kwargs = telegram.send_message.call_args
    assert args[0] == "777"
    assert "Google Maps" in args[1]
    assert kwargs["reply_markup"]["inline_keyboard"][0][0]["url"] == maps_url


def test_rating_low_score_admin_alert():
    # Arrange
    service, user_repo, feedback_repo, telegram = make_service(admin_ids={"42"})
    user = UserDTO(phone_number="+380000000000", name="Test", telegram_id="888", id=5)
    task = FeedbackTaskDTO(
        id=14,
        user_id=5,
        created_at=datetime(2026, 2, 1, 10, 0, 0),
        scheduled_for=datetime(2026, 2, 2, 10, 0, 0),
        status=FeedbackStatus.COMPLETED,
        pickup_attempts=0,
    )
    user_repo.get_user_by_id.return_value = user
    feedback_repo.get_latest_task_for_user.return_value = task

    # Act
    service.handle_rating("888", 2)

    # Assert
    calls = telegram.send_message.call_args_list
    assert any(call.args[0] == "888" and "Нам прикро" in call.args[1] for call in calls)
    assert any(call.args[0] == "42" and "🚨 Negative Feedback" in call.args[1] for call in calls)
