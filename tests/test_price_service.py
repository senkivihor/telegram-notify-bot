from services.price_service import PriceService


def test_price_service_returns_expected_text():
    service = PriceService()

    text = service.get_formatted_prices()

    assert "Вкорочення" in text
    assert "250" in text
