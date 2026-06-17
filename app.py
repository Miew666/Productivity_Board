"""Productivity Board – Mobile-First Streamlit Dashboard."""

from __future__ import annotations

from datetime import date, datetime

import streamlit as st

import config
from services import (
    google_auth,
    google_calendar,
    google_gmail,
    google_tasks,
    train_schedule,
    weather,
)

# ---------------------------------------------------------------------------
# Session State – zentrale Initialisierung für spätere Filter/Refresh-Logik
# ---------------------------------------------------------------------------

_DEFAULT_SESSION_STATE: dict[str, object] = {
    "initialized": False,
    "last_refresh_at": None,
    "show_completed_tasks": False,
    "task_sort_by": "due_date",  # due_date | title
    "weather_data": None,
    "tasks_data": None,
    "calendar_data": None,
    "emails_data": None,
    "unread_email_count": None,
    "train_data": None,
}


def _init_session_state() -> None:
    for key, value in _DEFAULT_SESSION_STATE.items():
        if key not in st.session_state:
            st.session_state[key] = value
    st.session_state["initialized"] = True


def _load_data() -> None:
    """Lädt alle Service-Daten und speichert sie im Session State."""
    st.session_state["weather_data"] = weather.get_weather()
    st.session_state["tasks_data"] = google_tasks.get_tasks_by_lists()
    st.session_state["calendar_data"] = google_calendar.get_upcoming_events()
    st.session_state["emails_data"] = google_gmail.get_latest_emails()
    st.session_state["unread_email_count"] = google_gmail.get_unread_count()
    st.session_state["train_data"] = train_schedule.get_commute_schedule()
    st.session_state["last_refresh_at"] = datetime.now()


def _format_temperature(value: float | None) -> str:
    if value is None:
        return "–"
    return f"{value:.0f}°C"


def _format_due_date(due_date: str | None) -> str:
    if not due_date:
        return "Kein Datum"
    try:
        parsed = date.fromisoformat(due_date)
        return parsed.strftime("%d.%m.%Y")
    except ValueError:
        return due_date


def _format_event_datetime(value: str | None, all_day: bool) -> str:
    if not value:
        return "–"
    if all_day:
        try:
            return date.fromisoformat(value).strftime("%d.%m.%Y")
        except ValueError:
            return value
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return value


def _sort_tasks(tasks: list[dict], sort_by: str) -> list[dict]:
    if sort_by == "title":
        return sorted(tasks, key=lambda t: t.get("title", "").lower())
    return sorted(
        tasks,
        key=lambda t: (t.get("due_date") is None, t.get("due_date") or ""),
    )


def _filter_open_tasks(tasks: list[dict]) -> list[dict]:
    if st.session_state["show_completed_tasks"]:
        return tasks
    return [t for t in tasks if not t.get("completed")]


def _render_weather_compact(weather_data: dict) -> None:
    current = weather_data.get("current", {})
    with st.container(border=True):
        st.markdown(f"**{weather_data.get('location', config.LOCATION_NAME)}**")
        col_temp, col_desc = st.columns([1, 2])
        with col_temp:
            st.metric("Jetzt", _format_temperature(current.get("temperature_c")))
        with col_desc:
            st.write(current.get("weather_description", "–"))
            st.caption(
                f"💨 {current.get('wind_speed_kmh', '–')} km/h · "
                f"💧 {current.get('humidity_percent', '–')}%"
            )


def _render_weather_detail(weather_data: dict) -> None:
    current = weather_data.get("current", {})
    with st.container(border=True):
        st.subheader("Aktuell")
        st.metric("Temperatur", _format_temperature(current.get("temperature_c")))
        st.write(f"**{current.get('weather_description', '–')}**")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Wind", f"{current.get('wind_speed_kmh', '–')} km/h")
        with col2:
            st.metric("Luftfeuchtigkeit", f"{current.get('humidity_percent', '–')}%")

    st.subheader("Vorhersage")
    for day in weather_data.get("forecast", []):
        with st.container(border=True):
            col_date, col_temp, col_desc = st.columns([2, 2, 3])
            with col_date:
                st.write(f"**{_format_due_date(day.get('date'))}**")
            with col_temp:
                max_t = day.get("temperature_max_c")
                min_t = day.get("temperature_min_c")
                st.write(
                    f"{_format_temperature(max_t)} / {_format_temperature(min_t)}"
                )
            with col_desc:
                st.write(day.get("weather_description", "–"))


def _render_task_item(task: dict) -> None:
    status = "✅" if task.get("completed") else "⬜"
    due = _format_due_date(task.get("due_date"))
    st.markdown(f"{status} **{task.get('title', 'Ohne Titel')}**")
    st.caption(f"Fällig: {due}")


def _clear_google_caches() -> None:
    google_calendar.get_upcoming_events.clear()
    google_gmail.get_latest_emails.clear()
    google_gmail.get_unread_count.clear()
    google_tasks.get_tasks_by_lists.clear()


def _render_google_auth_prompt() -> None:
    if google_auth.is_cloud_deployment():
        st.warning(
            "Google-Anmeldung auf dem Server nur über Streamlit Secrets möglich. "
            "Bitte `[google_token][json_data]` und `[google_credentials][json_data]` prüfen."
        )
        return

    st.info("Google-Konto ist noch nicht verbunden (Kalender, Gmail & Tasks).")
    if st.button("Mit Google verbinden", type="primary"):
        try:
            if google_auth.authenticate_interactive():
                _clear_google_caches()
                _load_data()
                st.rerun()
        except FileNotFoundError as error:
            st.error(str(error))


def _format_email_date(date_value: str | None) -> str:
    if not date_value:
        return "–"
    try:
        parsed = datetime.fromisoformat(date_value)
        return parsed.strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return date_value


def _render_email_item(email: dict) -> None:
    st.markdown(f"**{email.get('from', 'Unbekannter Absender')}**")
    st.write(email.get("subject", "(Kein Betreff)"))
    st.caption(email.get("snippet", ""))
    date_label = _format_email_date(email.get("date"))
    if date_label != "–":
        st.caption(f"🕐 {date_label}")


def _render_emails_list(emails: list[dict]) -> None:
    if google_gmail.needs_authentication():
        _render_google_auth_prompt()
        return

    if not emails:
        st.info("Keine ungelesenen E-Mails im Posteingang.")
        return

    for email in emails:
        with st.container(border=True):
            _render_email_item(email)


def _render_unread_email_summary(unread_count: int) -> None:
    if google_gmail.needs_authentication():
        return

    with st.container(border=True):
        if unread_count == 0:
            st.write("Du hast **keine** ungelesenen Nachrichten.")
        elif unread_count == 1:
            st.write("Du hast **1** ungelesene Nachricht.")
        else:
            st.write(f"Du hast **{unread_count}** ungelesene Nachrichten.")


def _render_event_item(event: dict, *, compact: bool = False) -> None:
    title = event.get("title", "Ohne Titel")
    calendar_name = event.get("calendar_name")
    start_label = _format_event_datetime(
        event.get("start"),
        event.get("all_day", False),
    )
    location = event.get("location")

    if compact:
        st.markdown(f"**{title}**")
        if calendar_name:
            st.caption(calendar_name)
        st.caption(f"🕐 {start_label}")
        if location:
            st.caption(f"📍 {location}")
        return

    st.markdown(f"**{title}**")
    if calendar_name:
        st.caption(calendar_name)
    st.write(f"🕐 {start_label}")
    if location:
        st.write(f"📍 {location}")
    link = event.get("link")
    if link:
        st.link_button("In Google Calendar öffnen", link)


def _render_calendar_list(events: list[dict], limit: int | None = None) -> None:
    if google_calendar.needs_authentication():
        _render_google_auth_prompt()
        return

    display_events = events[:limit] if limit else events
    if not display_events:
        st.info("Keine anstehenden Termine.")
        return

    for event in display_events:
        with st.container(border=True):
            _render_event_item(event, compact=limit is not None)


def _render_tasks_list(tasks: list[dict], limit: int | None = None) -> None:
    filtered = _filter_open_tasks(tasks)
    sorted_tasks = _sort_tasks(filtered, st.session_state["task_sort_by"])
    display_tasks = sorted_tasks[:limit] if limit else sorted_tasks

    if not display_tasks:
        st.info("Keine Tasks vorhanden.")
        return

    for task in display_tasks:
        with st.container(border=True):
            _render_task_item(task)


def _render_task_lists(
    tasks_data: dict,
    *,
    limit_per_list: int,
) -> None:
    if google_tasks.needs_authentication():
        _render_google_auth_prompt()
        return

    if tasks_data.get("error"):
        st.warning(f"Tasks momentan nicht verfügbar: {tasks_data['error']}")

    task_lists = tasks_data.get("lists") or []
    if not task_lists:
        st.info("Keine Task-Listen gefunden.")
        return

    for task_list in task_lists:
        list_title = task_list.get("list_title", "Unbenannte Liste")
        list_error = task_list.get("error")
        tasks = task_list.get("tasks") or []

        st.subheader(list_title)

        if list_error:
            st.warning(list_error)
            continue

        _render_tasks_list(tasks, limit=limit_per_list)


def _render_overview_tab(
    weather_data: dict,
    tasks_data: dict,
    events: list[dict],
    unread_count: int,
) -> None:
    st.subheader("Wetter")
    _render_weather_compact(weather_data)

    st.subheader("E-Mails")
    _render_unread_email_summary(unread_count)

    st.subheader(f"Nächste {config.OVERVIEW_CALENDAR_LIMIT} Termine")
    _render_calendar_list(events, limit=config.OVERVIEW_CALENDAR_LIMIT)

    st.subheader("Tasks")
    _render_task_lists(
        tasks_data,
        limit_per_list=config.OVERVIEW_TASKS_PER_LIST,
    )


def _render_tasks_tab(tasks_data: dict) -> None:
    with st.container(border=True):
        col_filter, col_sort = st.columns(2)
        with col_filter:
            st.session_state["show_completed_tasks"] = st.toggle(
                "Erledigte anzeigen",
                value=st.session_state["show_completed_tasks"],
            )
        with col_sort:
            st.session_state["task_sort_by"] = st.selectbox(
                "Sortierung",
                options=["due_date", "title"],
                format_func=lambda x: "Fälligkeitsdatum" if x == "due_date" else "Titel",
                index=0 if st.session_state["task_sort_by"] == "due_date" else 1,
            )

    _render_task_lists(
        tasks_data,
        limit_per_list=config.TASKS_TAB_LIMIT_PER_LIST,
    )


def _render_weather_tab(weather_data: dict) -> None:
    _render_weather_detail(weather_data)
    fetched_at = weather_data.get("fetched_at")
    if fetched_at:
        st.caption(f"Zuletzt aktualisiert: {fetched_at}")


def _render_calendar_tab(events: list[dict]) -> None:
    st.subheader(f"Nächste {config.CALENDAR_EVENT_LIMIT} Termine")
    _render_calendar_list(events)


def _render_emails_tab(emails: list[dict]) -> None:
    st.subheader("Ungelesene E-Mails")
    _render_emails_list(emails)


def _format_connection_time(value: str | None) -> str:
    if not value:
        return "–"
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.strftime("%H:%M")
    except ValueError:
        return value


def _render_connection_item(connection: dict) -> None:
    departure = _format_connection_time(connection.get("departure"))
    arrival = _format_connection_time(connection.get("arrival"))
    duration = connection.get("duration_minutes")
    transfers = connection.get("transfers") or []
    line_names = connection.get("line_names") or []

    st.markdown(f"**{departure} → {arrival}**")
    st.write(f"Dauer: {duration} Min.")

    if line_names:
        st.caption(" · ".join(line_names))

    if transfers:
        st.caption(f"Umstieg: {', '.join(transfers)}")
    else:
        st.caption("Direktverbindung")


def _render_train_tab(train_data: dict) -> None:
    direction_label = train_data.get("direction_label", "–")
    st.subheader(f"Richtung: {direction_label}")

    if train_data.get("error"):
        st.warning(f"Zugdaten momentan nicht verfügbar: {train_data['error']}")

    connections = train_data.get("connections") or []
    if not connections and not train_data.get("error"):
        st.info("Keine Verbindungen gefunden.")
        return

    for connection in connections:
        delay = int(connection.get("delay_minutes") or 0)
        with st.container(border=True):
            if delay > 0:
                st.error(f"Verspätung: +{delay} Minuten")
            _render_connection_item(connection)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(
        page_title=config.APP_TITLE,
        page_icon=config.APP_ICON,
        layout=config.PAGE_LAYOUT,
        initial_sidebar_state="collapsed",
    )

    _init_session_state()

    if (
        st.session_state["weather_data"] is None
        or st.session_state["tasks_data"] is None
        or st.session_state["calendar_data"] is None
        or st.session_state["emails_data"] is None
        or st.session_state["unread_email_count"] is None
        or st.session_state["train_data"] is None
    ):
        _load_data()

    st.title(config.APP_TITLE)

    header_col, refresh_col = st.columns([4, 1])
    with refresh_col:
        if st.button("🔄", help="Daten aktualisieren", use_container_width=True):
            weather.get_weather.clear()
            _clear_google_caches()
            train_schedule.get_commute_schedule.clear()
            train_schedule.get_next_connections.clear()
            _load_data()
            st.rerun()

    with header_col:
        last_refresh = st.session_state.get("last_refresh_at")
        if last_refresh:
            st.caption(f"Aktualisiert: {last_refresh.strftime('%H:%M:%S')}")

    weather_data: dict = st.session_state["weather_data"] or {}
    tasks_data: dict = st.session_state["tasks_data"] or {}
    calendar_data: list[dict] = st.session_state["calendar_data"] or []
    emails_data: list[dict] = st.session_state["emails_data"] or []
    unread_email_count: int = st.session_state["unread_email_count"] or 0
    train_data: dict = st.session_state["train_data"] or {}

    tab_overview, tab_tasks, tab_calendar, tab_emails, tab_train, tab_weather = st.tabs(
        ["🏠 Übersicht", "✅ Tasks", "📅 Kalender", "✉️ Mails", "🚂 Zug", "☀️ Wetter"]
    )

    with tab_overview:
        _render_overview_tab(
            weather_data,
            tasks_data,
            calendar_data,
            unread_email_count,
        )

    with tab_tasks:
        _render_tasks_tab(tasks_data)

    with tab_calendar:
        _render_calendar_tab(calendar_data)

    with tab_emails:
        _render_emails_tab(emails_data)

    with tab_train:
        _render_train_tab(train_data)

    with tab_weather:
        _render_weather_tab(weather_data)


if __name__ == "__main__":
    main()
