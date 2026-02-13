import importlib
from unittest.mock import patch


def test_calculate_min_price_with_env_values():
    # Arrange
    env_values = {
        "HOURLY_LABOR_RATE": "200",
        "OVERHEAD_PER_HOUR": "50",
        "DEPRECIATION_FEE": "10",
        "CONSUMABLES_FEE": "15",
        "TAX_RATE": "0.05",
        "SERVICE_COMPLEXITY": '{"hem_pants": 60}',
    }

    def getenv_side_effect(key, default=None):
        if key in env_values:
            return env_values[key]
        return default

    with patch("services.pricing_model.os.getenv", side_effect=getenv_side_effect):
        import services.pricing_model as pricing_model

        importlib.reload(pricing_model)

        # Act
        result = pricing_model.calculate_min_price(60)

    # Assert
    assert result == {
        "final_price": 289,
        "labor": 200,
        "overhead": 50,
        "tax": 14,
    }


def test_service_complexity_fallback_on_invalid_json():
    # Arrange
    env_values = {
        "SERVICE_COMPLEXITY": "not-json",
    }

    def getenv_side_effect(key, default=None):
        if key in env_values:
            return env_values[key]
        return default

    with patch("services.pricing_model.os.getenv", side_effect=getenv_side_effect):
        import services.pricing_model as pricing_model

        importlib.reload(pricing_model)

        # Act
        complexity = pricing_model.SERVICE_COMPLEXITY

    # Assert
    assert complexity == pricing_model.DEFAULT_SERVICE_COMPLEXITY
