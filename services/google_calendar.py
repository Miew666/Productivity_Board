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


def _parse_start_for_sort(start: str | None, all_day: bool) -> datetime:
    """Normalisiert Startzeitpunkte für chronologische Sortierung."""
    if not start:
        return datetime.max.replace(tzinfo=timezone.utc)
    if all_day:
        parsed_date = datetime.fromisoformat(start).date()
        return datetime.combine(parsed_date, datetime.min.time(), tzinfo=timezone.utc)
    return datetime.fromisoformat(start.replace("Z", "+00:00"))


def _parse_event(
    event: dict[str, Any],
    *,
    calendar_id: str,
    calendar_name: str,
) -> dict[str, Any]:
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

    event_id = event.get("id", "")
    return {
        "id": f"{calendar_id}:{event_id}",
        "title": event.get("summary") or "Ohne Titel",
        "start": start_value,
        "end": end_value,
        "all_day": all_day,
        "location": event.get("location"),
        "link": event.get("htmlLink"),
        "calendar_id": calendar_id,
        "calendar_name": calendar_name,
    }


def _list_calendars(service: Any) -> list[dict[str, Any]]:
    """Ruft alle Kalender des Nutzers ab."""
    calendars: list[dict[str, Any]] = []
    page_token: str | None = None

    while True:
        response = (
            service.calendarList()
            .list(pageToken=page_token)
            .execute()
        )
        calendars.extend(response.get("items", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return calendars


def _fetch_events_for_calendar(
    service: Any,
    calendar: dict[str, Any],
    *,
    time_min: str,
    max_results: int,
) -> list[dict[str, Any]]:
    """Holt anstehende Termine für einen einzelnen Kalender."""
    calendar_id = calendar.get("id")
    if not calendar_id:
        return []

    calendar_name = calendar.get("summary") or "Unbenannter Kalender"

    try:
        response = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
    except Exception:
        return []

    return [
        _parse_event(
            event,
            calendar_id=calendar_id,
            calendar_name=calendar_name,
        )
        for event in response.get("items", [])
    ]


def _fetch_events_from_source() -> list[dict[str, Any]]:
    """
    Interne Datenquelle – Google Calendar API (alle Kalender aggregiert).
    Erwartetes Rückgabeformat pro Termin:
        {
            "id": str,
            "title": str,
            "start": str | None,
            "end": str | None,
            "all_day": bool,
            "location": str | None,
            "link": str | None,
            "calendar_id": str,
            "calendar_name": str,
        }
    """
    credentials = _get_valid_credentials(allow_interactive=False)
    if credentials is None:
        return []

    service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
    time_min = datetime.now(timezone.utc).isoformat()
    per_calendar_limit = max(config.CALENDAR_EVENT_LIMIT * 5, 25)

    all_events: list[dict[str, Any]] = []
    for calendar in _list_calendars(service):
        all_events.extend(
            _fetch_events_for_calendar(
                service,
                calendar,
                time_min=time_min,
                max_results=per_calendar_limit,
            )
        )

    all_events.sort(
        key=lambda event: _parse_start_for_sort(
            event.get("start"),
            event.get("all_day", False),
        )
    )

    return all_events[: config.CALENDAR_EVENT_LIMIT]


@st.cache_data(ttl=config.CALENDAR_CACHE_TTL_SECONDS, show_spinner=False)
def get_upcoming_events() -> list[dict[str, Any]]:
    """
    Liefert die nächsten Termine als standardisierte Liste von Dictionaries.

    Rückgabe-Schema (Liste, chronologisch sortiert):
        [
            {
                "id": str,
                "title": str,
                "start": str | None,
                "end": str | None,
                "all_day": bool,
                "location": str | None,
                "link": str | None,
                "calendar_id": str,
                "calendar_name": str,
            },
            ...
        ]
    """
    return _fetch_events_from_source()
