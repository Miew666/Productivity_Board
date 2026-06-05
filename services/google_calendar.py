"""Google-Calendar-Service mit OAuth und standardisiertem Rückgabeformat."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import streamlit as st
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

import config

SCOPES = config.GOOGLE_CALENDAR_SCOPES


def _load_stored_credentials() -> Credentials | None:
    if not config.GOOGLE_TOKEN_PATH.exists():
        return None
    return Credentials.from_authorized_user_file(config.GOOGLE_TOKEN_PATH, SCOPES)


def _save_credentials(credentials: Credentials) -> None:
    config.GOOGLE_TOKEN_PATH.write_text(credentials.to_json(), encoding="utf-8")


def _get_valid_credentials(*, allow_interactive: bool = False) -> Credentials | None:
    credentials = _load_stored_credentials()

    if credentials and credentials.valid:
        return credentials

    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        _save_credentials(credentials)
        return credentials

    if not allow_interactive:
        return None

    if not config.GOOGLE_CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            f"credentials.json nicht gefunden: {config.GOOGLE_CREDENTIALS_PATH}"
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(config.GOOGLE_CREDENTIALS_PATH),
        SCOPES,
    )
    credentials = flow.run_local_server(port=0)
    _save_credentials(credentials)
    return credentials


def needs_authentication() -> bool:
    """True, wenn noch kein gültiges Token vorhanden ist."""
    return _get_valid_credentials(allow_interactive=False) is None


def authenticate() -> bool:
    """
    Startet den OAuth-Flow und speichert token.json.
    Gibt True zurück, wenn die Authentifizierung erfolgreich war.
    """
    credentials = _get_valid_credentials(allow_interactive=True)
    if credentials:
        get_upcoming_events.clear()
        return True
    return False


def _parse_event(event: dict[str, Any]) -> dict[str, Any]:
    """Mappt ein Google-API-Event auf das standardisierte UI-Format."""
    start = event.get("start", {})
    end = event.get("end", {})
    all_day = "date" in start

    if all_day:
        start_value = start.get("date")
        end_value = end.get("date")
    else:
        start_value = start.get("dateTime")
        end_value = end.get("dateTime")

    return {
        "id": event.get("id", ""),
        "title": event.get("summary") or "Ohne Titel",
        "start": start_value,
        "end": end_value,
        "all_day": all_day,
        "location": event.get("location"),
        "link": event.get("htmlLink"),
    }


def _fetch_events_from_source() -> list[dict[str, Any]]:
    """
    Interne Datenquelle – Google Calendar API.
    Erwartetes Rückgabeformat pro Termin:
        {
            "id": str,
            "title": str,
            "start": str | None,
            "end": str | None,
            "all_day": bool,
            "location": str | None,
            "link": str | None,
        }
    """
    credentials = _get_valid_credentials(allow_interactive=False)
    if credentials is None:
        return []

    service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
    time_min = datetime.now(timezone.utc).isoformat()

    response = (
        service.events()
        .list(
            calendarId=config.GOOGLE_CALENDAR_ID,
            timeMin=time_min,
            maxResults=config.CALENDAR_EVENT_LIMIT,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    return [_parse_event(event) for event in response.get("items", [])]


@st.cache_data(ttl=config.CALENDAR_CACHE_TTL_SECONDS, show_spinner=False)
def get_upcoming_events() -> list[dict[str, Any]]:
    """
    Liefert die nächsten Termine als standardisierte Liste von Dictionaries.

    Rückgabe-Schema (Liste):
        [
            {
                "id": str,
                "title": str,
                "start": str | None,
                "end": str | None,
                "all_day": bool,
                "location": str | None,
                "link": str | None,
            },
            ...
        ]
    """
    return _fetch_events_from_source()
