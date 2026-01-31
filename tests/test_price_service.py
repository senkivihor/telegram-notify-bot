from services.price_service import PriceService


def test_get_formatted_prices_contains_expected_fragments():
    # Arrange
    service = PriceService()

    # Act
    text = service.get_formatted_prices()

    # Assert
    assert "Вкорочення" in text
    assert "250" in text
