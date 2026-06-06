"""Gmail-Service mit OAuth und standardisiertem Rückgabeformat."""

from __future__ import annotations

from email.utils import parsedate_to_datetime
from typing import Any

import streamlit as st
from googleapiclient.discovery import build

import config
from services import google_auth


def _get_header(headers: list[dict[str, str]], name: str) -> str:
    for header in headers:
        if header.get("name", "").lower() == name.lower():
            return header.get("value", "")
    return ""


def _parse_email(message: dict[str, Any]) -> dict[str, Any]:
    """Mappt eine Gmail-API-Nachricht auf das standardisierte UI-Format."""
    payload = message.get("payload", {})
    headers = payload.get("headers", [])
    date_raw = _get_header(headers, "Date")

    try:
        date_value = (
            parsedate_to_datetime(date_raw).isoformat() if date_raw else None
        )
    except (TypeError, ValueError, OverflowError):
        date_value = date_raw or None

    return {
        "id": message.get("id", ""),
        "from": _get_header(headers, "From") or "Unbekannter Absender",
        "subject": _get_header(headers, "Subject") or "(Kein Betreff)",
        "date": date_value,
        "snippet": message.get("snippet", ""),
    }


def _build_gmail_service() -> Any | None:
    credentials = google_auth.get_valid_credentials(allow_interactive=False)
    if credentials is None:
        return None
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def _fetch_unread_count_from_source() -> int:
    service = _build_gmail_service()
    if service is None:
        return 0

    label = service.users().labels().get(userId="me", id="INBOX").execute()
    return int(label.get("messagesUnread", 0))


def _fetch_latest_emails_from_source(max_results: int) -> list[dict[str, Any]]:
    """
    Interne Datenquelle – Gmail API (ungelesene Mails im Posteingang).
    Erwartetes Rückgabeformat pro Mail:
        {
            "id": str,
            "from": str,
            "subject": str,
            "date": str | None,
            "snippet": str,
        }
    """
    service = _build_gmail_service()
    if service is None:
        return []

    response = (
        service.users()
        .messages()
        .list(
            userId="me",
            labelIds=["INBOX", "UNREAD"],
            maxResults=max_results,
        )
        .execute()
    )

    emails: list[dict[str, Any]] = []
    for item in response.get("messages", []):
        message_id = item.get("id")
        if not message_id:
            continue

        message = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=message_id,
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            )
            .execute()
        )
        emails.append(_parse_email(message))

    return emails


def needs_authentication() -> bool:
    return google_auth.needs_authentication()


def authenticate() -> bool:
    """Startet den OAuth-Flow und leert den Gmail-Cache."""
    if google_auth.authenticate_interactive():
        get_latest_emails.clear()
        get_unread_count.clear()
        from services import google_calendar

        google_calendar.get_upcoming_events.clear()
        return True
    return False


@st.cache_data(ttl=config.GMAIL_CACHE_TTL_SECONDS, show_spinner=False)
def get_unread_count() -> int:
    """Liefert die Anzahl ungelesener Nachrichten im Posteingang."""
    return _fetch_unread_count_from_source()


@st.cache_data(ttl=config.GMAIL_CACHE_TTL_SECONDS, show_spinner=False)
def get_latest_emails(max_results: int = config.GMAIL_MAX_RESULTS) -> list[dict[str, Any]]:
    """
    Liefert die neuesten ungelesenen E-Mails aus dem Posteingang.

    Rückgabe-Schema (Liste):
        [
            {
                "id": str,
                "from": str,
                "subject": str,
                "date": str | None,
                "snippet": str,
            },
            ...
        ]
    """
    return _fetch_latest_emails_from_source(max_results=max_results)
