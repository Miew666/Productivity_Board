"""Gemeinsame Google-OAuth-Authentifizierung für Kalender und Gmail."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

import config

SCOPES = config.GOOGLE_SCOPES


def _parse_json_data(raw_data: Any) -> dict[str, Any]:
    """Wandelt Secret- oder Datei-Inhalt in ein Dictionary um."""
    if isinstance(raw_data, dict):
        return raw_data
    if isinstance(raw_data, str):
        return json.loads(raw_data)
    raise ValueError("JSON-Daten müssen ein String oder Dictionary sein.")


def _load_json_from_secrets(section: str) -> dict[str, Any] | None:
    """Lädt JSON aus Streamlit Secrets: st.secrets[section]['json_data']."""
    try:
        secret_section = st.secrets[section]

        if hasattr(secret_section, "to_dict"):
            secret_section = secret_section.to_dict()
        elif not isinstance(secret_section, dict):
            secret_section = dict(secret_section)

        if "json_data" in secret_section:
            return _parse_json_data(secret_section["json_data"])

        # Fallback: Secret-Block enthält bereits die Felder direkt
        if section == "google_token" and (
            "token" in secret_section or "refresh_token" in secret_section
        ):
            return secret_section

        if section == "google_credentials" and (
            "installed" in secret_section or "web" in secret_section
        ):
            return secret_section
    except (KeyError, TypeError, json.JSONDecodeError, FileNotFoundError, AttributeError):
        return None

    return None


def _load_token_info() -> dict[str, Any] | None:
    if config.GOOGLE_TOKEN_PATH.exists():
        return _parse_json_data(
            config.GOOGLE_TOKEN_PATH.read_text(encoding="utf-8")
        )
    return _load_json_from_secrets("google_token")


def _load_client_config() -> dict[str, Any] | None:
    if config.GOOGLE_CREDENTIALS_PATH.exists():
        return _parse_json_data(
            config.GOOGLE_CREDENTIALS_PATH.read_text(encoding="utf-8")
        )
    return _load_json_from_secrets("google_credentials")


def _credentials_from_client_dict(client_config: dict[str, Any]) -> dict[str, Any]:
    """
    Normalisiert OAuth-Client-Credentials aus einem Dictionary.
    Unterstützt das Standardformat von credentials.json (Schlüssel 'installed').
    """
    if "installed" in client_config or "web" in client_config:
        return client_config
    return {"installed": client_config}


def _is_headless_environment() -> bool:
    """True auf Streamlit Cloud, wenn nur Secrets und keine lokalen Dateien existieren."""
    return (
        not config.GOOGLE_TOKEN_PATH.exists()
        and not config.GOOGLE_CREDENTIALS_PATH.exists()
    )


def _load_stored_credentials() -> Credentials | None:
    token_info = _load_token_info()
    if not token_info:
        return None

    credentials = Credentials.from_authorized_user_info(token_info, SCOPES)

    if not credentials.client_id or not credentials.client_secret:
        client_config = _load_client_config()
        if client_config:
            client_dict = _credentials_from_client_dict(client_config)
            installed = client_dict.get("installed") or client_dict.get("web") or {}
            credentials.client_id = credentials.client_id or installed.get("client_id")
            credentials.client_secret = (
                credentials.client_secret or installed.get("client_secret")
            )
            credentials.token_uri = credentials.token_uri or installed.get(
                "token_uri", "https://oauth2.googleapis.com/token"
            )

    return credentials


def _save_credentials(credentials: Credentials) -> None:
    """Speichert Token nur lokal – auf Streamlit Cloud bleiben Secrets unverändert."""
    if _is_headless_environment():
        return
    config.GOOGLE_TOKEN_PATH.write_text(credentials.to_json(), encoding="utf-8")


def _credentials_have_required_scopes(credentials: Credentials) -> bool:
    token_scopes = set(credentials.scopes or [])
    return all(scope in token_scopes for scope in SCOPES)


def get_valid_credentials(*, allow_interactive: bool = False) -> Credentials | None:
    credentials = _load_stored_credentials()

    if credentials and credentials.valid and _credentials_have_required_scopes(credentials):
        return credentials

    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        if _credentials_have_required_scopes(credentials):
            _save_credentials(credentials)
            return credentials

    if not allow_interactive:
        return None

    if _is_headless_environment():
        return None

    client_config = _load_client_config()
    if client_config is None:
        raise FileNotFoundError(
            "Weder credentials.json noch Streamlit-Secret "
            "[google_credentials][json_data] gefunden."
        )

    flow = InstalledAppFlow.from_client_config(
        _credentials_from_client_dict(client_config),
        SCOPES,
    )
    credentials = flow.run_local_server(port=0)
    _save_credentials(credentials)
    return credentials


def is_cloud_deployment() -> bool:
    """True, wenn die App ohne lokale Google-Dateien aus Secrets läuft."""
    return _is_headless_environment()


def needs_authentication() -> bool:
    """True, wenn noch kein gültiges Token mit allen Scopes vorhanden ist."""
    return get_valid_credentials(allow_interactive=False) is None


def authenticate_interactive() -> bool:
    """
    Startet den OAuth-Flow lokal und speichert token.json.
    Auf Streamlit Cloud ohne lokale Dateien wird kein Browser geöffnet.
    """
    if _is_headless_environment():
        return False

    credentials = get_valid_credentials(allow_interactive=True)
    return credentials is not None
