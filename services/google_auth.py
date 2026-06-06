"""Gemeinsame Google-OAuth-Authentifizierung für Kalender und Gmail."""

from __future__ import annotations

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

import config

SCOPES = config.GOOGLE_SCOPES


def _load_stored_credentials() -> Credentials | None:
    if not config.GOOGLE_TOKEN_PATH.exists():
        return None
    return Credentials.from_authorized_user_file(config.GOOGLE_TOKEN_PATH, SCOPES)


def _save_credentials(credentials: Credentials) -> None:
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
    """True, wenn noch kein gültiges Token mit allen Scopes vorhanden ist."""
    return get_valid_credentials(allow_interactive=False) is None


def authenticate_interactive() -> bool:
    """Startet den OAuth-Flow und speichert token.json."""
    credentials = get_valid_credentials(allow_interactive=True)
    return credentials is not None
