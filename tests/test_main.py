import pytest
from unittest.mock import MagicMock, patch
from main import app
from core.models import UserDTO

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
    Mocks the Database Repo and Telegram Adapter so we don't
    actually touch the DB or send real messages during tests.
    """
    with (
        patch("main.repo") as mock_repo,
        patch("main.telegram") as mock_telegram,
        patch("main.INTERNAL_KEY", "test_secret_key"),
    ):

        yield mock_repo, mock_telegram


# --- TEST CASES ---


# 1. Test /start Command (User clicks Start)
def test_telegram_start_command(client, mock_dependencies):
    mock_repo, mock_telegram = mock_dependencies

    # Simulate Telegram sending a /start message
    payload = {"message": {"chat": {"id": 12345}, "text": "/start"}}

    response = client.post("/webhook/telegram", json=payload)

    # Assertions
    assert response.status_code == 200
    # Check if the bot asked for the phone number
    mock_telegram.ask_for_phone.assert_called_once_with(12345)


# 2. Test Sharing Phone Number (User clicks 'Share Phone')
def test_telegram_share_contact(client, mock_dependencies):
    mock_repo, mock_telegram = mock_dependencies

    # Simulate user sharing their contact
    payload = {"message": {"chat": {"id": 999}, "contact": {"phone_number": "1234567890", "first_name": "Alice"}}}

    response = client.post("/webhook/telegram", json=payload)

    # Assertions
    assert response.status_code == 200

    # 1. Ensure user is saved to DB (Normalizes phone to +123...)
    mock_repo.save_or_update_user.assert_called_once_with(phone_number="+1234567890", name="Alice", telegram_id="999")

    # 2. Ensure success message is sent back
    mock_telegram.send_message.assert_called_once()
    assert "Connected" in mock_telegram.send_message.call_args[0][1]


# 3. Test Trigger API - UNAUTHORIZED (No Key)
def test_trigger_unauthorized(client):
    # Try to trigger without the API Key header
    response = client.post("/trigger-notification", json={})
    assert response.status_code == 403


# 4. Test Trigger API - SUCCESS (Happy Path)
def test_trigger_success(client, mock_dependencies):
    mock_repo, mock_telegram = mock_dependencies

    # Setup Mock: DB finds the user
    mock_user = UserDTO(phone_number="+123", name="Bob", telegram_id="555")
    mock_repo.get_user_by_phone.return_value = mock_user

    # Setup Mock: Telegram sends successfully
    mock_telegram.send_message.return_value = True

    # Make the Request
    headers = {"X-Internal-API-Key": "test_secret_key"}
    data = {"phone_number": "+123", "order_id": "ORD-101", "items": ["Burger", "Coke"]}

    response = client.post("/trigger-notification", json=data, headers=headers)

    # Assertions
    assert response.status_code == 200
    assert response.json["status"] == "Success"

    # Verify the message content
    args = mock_telegram.send_message.call_args[0]
    assert args[0] == "555"  # Chat ID
    assert "ORD-101" in args[1]  # Message body contains Order ID
    assert "Burger" in args[1]


# 5. Test Trigger API - USER NOT FOUND
def test_trigger_user_not_found(client, mock_dependencies):
    mock_repo, mock_telegram = mock_dependencies

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
    mock_repo, mock_telegram = mock_dependencies

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
