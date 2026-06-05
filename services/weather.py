"""Wetter-Service über die Open-Meteo API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests
import streamlit as st

import config

# WMO Weather interpretation codes (vereinfacht)
_WMO_DESCRIPTIONS: dict[int, str] = {
    0: "Klar",
    1: "Überwiegend klar",
    2: "Teilweise bewölkt",
    3: "Bewölkt",
    45: "Nebel",
    48: "Nebel mit Reifbildung",
    51: "Leichter Nieselregen",
    53: "Nieselregen",
    55: "Starker Nieselregen",
    61: "Leichter Regen",
    63: "Regen",
    65: "Starker Regen",
    71: "Leichter Schneefall",
    73: "Schneefall",
    75: "Starker Schneefall",
    80: "Leichte Regenschauer",
    81: "Regenschauer",
    82: "Starke Regenschauer",
    95: "Gewitter",
    96: "Gewitter mit Hagel",
    99: "Starkes Gewitter mit Hagel",
}


def _weather_description(code: int | None) -> str:
    if code is None:
        return "Unbekannt"
    return _WMO_DESCRIPTIONS.get(code, "Wechselhaft")


def _build_standardized_response(
    current: dict[str, Any],
    forecast: list[dict[str, Any]],
) -> dict[str, Any]:
    """Erzeugt das standardisierte Wetter-Dictionary für die UI-Schicht."""
    return {
        "location": config.LOCATION_NAME,
        "current": current,
        "forecast": forecast,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def _fetch_weather_from_api() -> dict[str, Any]:
    """Ruft Rohdaten von Open-Meteo ab und mappt sie auf das Standardformat."""
    params = {
        "latitude": config.LOCATION_LATITUDE,
        "longitude": config.LOCATION_LONGITUDE,
        "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min",
        "timezone": config.LOCATION_TIMEZONE,
        "forecast_days": config.FORECAST_DAYS,
    }

    response = requests.get(config.OPEN_METEO_BASE_URL, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    current_raw = data.get("current", {})
    daily_raw = data.get("daily", {})

    current = {
        "temperature_c": current_raw.get("temperature_2m"),
        "humidity_percent": current_raw.get("relative_humidity_2m"),
        "weather_code": current_raw.get("weather_code"),
        "weather_description": _weather_description(current_raw.get("weather_code")),
        "wind_speed_kmh": current_raw.get("wind_speed_10m"),
    }

    forecast: list[dict[str, Any]] = []
    dates = daily_raw.get("time", [])
    max_temps = daily_raw.get("temperature_2m_max", [])
    min_temps = daily_raw.get("temperature_2m_min", [])
    weather_codes = daily_raw.get("weather_code", [])

    for index, date in enumerate(dates):
        code = weather_codes[index] if index < len(weather_codes) else None
        forecast.append(
            {
                "date": date,
                "temperature_max_c": max_temps[index] if index < len(max_temps) else None,
                "temperature_min_c": min_temps[index] if index < len(min_temps) else None,
                "weather_code": code,
                "weather_description": _weather_description(code),
            }
        )

    return _build_standardized_response(current=current, forecast=forecast)


@st.cache_data(ttl=config.WEATHER_CACHE_TTL_SECONDS, show_spinner=False)
def get_weather() -> dict[str, Any]:
    """
    Liefert aktuelles Wetter und Vorhersage als standardisiertes Dictionary.

    Rückgabe-Schema:
        {
            "location": str,
            "current": {
                "temperature_c": float | None,
                "humidity_percent": int | None,
                "weather_code": int | None,
                "weather_description": str,
                "wind_speed_kmh": float | None,
            },
            "forecast": [
                {
                    "date": str,  # YYYY-MM-DD
                    "temperature_max_c": float | None,
                    "temperature_min_c": float | None,
                    "weather_code": int | None,
                    "weather_description": str,
                },
                ...
            ],
            "fetched_at": str,  # ISO-8601 UTC
        }
    """
    return _fetch_weather_from_api()
