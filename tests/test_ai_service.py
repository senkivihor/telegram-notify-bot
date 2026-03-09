from unittest.mock import patch

import pytest

from services.ai_service import AIService, calculate_smart_price_range


class FakeResponse:
    def __init__(self, text: str):
        self.text = text


@pytest.mark.parametrize(
    "raw_min_price, expected",
    [
        ("500", 500),
        ("oops", 0),
        (None, 0),
    ],
)
def test_ai_service_min_list_price_parsing(raw_min_price, expected):
    with patch("services.ai_service.genai.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.models.generate_content.return_value = FakeResponse(
            "{"
            '"task_summary": "test", '
            '"estimated_minutes": 60, '
            f'"min_list_price": {"null" if raw_min_price is None else f"\"{raw_min_price}\""}'
            "}"
        )

        service = AIService("test-key")
        result = service.analyze_tailoring_task("test")

    assert result["min_list_price"] == expected


def test_calculate_smart_price_range_uses_list_floor():
    min_price, max_price = calculate_smart_price_range(300, 500)
    assert min_price == 500
    assert max_price == 600


def test_calculate_smart_price_range_standard_rule():
    min_price, max_price = calculate_smart_price_range(300, 0)
    assert min_price == 200
    assert max_price == 400
