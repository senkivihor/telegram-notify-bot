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
        patch("main.feedback_service") as mock_feedback_service,
    ):
        yield mock_repo, mock_telegram, mock_location_service, mock_feedback_service


class FakeResponse:
    def __init__(self, text: str):
        self.text = text


def test_ai_estimator_client_response(client, mock_dependencies):
    mock_repo, mock_telegram, _, _ = mock_dependencies
    mock_repo.get_user.return_value = UserDTO(phone_number="+1", name="Ann", telegram_id="101")

    with (
        patch("main.GEMINI_API_KEY", "test-key"),
        patch("main._AI_SERVICE", None),
        patch("services.ai_service.genai.Client") as mock_client_cls,
    ):
        mock_client = mock_client_cls.return_value
        mock_client.models.generate_content.return_value = FakeResponse(
            '{"task_summary": "test", "estimated_minutes": 45}'
        )

        payload_button = {"message": {"chat": {"id": 101}, "text": "🪄 AI Оцінка вартості"}}
        response = client.post("/webhook/telegram", json=payload_button)
        assert response.status_code == 200

        payload_prompt = {"message": {"chat": {"id": 101}, "text": "test"}}
        response = client.post("/webhook/telegram", json=payload_prompt)

    assert response.status_code == 200
    assert mock_telegram.send_message.call_count >= 2
    final_text = mock_telegram.send_message.call_args_list[-1][0][1]
    assert "Попередня оцінка AI" in final_text
    assert "Орієнтовна вартість" in final_text


def test_ai_estimator_admin_response(client, mock_dependencies):
    mock_repo, mock_telegram, _, _ = mock_dependencies
    mock_repo.get_user.return_value = UserDTO(phone_number="+1", name="Admin", telegram_id="202")

    with (
        patch("main.ADMIN_IDS", {"202"}),
        patch("main.GEMINI_API_KEY", "test-key"),
        patch("main._AI_SERVICE", None),
        patch("services.ai_service.genai.Client") as mock_client_cls,
    ):
        mock_client = mock_client_cls.return_value
        mock_client.models.generate_content.return_value = FakeResponse(
            '{"task_summary": "test", "estimated_minutes": 45}'
        )

        payload_button = {"message": {"chat": {"id": 202}, "text": "🧮 AI Калькулятор вартості"}}
        response = client.post("/webhook/telegram", json=payload_button)
        assert response.status_code == 200

        payload_prompt = {"message": {"chat": {"id": 202}, "text": "test"}}
        response = client.post("/webhook/telegram", json=payload_prompt)

    assert response.status_code == 200
    assert mock_telegram.send_message.call_count >= 2
    final_text = mock_telegram.send_message.call_args_list[-1][0][1]
    assert "AI Калькулятор вартості" in final_text
    assert "Вартість" in final_text
    assert "Мінімальна ціна" in final_text
