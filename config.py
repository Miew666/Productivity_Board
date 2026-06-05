"""Globale Konstanten und App-Einstellungen."""

from pathlib import Path

# Projektpfade
PROJECT_ROOT = Path(__file__).resolve().parent
GOOGLE_CREDENTIALS_PATH = PROJECT_ROOT / "credentials.json"
GOOGLE_TOKEN_PATH = PROJECT_ROOT / "token.json"

# Standort: St. Pölten, Österreich
LOCATION_NAME = "St. Pölten"
LOCATION_LATITUDE = 48.2047
LOCATION_LONGITUDE = 15.6258
LOCATION_TIMEZONE = "Europe/Vienna"

# Cache-Zeiten (Sekunden)
WEATHER_CACHE_TTL_SECONDS = 15 * 60  # 15 Minuten
TASKS_CACHE_TTL_SECONDS = 5 * 60  # 5 Minuten (für spätere API-Integration)
CALENDAR_CACHE_TTL_SECONDS = 15 * 60  # 15 Minuten

# Google Calendar API
GOOGLE_CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
GOOGLE_CALENDAR_ID = "primary"
CALENDAR_EVENT_LIMIT = 5
OVERVIEW_CALENDAR_LIMIT = 2

# Open-Meteo API
OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1/forecast"

# App-Einstellungen
APP_TITLE = "Productivity Board"
APP_ICON = "📋"
OVERVIEW_TASK_LIMIT = 3
FORECAST_DAYS = 5

# UI
PAGE_LAYOUT = "wide"
