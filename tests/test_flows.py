from unittest.mock import patch

from core.models import UserDTO

from main import app

import pytest


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_dependencies():
    with (
        patch("main.repo") as mock_repo,
        patch("main.telegram") as mock_telegram,
        patch("main.location_service") as mock_location_service,
        patch("main.price_service") as mock_price_service,
    ):
        yield mock_repo, mock_telegram, mock_location_service, mock_price_service


def test_admin_non_admin_member_reroutes_to_member_menu(client, mock_dependencies):
    mock_repo, mock_telegram, _, _ = mock_dependencies
    mock_repo.get_user.return_value = UserDTO(phone_number="+1", name="Mila", telegram_id="101")
    mock_telegram.get_member_keyboard.return_value = {"keyboard": "member"}

    with patch("main.ADMIN_IDS", set()):
        payload = {"message": {"chat": {"id": 101}, "text": "/admin"}}
        response = client.post("/webhook/telegram", json=payload)

    assert response.status_code == 200
    assert mock_telegram.send_message.call_count == 2

    first_args, first_kwargs = mock_telegram.send_message.call_args_list[0]
    assert first_args[0] == 101
    assert "Command not recognized" in first_args[1]

    second_args, second_kwargs = mock_telegram.send_message.call_args_list[1]
    assert second_args[0] == 101
    assert "Welcome back" in second_args[1]
    assert second_kwargs.get("reply_markup") == {"keyboard": "member"}
    assert second_kwargs.get("parse_mode") == "Markdown"


def test_admin_non_admin_guest_reroutes_to_guest_menu(client, mock_dependencies):
    mock_repo, mock_telegram, _, _ = mock_dependencies
    mock_repo.get_user.return_value = None
    mock_telegram.get_guest_keyboard.return_value = {"keyboard": "guest"}

    with patch("main.ADMIN_IDS", set()):
        payload = {"message": {"chat": {"id": 202}, "text": "/admin"}}
        response = client.post("/webhook/telegram", json=payload)

    assert response.status_code == 200
    assert mock_telegram.send_message.call_count == 2

    first_args, first_kwargs = mock_telegram.send_message.call_args_list[0]
    assert first_args[0] == 202
    assert "Command not recognized" in first_args[1]

    second_args, second_kwargs = mock_telegram.send_message.call_args_list[1]
    assert second_args[0] == 202
    assert "Share your contact" in second_args[1]
    assert second_kwargs.get("reply_markup") == {"keyboard": "guest"}
    assert second_kwargs.get("parse_mode") == "Markdown"
