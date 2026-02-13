"""Pricing model for tailoring services.

Tweak the numbers in your .env file to match your atelier economics:
- HOURLY_LABOR_RATE: target salary / paid hours (UAH per hour).
- OVERHEAD_PER_HOUR: rent + utilities / paid hours.
- DEPRECIATION_FEE: fixed machine wear per order.
- CONSUMABLES_FEE: fixed consumables per order.
- TAX_RATE: effective tax rate (e.g., 0.05 for 5%).

SERVICE_COMPLEXITY must be a JSON dictionary in .env, for example:
SERVICE_COMPLEXITY='{"hem_pants": 30, "zipper_jacket": 60}'
"""

from __future__ import annotations

import json
import os
from typing import Dict

DEFAULT_SERVICE_COMPLEXITY: Dict[str, int] = {
    "hem_pants": 30,
    "zipper_jacket": 60,
    "patch_simple": 20,
}


def _get_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _load_service_complexity() -> Dict[str, int]:
    raw = os.getenv("SERVICE_COMPLEXITY", "")
    if not raw:
        return DEFAULT_SERVICE_COMPLEXITY.copy()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return DEFAULT_SERVICE_COMPLEXITY.copy()
    if not isinstance(payload, dict):
        return DEFAULT_SERVICE_COMPLEXITY.copy()
    cleaned: Dict[str, int] = {}
    for key, value in payload.items():
        try:
            cleaned[str(key)] = int(value)
        except (TypeError, ValueError):
            continue
    return cleaned or DEFAULT_SERVICE_COMPLEXITY.copy()


# Economics (UAH) loaded from .env with safe defaults
HOURLY_LABOR_RATE: float = _get_float_env("HOURLY_LABOR_RATE", 156.0)
OVERHEAD_PER_HOUR: float = _get_float_env("OVERHEAD_PER_HOUR", 31.0)
DEPRECIATION_FEE: float = _get_float_env("DEPRECIATION_FEE", 10.0)
CONSUMABLES_FEE: float = _get_float_env("CONSUMABLES_FEE", 15.0)
TAX_RATE: float = _get_float_env("TAX_RATE", 0.05)

# Service complexity matrix (minutes per task)
SERVICE_COMPLEXITY: Dict[str, int] = _load_service_complexity()


def calculate_min_price(base_minutes: int) -> Dict[str, int]:
    """Calculate minimum viable price for a service.
    Returns a rounded integer breakdown in UAH.
    """
    if base_minutes <= 0:
        raise ValueError("base_minutes must be > 0")

    hours = base_minutes / 60
    labor_cost = hours * HOURLY_LABOR_RATE
    overhead_cost = hours * OVERHEAD_PER_HOUR
    subtotal = labor_cost + overhead_cost + DEPRECIATION_FEE + CONSUMABLES_FEE
    final_price = subtotal / (1 - TAX_RATE)

    return {
        "final_price": int(round(final_price)),
        "labor": int(round(labor_cost)),
        "overhead": int(round(overhead_cost)),
        "tax": int(round(final_price * TAX_RATE)),
    }
