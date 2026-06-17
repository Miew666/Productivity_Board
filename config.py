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
GMAIL_CACHE_TTL_SECONDS = 5 * 60  # 5 Minuten

# Google APIs (Kalender + Gmail + Tasks)
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/tasks.readonly",
]
GOOGLE_TASK_LIST_NAMES = [
    "Aufgabenkorb",
    "To-do List für Pam u. Basti",
]
OVERVIEW_TASKS_PER_LIST = 1
TASKS_TAB_LIMIT_PER_LIST = 5
GOOGLE_CALENDAR_ID = "primary"
CALENDAR_EVENT_LIMIT = 5
OVERVIEW_CALENDAR_LIMIT = 2
GMAIL_MAX_RESULTS = 5

# Zug / ÖBB Pendelstrecke
TRAIN_HOME_STATION = "St. Georgen am Steinfelde"
TRAIN_WORK_STATION = "Wien Meidling"
TRAIN_CONNECTION_LIMIT = 3
TRAIN_MORNING_UNTIL_HOUR = 12  # vor 12:00 Uhr: Heimat -> Arbeit
TRAIN_CACHE_TTL_SECONDS = 120  # 2 Minuten

# Open-Meteo API
OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1/forecast"

# App-Einstellungen
APP_TITLE = "Productivity Board"
APP_ICON = "📋"
FORECAST_DAYS = 5

# UI
PAGE_LAYOUT = "wide"
