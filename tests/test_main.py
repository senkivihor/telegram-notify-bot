from unittest.mock import patch

from core.models import UserDTO

from main import app

import pytest

# --- FIXTURES (Setup) ---


@pytest.fixture
def client():
    """Creates a test client for the Flask app."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_dependencies():
    """
    Mocks the Database Repo, Location Service, and Telegram Adapter so we don't
    actually touch the DB or send real messages during tests.
    """
    with (
        patch("main.repo") as mock_repo,
        patch("main.telegram") as mock_telegram,
        patch("main.location_service") as mock_location_service,
        patch("main.feedback_service") as mock_feedback_service,
        patch("main.INTERNAL_KEY", "test_secret_key"),
    ):
        yield mock_repo, mock_telegram, mock_location_service, mock_feedback_service


# --- TEST CASES ---


def test_telegram_start_command_new_user(client, mock_dependencies):
    mock_repo, mock_telegram, _, _ = mock_dependencies
    mock_repo.get_user.return_value = None

    payload = {"message": {"chat": {"id": 12345}, "text": "/start"}}

    response = client.post("/webhook/telegram", json=payload)

    assert response.status_code == 200
    mock_repo.get_user.assert_called_once_with("12345")
    mock_telegram.send_message.assert_called_once()
    args, kwargs = mock_telegram.send_message.call_args
    assert args[0] == 12345
    assert "поділіться номером" in args[1]
    reply_markup = kwargs.get("reply_markup")
    assert reply_markup and reply_markup.get("keyboard")
    mock_telegram.ask_for_phone.assert_not_called()
    mock_telegram.send_main_menu.assert_not_called()


def test_telegram_start_command_existing_user(client, mock_dependencies):
    mock_repo, mock_telegram, _, _ = mock_dependencies
    mock_repo.get_user.return_value = UserDTO(phone_number="+1", name="Alice", telegram_id="12345")

    payload = {"message": {"chat": {"id": 12345}, "text": "/start"}}

    response = client.post("/webhook/telegram", json=payload)

    assert response.status_code == 200
    mock_repo.get_user.assert_called_once_with("12345")
    mock_telegram.send_message.assert_called_once()
    args, kwargs = mock_telegram.send_message.call_args
    assert args[0] == 12345
    assert "З поверненням" in args[1]
    assert kwargs.get("reply_markup")
    mock_telegram.ask_for_phone.assert_not_called()


def test_help_sends_support_text(client, mock_dependencies):
    mock_repo, mock_telegram, _, _ = mock_dependencies

    with patch("main.SUPPORT_CONTACT_USERNAME", "@SupportHero"), patch("main.LOCATION_CONTACT_PHONE", "+111 222 333"):
        payload = {"message": {"chat": {"id": 111}, "text": "/help"}}

        response = client.post("/webhook/telegram", json=payload)

    assert response.status_code == 200
    mock_telegram.send_message.assert_called_once()
    args = mock_telegram.send_message.call_args[0]
    assert args[0] == 111
    assert "Потрібна допомога" in args[1]
    assert "@SupportHero" in args[1]
    assert "+111 222 333" in args[1]
    mock_telegram.ask_for_phone.assert_not_called()
    mock_telegram.send_admin_menu.assert_not_called()


def test_admin_stats_button(client, mock_dependencies):
    mock_repo, mock_telegram, _, _ = mock_dependencies
    mock_repo.count_all_users.return_value = 5

    with patch("main.ADMIN_IDS", {"42"}):
        payload = {"message": {"chat": {"id": 42}, "text": "📊 Статистика"}}

        response = client.post("/webhook/telegram", json=payload)

    assert response.status_code == 200
    mock_repo.count_all_users.assert_called_once()
    mock_telegram.send_message.assert_called_once()
    assert "Total Users: **5**" in mock_telegram.send_message.call_args[0][1]


def test_admin_broadcast_handles_blocked_user(client, mock_dependencies):
    mock_repo, mock_telegram, _, _ = mock_dependencies
    mock_repo.get_all_user_ids.return_value = ["u1", "u2"]

    def side_effect(chat_id, text, reply_markup=None):
        if chat_id in {"u1", "99", 99}:  # allow admin report (int) and first user
            return True
        raise Exception("403")

    mock_telegram.send_message.side_effect = side_effect

    with patch("main.ADMIN_IDS", {"99"}):
        payload = {"message": {"chat": {"id": 99}, "text": "/broadcast hello"}}

        response = client.post("/webhook/telegram", json=payload)

    assert response.status_code == 200
    # send_message called 3 times: u1, u2, admin report
    assert mock_telegram.send_message.call_count == 3
    report_text = mock_telegram.send_message.call_args[0][1]
    assert "Sent to 1 users" in report_text
    assert "Failed/Blocked: 1" in report_text


def test_telegram_start_command_admin(client, mock_dependencies):
    mock_repo, mock_telegram, _, _ = mock_dependencies
    mock_repo.get_user.return_value = None

    payload = {"message": {"chat": {"id": 4242}, "text": "/start"}}

    response = client.post("/webhook/telegram", json=payload)

    assert response.status_code == 200
    mock_telegram.send_admin_menu.assert_not_called()
    mock_telegram.send_message.assert_called_once()
    assert "Вітаємо" in mock_telegram.send_message.call_args[0][1]


def test_admin_command_non_admin_soft_fail(client, mock_dependencies):
    mock_repo, mock_telegram, _, _ = mock_dependencies
    mock_repo.get_user.return_value = UserDTO(phone_number="+1", name="Ann", telegram_id="700")

    payload = {"message": {"chat": {"id": 700}, "text": "/admin"}}

    response = client.post("/webhook/telegram", json=payload)

    assert response.status_code == 200
    mock_telegram.send_admin_menu.assert_not_called()
    assert mock_telegram.send_message.call_count == 2
    first_text = mock_telegram.send_message.call_args_list[0][0][1]
    second_text = mock_telegram.send_message.call_args_list[1][0][1]
    assert "Команда не розпізнана" in first_text
    assert "З поверненням" in second_text
    # Ensure member keyboard was shown (no request_contact flag expected)
    member_markup = mock_telegram.send_message.call_args_list[1][1].get("reply_markup")
    assert member_markup
    buttons_flat = [btn for row in member_markup.get("keyboard", []) for btn in row]
    assert all("request_contact" not in btn for btn in buttons_flat)
    mock_telegram.ask_for_phone.assert_not_called()


def test_admin_command_admin_shows_menu(client, mock_dependencies):
    mock_repo, mock_telegram, _, _ = mock_dependencies

    with patch("main.ADMIN_IDS", {"800"}):
        payload = {"message": {"chat": {"id": 800}, "text": "/admin"}}

        response = client.post("/webhook/telegram", json=payload)

    assert response.status_code == 200
    mock_telegram.send_admin_menu.assert_called_once_with(800)
    mock_telegram.ask_for_phone.assert_not_called()


# 2. Test Sharing Phone Number (User clicks 'Share Phone')
def test_telegram_share_contact(client, mock_dependencies):
    mock_repo, mock_telegram, _, _ = mock_dependencies

    # Simulate user sharing their contact
    payload = {"message": {"chat": {"id": 999}, "contact": {"phone_number": "1234567890", "first_name": "Alice"}}}

    with patch("main.get_instagram_url", return_value="https://instagram.com/demo"):
        response = client.post("/webhook/telegram", json=payload)

    # Assertions
    assert response.status_code == 200

    # 1. Ensure user is saved to DB (Normalizes phone to +123...)
    mock_repo.save_or_update_user.assert_called_once_with(phone_number="+1234567890", name="Alice", telegram_id="999")

    # 2. Ensure success message includes Instagram link and CTA button
    assert mock_telegram.send_message.call_count == 1
    first_args, first_kwargs = mock_telegram.send_message.call_args
    assert first_args[0] == 999
    assert "Дякуємо, зберегли ваш номер" in first_args[1]
    assert "https://instagram.com/demo" in first_args[1]
    assert first_kwargs.get("reply_markup") == {
        "inline_keyboard": [[{"text": "Відкрити Instagram", "url": "https://instagram.com/demo"}]]
    }

    # 4. Ensure reply keyboard with location was re-opened
    mock_telegram.send_location_menu.assert_called_once_with(999)


# 3. Test Trigger API - UNAUTHORIZED (No Key)
def test_trigger_unauthorized(client):
    # Try to trigger without the API Key header
    response = client.post("/trigger-notification", json={})
    assert response.status_code == 403


# 4. Test Trigger API - SUCCESS (Happy Path)
def test_trigger_success(client, mock_dependencies):
    mock_repo, mock_telegram, _, mock_feedback_service = mock_dependencies

    # Setup Mock: DB finds the user
    mock_user = UserDTO(phone_number="+123", name="Bob", telegram_id="555", id=10)
    mock_repo.get_user_by_phone.return_value = mock_user

    # Setup Mock: Telegram sends successfully
    mock_telegram.send_message.return_value = True

    # Make the Request
    headers = {"X-Internal-API-Key": "test_secret_key"}
    data = {"phone_number": "+123", "order_id": "", "items": []}

    response = client.post("/trigger-notification", json=data, headers=headers)

    # Assertions
    assert response.status_code == 200
    assert response.json["status"] == "Success"

    # Verify the message content
    args = mock_telegram.send_message.call_args[0]
    assert args[0] == "555"  # Chat ID
    assert "Ура! Ваше замовлення вже готове!" in args[1]  # Message body contains Order ID
    assert "Ми все підготували і чекаємо на вас." in args[1]
    mock_feedback_service.schedule_feedback_for_user.assert_called_once_with(10)


# 5. Test Trigger API - USER NOT FOUND
def test_trigger_user_not_found(client, mock_dependencies):
    mock_repo, mock_telegram, _, _ = mock_dependencies

    # Setup Mock: DB returns None (User not in system)
    mock_repo.get_user_by_phone.return_value = None

    headers = {"X-Internal-API-Key": "test_secret_key"}
    data = {"phone": "+999"}

    response = client.post("/trigger-notification", json=data, headers=headers)

    assert response.status_code == 200
    assert "Failed" in response.json["status"]
    # Ensure we never tried to send a telegram message
    mock_telegram.send_message.assert_not_called()


# 6. Test Trigger API - TELEGRAM API FAILURE
def test_trigger_telegram_api_failure(client, mock_dependencies):
    mock_repo, mock_telegram, _, _ = mock_dependencies

    # Setup Mock: DB finds the user
    mock_user = UserDTO(phone_number="+123", name="Bob", telegram_id="555")
    mock_repo.get_user_by_phone.return_value = mock_user

    # Setup Mock: Telegram fails to send
    mock_telegram.send_message.return_value = False

    # Make the Request
    headers = {"X-Internal-API-Key": "test_secret_key"}
    data = {"phone_number": "+123", "order_id": "ORD-102", "items": ["Pizza", "Soda"]}

    response = client.post("/trigger-notification", json=data, headers=headers)

    # Assertions
    assert response.status_code == 200
    assert "Failed" in response.json["status"]


def test_telegram_ignores_irrelevant_message(client, mock_dependencies):
    mock_repo, mock_telegram, _, _ = mock_dependencies

    payload = {"message": {"chat": {"id": 111}, "text": "hello"}}

    response = client.post("/webhook/telegram", json=payload)

    assert response.status_code == 200
    mock_repo.save_or_update_user.assert_not_called()
    mock_telegram.ask_for_phone.assert_not_called()
    mock_telegram.send_message.assert_not_called()


def test_telegram_start_with_deep_link(client, mock_dependencies):
    mock_repo, mock_telegram, _, _ = mock_dependencies
    mock_repo.get_user.return_value = None

    payload = {"message": {"chat": {"id": 4242}, "text": "/start ORD-123"}}

    response = client.post("/webhook/telegram", json=payload)

    assert response.status_code == 200
    mock_repo.get_user.assert_called_once_with("4242")
    mock_telegram.send_message.assert_called_once()
    assert "Вітаємо" in mock_telegram.send_message.call_args[0][1]


def test_trigger_wrong_key(client):
    headers = {"X-Internal-API-Key": "wrong"}

    response = client.post("/trigger-notification", json={}, headers=headers)

    assert response.status_code == 403


def test_trigger_missing_phone_fails(client, mock_dependencies):
    mock_repo, mock_telegram, _, _ = mock_dependencies
    mock_repo.get_user_by_phone.return_value = None

    headers = {"X-Internal-API-Key": "test_secret_key"}
    data = {"order_id": "ORD-500", "items": ["Tea"]}

    response = client.post("/trigger-notification", json=data, headers=headers)

    assert response.status_code == 200
    assert "Failed" in response.json["status"]
    mock_telegram.send_message.assert_not_called()


def test_instagram_url_reads_from_env(monkeypatch):
    import main

    monkeypatch.setenv("INSTAGRAM_URL", "https://instagram.com/from-env")
    main._INSTAGRAM_WARNING_EMITTED = False

    assert main.get_instagram_url() == "https://instagram.com/from-env"


def test_portfolio_button_sends_instagram_link(client, mock_dependencies):
    mock_repo, mock_telegram, _, _ = mock_dependencies

    with patch("main.get_instagram_url", return_value="https://instagram.com/demo"):
        payload = {"message": {"chat": {"id": 303}, "text": "📸 Наші роботи"}}

        response = client.post("/webhook/telegram", json=payload)

    assert response.status_code == 200
    mock_telegram.send_message.assert_called_once()
    args, kwargs = mock_telegram.send_message.call_args
    assert args[0] == 303
    assert "Подивіться наше портфоліо" in args[1]
    assert "https://instagram.com/demo" in args[1]
    assert kwargs.get("reply_markup") == {
        "inline_keyboard": [[{"text": "Відкрити Instagram", "url": "https://instagram.com/demo"}]]
    }


def test_prices_button_sends_price_list(client, mock_dependencies):
    mock_repo, mock_telegram, _, _ = mock_dependencies

    with patch("main.price_service") as mock_price_service:
        mock_price_service.get_formatted_prices.return_value = "PRICE TEXT"

        payload = {"message": {"chat": {"id": 404}, "text": "💰 Ціни"}}
        response = client.post("/webhook/telegram", json=payload)

    assert response.status_code == 200
    mock_price_service.get_formatted_prices.assert_called_once()
    mock_telegram.send_message.assert_called_once()
    args, kwargs = mock_telegram.send_message.call_args
    assert args[0] == 404
    assert args[1] == "PRICE TEXT"
    assert kwargs.get("parse_mode") == "Markdown"


def test_health_check(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.data == b"OK"


def test_feedback_task_endpoint_rejects_missing_token(client, mock_dependencies):
    response = client.get("/tasks/check-feedback")

    assert response.status_code == 403


def test_location_button_triggers_location_flow(client, mock_dependencies):
    mock_repo, mock_telegram, mock_location_service, _ = mock_dependencies

    payload = {"message": {"chat": {"id": 321}, "text": "📍 Локація"}}

    response = client.post("/webhook/telegram", json=payload)

    assert response.status_code == 200
    mock_location_service.send_location_details.assert_called_once_with(321)
    mock_repo.save_or_update_user.assert_not_called()


def test_menu_resends_keyboard(client, mock_dependencies):
    mock_repo, mock_telegram, _, _ = mock_dependencies

    payload = {"message": {"chat": {"id": 777}, "text": "/menu"}}

    response = client.post("/webhook/telegram", json=payload)

    assert response.status_code == 200
    mock_telegram.ask_for_phone.assert_not_called()
    mock_telegram.send_message.assert_not_called()
    mock_repo.save_or_update_user.assert_not_called()


def test_schedule_button_sends_schedule_text(client, mock_dependencies):
    mock_repo, mock_telegram, _, _ = mock_dependencies

    payload = {"message": {"chat": {"id": 606}, "text": "📅 Графік"}}

    response = client.post("/webhook/telegram", json=payload)

    assert response.status_code == 200
    mock_telegram.send_message.assert_called_once()
    args, kwargs = mock_telegram.send_message.call_args
    assert args[0] == 606
    # schedule text originates from env; ensure we at least see a clock emoji default
    assert "⏰" in args[1] or "Графік" in args[1]
    assert kwargs.get("parse_mode") is None
    # Ensure no request_contact flag in any button
    markup = kwargs.get("reply_markup")
    if markup:
        buttons_flat = [btn for row in markup.get("keyboard", []) for btn in row]
        assert all("request_contact" not in btn for btn in buttons_flat)


def test_contact_phone_button_sends_phone(client, mock_dependencies):
    mock_repo, mock_telegram, _, _ = mock_dependencies

    payload = {"message": {"chat": {"id": 707}, "text": "📞 Контактний телефон"}}

    response = client.post("/webhook/telegram", json=payload)

    assert response.status_code == 200
    mock_telegram.send_message.assert_called_once()
    args, kwargs = mock_telegram.send_message.call_args
    assert args[0] == 707
    assert "📞" in args[1]
    assert kwargs.get("parse_mode") is None
    # Ensure no request_contact flag in any button
    markup = kwargs.get("reply_markup")
    if markup:
        buttons_flat = [btn for row in markup.get("keyboard", []) for btn in row]
        assert all("request_contact" not in btn for btn in buttons_flat)
