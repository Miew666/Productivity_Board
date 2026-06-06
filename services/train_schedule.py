"""Zugfahrplan-Service über die ÖBB-HAFAS-API."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import requests
import streamlit as st
from pyhafas import HafasClient
from pyhafas.types.fptf import Station

import config
from services.hafas_oebb import OEBBProfile

REQUEST_TIMEOUT_SECONDS = 15


def _format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo(config.LOCATION_TIMEZONE))
    return value.isoformat()


def _duration_to_minutes(duration: timedelta | None) -> int:
    if duration is None:
        return 0
    return max(0, int(duration.total_seconds() // 60))


def _resolve_station(client: HafasClient, station_name: str) -> Station:
    locations = client.locations(station_name)
    if not locations:
        raise LookupError(f"Bahnhof nicht gefunden: {station_name}")

    normalized_query = (
        station_name.casefold().replace(".", "").replace(" ", "")
    )

    for location in locations:
        if not location.name:
            continue
        normalized_name = location.name.casefold().replace(".", "").replace(" ", "")
        if normalized_name == normalized_query:
            return location

    for location in locations:
        if not location.name:
            continue
        if "bahnhst" in location.name.casefold():
            continue
        normalized_name = location.name.casefold().replace(".", "").replace(" ", "")
        if normalized_query in normalized_name:
            return location

    return locations[0]


def _station_name(common: dict[str, Any], point: dict[str, Any] | None) -> str | None:
    if not point:
        return None
    loc_index = point.get("locX")
    if loc_index is None:
        return None
    locations = common.get("locL", [])
    if loc_index >= len(locations):
        return None
    return locations[loc_index].get("name")


def _point_delay_minutes(
    profile: OEBBProfile,
    point: dict[str, Any],
    journey_date: date,
    *,
    is_arrival: bool,
) -> int:
    scheduled_key = "aTimeS" if is_arrival else "dTimeS"
    realtime_key = "aTimeR" if is_arrival else "dTimeR"

    scheduled = point.get(scheduled_key)
    realtime = point.get(realtime_key)
    if not scheduled or not realtime:
        return 0

    scheduled_dt = profile.parse_datetime(scheduled, journey_date)
    realtime_dt = profile.parse_datetime(realtime, journey_date)
    return max(0, _duration_to_minutes(realtime_dt - scheduled_dt))


def _point_datetime(
    profile: OEBBProfile,
    point: dict[str, Any],
    journey_date: date,
    *,
    is_arrival: bool,
) -> datetime | None:
    realtime_key = "aTimeR" if is_arrival else "dTimeR"
    scheduled_key = "aTimeS" if is_arrival else "dTimeS"
    time_value = point.get(realtime_key) or point.get(scheduled_key)
    if not time_value:
        return None
    return profile.parse_datetime(time_value, journey_date)


def _extract_transfers_from_sections(
    sections: list[dict[str, Any]],
    common: dict[str, Any],
) -> list[str]:
    train_sections = [section for section in sections if section.get("type") == "JNY"]
    transfers: list[str] = []

    for index in range(len(train_sections) - 1):
        arrival_point = train_sections[index].get("arr")
        station = _station_name(common, arrival_point)
        if station and station not in transfers:
            transfers.append(station)

    return transfers


def _max_delay_for_journey(
    profile: OEBBProfile,
    journey: dict[str, Any],
    common: dict[str, Any],
    journey_date: date,
) -> int:
    max_delay = 0

    for key, is_arrival in (("dep", False), ("arr", True)):
        point = journey.get(key)
        if point:
            max_delay = max(
                max_delay,
                _point_delay_minutes(profile, point, journey_date, is_arrival=is_arrival),
            )

    for section in journey.get("secL", []):
        if section.get("type") != "JNY":
            continue
        for key, is_arrival in (("dep", False), ("arr", True)):
            point = section.get(key)
            if point:
                max_delay = max(
                    max_delay,
                    _point_delay_minutes(
                        profile, point, journey_date, is_arrival=is_arrival
                    ),
                )

    return max_delay


def _line_names_from_sections(
    sections: list[dict[str, Any]],
    common: dict[str, Any],
) -> list[str]:
    line_names: list[str] = []

    for section in sections:
        if section.get("type") != "JNY":
            continue
        journey_part = section.get("jny", {})
        product_index = journey_part.get("prodX")
        products = common.get("prodL", [])
        if product_index is None or product_index >= len(products):
            continue
        product_name = products[product_index].get("nameS") or products[product_index].get("name")
        if product_name and product_name not in line_names:
            line_names.append(product_name)

    return line_names


def _parse_raw_journey(
    profile: OEBBProfile,
    journey: dict[str, Any],
    common: dict[str, Any],
    *,
    from_station: str,
    to_station: str,
) -> dict[str, Any]:
    journey_date = profile.parse_date(journey["date"])
    sections = journey.get("secL", [])

    departure = _point_datetime(profile, journey.get("dep", {}), journey_date, is_arrival=False)
    arrival = _point_datetime(profile, journey.get("arr", {}), journey_date, is_arrival=True)
    duration = profile.parse_timedelta(journey.get("dur", "000000"))

    return {
        "id": journey.get("recon", {}).get("ctx", journey.get("cid", "")),
        "from_station": from_station,
        "to_station": to_station,
        "departure": _format_datetime(departure),
        "arrival": _format_datetime(arrival),
        "duration_minutes": _duration_to_minutes(duration),
        "transfers": _extract_transfers_from_sections(sections, common),
        "delay_minutes": _max_delay_for_journey(profile, journey, common, journey_date),
        "line_names": _line_names_from_sections(sections, common),
    }


def _fetch_connections_from_source(
    from_station: str,
    to_station: str,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    profile = OEBBProfile()
    client = HafasClient(profile)
    profile.request_session.timeout = REQUEST_TIMEOUT_SECONDS

    origin = _resolve_station(client, from_station)
    destination = _resolve_station(client, to_station)
    now = datetime.now(ZoneInfo(config.LOCATION_TIMEZONE))
    search_time = profile.transform_datetime_parameter_timezone(now)

    trip_search_body = profile.format_journeys_request(
        origin,
        destination,
        [],
        search_time,
        0,
        -1,
        {},
        limit,
    )
    payload = {
        "svcReqL": [trip_search_body],
        **profile.requestBody,
    }

    response = requests.post(
        profile.baseUrl,
        data=json.dumps(payload),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "ProductivityBoard/1.0",
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()

    if data.get("err", "OK") != "OK":
        raise RuntimeError(data.get("errTxt", "ÖBB-Anfrage fehlgeschlagen"))

    service_result = data.get("svcResL", [{}])[0]
    if service_result.get("err", "OK") != "OK":
        raise RuntimeError(service_result.get("errTxt", "ÖBB-Anfrage fehlgeschlagen"))

    result = service_result.get("res", {})
    journeys = result.get("outConL", [])
    common = result.get("common", {})

    return [
        _parse_raw_journey(
            profile,
            journey,
            common,
            from_station=from_station,
            to_station=to_station,
        )
        for journey in journeys[:limit]
    ]


def get_commute_direction() -> tuple[str, str, str]:
    """
    Ermittelt die Pendelrichtung anhand der Tageszeit.

    Returns:
        (from_station, to_station, direction_label)
    """
    now = datetime.now(ZoneInfo(config.LOCATION_TIMEZONE))

    if now.hour < config.TRAIN_MORNING_UNTIL_HOUR:
        from_station = config.TRAIN_HOME_STATION
        to_station = config.TRAIN_WORK_STATION
    else:
        from_station = config.TRAIN_WORK_STATION
        to_station = config.TRAIN_HOME_STATION

    direction_label = f"{from_station} ➔ {to_station}"
    return from_station, to_station, direction_label


def _empty_schedule(
    *,
    from_station: str,
    to_station: str,
    direction_label: str,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "from_station": from_station,
        "to_station": to_station,
        "direction_label": direction_label,
        "connections": [],
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "error": error,
    }


@st.cache_data(ttl=config.TRAIN_CACHE_TTL_SECONDS, show_spinner=False)
def get_next_connections(
    from_station: str,
    to_station: str,
    limit: int = config.TRAIN_CONNECTION_LIMIT,
) -> list[dict[str, Any]]:
    """
    Liefert die nächsten Zugverbindungen als standardisierte Liste.

    Rückgabe-Schema pro Verbindung:
        {
            "id": str,
            "from_station": str,
            "to_station": str,
            "departure": str | None,
            "arrival": str | None,
            "duration_minutes": int,
            "transfers": list[str],
            "delay_minutes": int,
            "line_names": list[str],
        }
    """
    try:
        return _fetch_connections_from_source(
            from_station,
            to_station,
            limit=limit,
        )
    except Exception:
        return []


@st.cache_data(ttl=config.TRAIN_CACHE_TTL_SECONDS, show_spinner=False)
def get_commute_schedule(
    limit: int = config.TRAIN_CONNECTION_LIMIT,
) -> dict[str, Any]:
    """Liefert Pendelverbindungen inklusive Richtung und Metadaten."""
    from_station, to_station, direction_label = get_commute_direction()

    try:
        connections = _fetch_connections_from_source(
            from_station,
            to_station,
            limit=limit,
        )
        return {
            "from_station": from_station,
            "to_station": to_station,
            "direction_label": direction_label,
            "connections": connections,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "error": None,
        }
    except Exception as error:
        return _empty_schedule(
            from_station=from_station,
            to_station=to_station,
            direction_label=direction_label,
            error=str(error),
        )
