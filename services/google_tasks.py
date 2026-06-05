"""Google-Tasks-Service (aktuell Mock-Daten, später API/Webhook)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def _fetch_tasks_from_source() -> list[dict[str, Any]]:
    """
    Interne Datenquelle – hier später durch echten API-Aufruf oder
    Make.com-Webhook ersetzen. Die UI-Schicht bleibt unverändert.

    Erwartetes Rückgabeformat pro Task:
        {
            "id": str,
            "title": str,
            "due_date": str | None,  # YYYY-MM-DD
            "completed": bool,
        }
    """
    today = date.today()

    return [
        {
            "id": "task-001",
            "title": "Wochenplanung erstellen",
            "due_date": today.isoformat(),
            "completed": False,
        },
        {
            "id": "task-002",
            "title": "E-Mails aufräumen",
            "due_date": (today + timedelta(days=1)).isoformat(),
            "completed": False,
        },
        {
            "id": "task-003",
            "title": "Projekt-Dokumentation aktualisieren",
            "due_date": (today + timedelta(days=2)).isoformat(),
            "completed": False,
        },
        {
            "id": "task-004",
            "title": "Sport: Laufen 5 km",
            "due_date": (today + timedelta(days=3)).isoformat(),
            "completed": True,
        },
        {
            "id": "task-005",
            "title": "Steuerunterlagen sammeln",
            "due_date": None,
            "completed": False,
        },
    ]


def get_upcoming_tasks() -> list[dict[str, Any]]:
    """
    Liefert anstehende Tasks als standardisierte Liste von Dictionaries.

    Rückgabe-Schema (Liste):
        [
            {
                "id": str,
                "title": str,
                "due_date": str | None,
                "completed": bool,
            },
            ...
        ]
    """
    return _fetch_tasks_from_source()
