"""Transparent heuristic allocation used by the SMART Grid Austria demo.

All outputs are screening scenarios, not grid-connection approvals or yield
forecasts. The method uses the current snapshot's free connection capacity.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

PV_PERFORMANCE_RATIO = 0.85
REFERENCE_IRRADIANCE_KW_PER_M2 = 1.0

LOW_POTENTIAL_COLOR = [189, 195, 199, 100]
NO_CAPACITY_COLOR = [150, 150, 150, 160]


def _as_finite_float(value: Any, field_name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric; got {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite; got {value!r}")
    return number


def calculate_heuristic_mix(
    row: Mapping[str, Any],
    target_wind: float,
    target_solar: float,
    use_climate_analysis: bool = True,
) -> tuple[list[int], str, float, float, float, int]:
    """Return map color, strategy, Wind/PV/BESS MVA, and PV-hours proxy."""
    capacity = _as_finite_float(row.get("Frei_MVA"), "Frei_MVA")
    if capacity < 0:
        raise ValueError("Frei_MVA cannot be negative")

    base_color = row.get("Farbe_Netz", LOW_POTENTIAL_COLOR)
    if not use_climate_analysis:
        return base_color, "Basis-Netzmodus", 0.0, 0.0, 0.0, 0

    solar_irradiation = _as_finite_float(row.get("Solar_kWh"), "Solar_kWh")
    solar_proxy = (
        solar_irradiation / REFERENCE_IRRADIANCE_KW_PER_M2
    ) * PV_PERFORMANCE_RATIO
    solar_proxy_hours = int(solar_proxy)

    # A node with no published free connection capacity cannot be a current
    # connection candidate, regardless of its local climate indicators.
    if capacity <= 0:
        return (
            NO_CAPACITY_COLOR,
            "Keine freie Netzkapazität",
            0.0,
            0.0,
            0.0,
            solar_proxy_hours,
        )

    wind_value = row.get("Wind_ms")
    try:
        wind_speed = float(wind_value)
        wind_valid = math.isfinite(wind_speed)
    except (TypeError, ValueError):
        wind_speed = 0.0
        wind_valid = False

    if not wind_valid or wind_speed < target_wind:
        wind_weight_score = 0.0
    else:
        # Deliberately heuristic score; it is not a physical energy quantity.
        wind_weight_score = min(
            3200.0,
            1000.0 + (wind_speed - target_wind) * 500.0,
        )

    wind_ok = wind_weight_score > 0
    solar_ok = solar_irradiation >= target_solar

    if not wind_ok and not solar_ok:
        return (
            LOW_POTENTIAL_COLOR,
            "Geringes Potenzial",
            0.0,
            0.0,
            0.0,
            solar_proxy_hours,
        )

    total_resource_score = (
        (wind_weight_score if wind_ok else 0.0)
        + (solar_proxy if solar_ok else 0.0)
    )
    if total_resource_score <= 0:
        raise ValueError("Resource score must be positive for a candidate")

    wind_weight = wind_weight_score / total_resource_score if wind_ok else 0.0
    solar_weight = solar_proxy / total_resource_score if solar_ok else 0.0

    if wind_ok and solar_ok:
        bess_share = 0.20
        strategy = "Hybrides Wind-PV-System + BESS (heuristisch)"
        color = [155, 89, 182, 210]
    elif wind_ok:
        bess_share = 0.25
        strategy = "Windpark + BESS (heuristisch)"
        color = [41, 128, 185, 210]
    else:
        bess_share = 0.35
        strategy = "PV-Anlage + BESS (heuristisch)"
        color = [241, 196, 15, 210]

    bess_mva = round(capacity * bess_share, 1)
    wind_mva = round(capacity * wind_weight * (1 + bess_share), 1)
    pv_mva = round(capacity * solar_weight * (1 + bess_share), 1)

    return color, strategy, wind_mva, pv_mva, bess_mva, solar_proxy_hours
