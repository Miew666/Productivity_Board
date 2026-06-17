"""Google-Tasks-Service mit OAuth und standardisiertem Rückgabeformat."""

from __future__ import annotations

from typing import Any

import streamlit as st
from googleapiclient.discovery import build

import config
from services import google_auth


def _build_tasks_service() -> Any | None:
    credentials = google_auth.get_valid_credentials(allow_interactive=False)
    if credentials is None:
        return None
    return build("tasks", "v1", credentials=credentials, cache_discovery=False)


def _parse_task(task: dict[str, Any], *, list_title: str, list_id: str) -> dict[str, Any]:
    """Mappt eine Google-Tasks-API-Aufgabe auf das standardisierte UI-Format."""
    due_raw = task.get("due")
    due_date = due_raw[:10] if due_raw else None

    return {
        "id": task.get("id", ""),
        "title": task.get("title") or "Ohne Titel",
        "due_date": due_date,
        "completed": task.get("status") == "completed",
        "list_title": list_title,
        "list_id": list_id,
        "updated": task.get("updated"),
    }


def _sort_tasks_newest(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(tasks, key=lambda task: task.get("updated") or "", reverse=True)


def _fetch_all_task_lists(service: Any) -> list[dict[str, Any]]:
    task_lists: list[dict[str, Any]] = []
    page_token: str | None = None

    while True:
        response = (
            service.tasklists()
            .list(maxResults=100, pageToken=page_token)
            .execute()
        )
        task_lists.extend(response.get("items", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return task_lists


def _find_task_list_by_title(
    task_lists: list[dict[str, Any]],
    title: str,
) -> dict[str, Any] | None:
    for task_list in task_lists:
        if task_list.get("title") == title:
            return task_list
    return None


def _fetch_tasks_for_list(service: Any, list_id: str) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    page_token: str | None = None

    while True:
        response = (
            service.tasks()
            .list(
                tasklist=list_id,
                maxResults=100,
                showCompleted=True,
                showHidden=False,
                pageToken=page_token,
            )
            .execute()
        )
        tasks.extend(response.get("items", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return tasks


def _fetch_tasks_from_source() -> dict[str, Any]:
    """
    Interne Datenquelle – Google Tasks API.
    Erwartetes Rückgabeformat:
        {
            "lists": [
                {
                    "list_title": str,
                    "list_id": str | None,
                    "tasks": [
                        {
                            "id": str,
                            "title": str,
                            "due_date": str | None,
                            "completed": bool,
                            "list_title": str,
                            "list_id": str,
                            "updated": str | None,
                        },
                        ...
                    ],
                    "error": str | None,
                },
                ...
            ],
            "error": str | None,
        }
    """
    service = _build_tasks_service()
    if service is None:
        return {"lists": [], "error": "Nicht authentifiziert"}

    all_lists = _fetch_all_task_lists(service)
    result_lists: list[dict[str, Any]] = []

    for list_title in config.GOOGLE_TASK_LIST_NAMES:
        task_list = _find_task_list_by_title(all_lists, list_title)

        if task_list is None:
            result_lists.append(
                {
                    "list_title": list_title,
                    "list_id": None,
                    "tasks": [],
                    "error": f"Liste nicht gefunden: {list_title}",
                }
            )
            continue

        list_id = task_list["id"]
        raw_tasks = _fetch_tasks_for_list(service, list_id)
        parsed_tasks = _sort_tasks_newest(
            [
                _parse_task(task, list_title=list_title, list_id=list_id)
                for task in raw_tasks
            ]
        )

        result_lists.append(
            {
                "list_title": list_title,
                "list_id": list_id,
                "tasks": parsed_tasks,
                "error": None,
            }
        )

    return {"lists": result_lists, "error": None}


def needs_authentication() -> bool:
    return google_auth.needs_authentication()


def authenticate() -> bool:
    """Startet den OAuth-Flow und leert den Tasks-Cache."""
    if google_auth.authenticate_interactive():
        get_tasks_by_lists.clear()
        return True
    return False


@st.cache_data(ttl=config.TASKS_CACHE_TTL_SECONDS, show_spinner=False)
def get_tasks_by_lists() -> dict[str, Any]:
    """
    Liefert Aufgaben der konfigurierten Google-Task-Listen.

    Die Tasks innerhalb jeder Liste sind nach Aktualisierung (neueste zuerst) sortiert.
    """
    try:
        return _fetch_tasks_from_source()
    except Exception as error:
        return {
            "lists": [
                {
                    "list_title": title,
                    "list_id": None,
                    "tasks": [],
                    "error": str(error),
                }
                for title in config.GOOGLE_TASK_LIST_NAMES
            ],
            "error": str(error),
        }


def get_upcoming_tasks() -> list[dict[str, Any]]:
    """
    Abwärtskompatibler Flach-Export aller Tasks aus allen konfigurierten Listen.
    """
    data = get_tasks_by_lists()
    tasks: list[dict[str, Any]] = []
    for task_list in data.get("lists", []):
        tasks.extend(task_list.get("tasks", []))
    return tasks
