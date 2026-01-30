"""
Google OAuth authentication for Streamlit.

Handles the OAuth flow for Google Calendar and Sheets access.
Uses streamlit-oauth or manual flow depending on deployment.
"""

import json
from typing import Optional, Tuple
from dataclasses import dataclass
import streamlit as st

# Google OAuth scopes we need
SCOPES = [
    "https://www.googleapis.com/auth/calendar",  # Full calendar access
    "https://www.googleapis.com/auth/spreadsheets.readonly",  # Read sheets
]


@dataclass
class GoogleCredentials:
    """Stored Google OAuth credentials."""
    access_token: str
    refresh_token: str
    token_uri: str = "https://oauth2.googleapis.com/token"
    client_id: str = ""
    client_secret: str = ""
    expiry: Optional[str] = None


def get_google_client_config() -> Optional[dict]:
    """
    Get Google OAuth client configuration.

    Looks for credentials in:
    1. Streamlit secrets (google.client_id, google.client_secret)
    2. Environment variables
    3. credentials.json file
    """
    # Try Streamlit secrets first
    try:
        client_id = st.secrets.get("google", {}).get("client_id")
        client_secret = st.secrets.get("google", {}).get("client_secret")

        if client_id and client_secret:
            return {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost:8501"],
                }
            }
    except Exception:
        pass

    # Try environment variables
    import os
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")

    if client_id and client_secret:
        return {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost:8501"],
            }
        }

    return None


def get_stored_credentials() -> Optional[GoogleCredentials]:
    """Get stored Google credentials from session state."""
    if "google_credentials" in st.session_state:
        creds_data = st.session_state.google_credentials
        if isinstance(creds_data, dict):
            return GoogleCredentials(**creds_data)
        return creds_data
    return None


def store_credentials(credentials: GoogleCredentials):
    """Store Google credentials in session state."""
    st.session_state.google_credentials = {
        "access_token": credentials.access_token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "expiry": credentials.expiry,
    }
    st.session_state.google_connected = True


def clear_credentials():
    """Clear stored Google credentials."""
    if "google_credentials" in st.session_state:
        del st.session_state.google_credentials
    st.session_state.google_connected = False


def get_google_oauth_credentials():
    """
    Get google.oauth2.credentials.Credentials object for API calls.

    Returns None if not authenticated.
    """
    stored = get_stored_credentials()
    if not stored:
        return None

    try:
        from google.oauth2.credentials import Credentials

        return Credentials(
            token=stored.access_token,
            refresh_token=stored.refresh_token,
            token_uri=stored.token_uri,
            client_id=stored.client_id,
            client_secret=stored.client_secret,
        )
    except ImportError:
        st.error("Google auth libraries not installed. Run: pip install google-auth-oauthlib")
        return None


def render_google_oauth_button() -> bool:
    """
    Render the Google OAuth connect button and handle the flow.

    Returns True if successfully connected.
    """
    client_config = get_google_client_config()

    if not client_config:
        st.error("""
        **Google OAuth not configured.**

        Add to your Streamlit secrets (`.streamlit/secrets.toml`):
        ```toml
        [google]
        client_id = "your-client-id.apps.googleusercontent.com"
        client_secret = "your-client-secret"
        ```

        Or set environment variables:
        - `GOOGLE_CLIENT_ID`
        - `GOOGLE_CLIENT_SECRET`
        """)
        return False

    # Check if we already have credentials
    if get_stored_credentials():
        return True

    # Check for auth code in URL params (callback from OAuth)
    query_params = st.query_params
    auth_code = query_params.get("code")

    if auth_code:
        # Exchange code for tokens
        try:
            from google_auth_oauthlib.flow import Flow

            flow = Flow.from_client_config(
                client_config,
                scopes=SCOPES,
                redirect_uri=_get_redirect_uri(),
            )

            flow.fetch_token(code=auth_code)
            credentials = flow.credentials

            store_credentials(GoogleCredentials(
                access_token=credentials.token,
                refresh_token=credentials.refresh_token,
                token_uri=credentials.token_uri,
                client_id=credentials.client_id,
                client_secret=credentials.client_secret,
                expiry=credentials.expiry.isoformat() if credentials.expiry else None,
            ))

            # Clear the code from URL
            st.query_params.clear()
            st.success("✅ Connected to Google!")
            st.rerun()
            return True

        except Exception as e:
            st.error(f"Failed to complete OAuth: {e}")
            st.query_params.clear()
            return False

    # Show connect button
    try:
        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=_get_redirect_uri(),
        )

        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )

        st.link_button("🔗 Connect Google Account", auth_url, type="primary")

        st.caption("""
        This will allow the app to:
        - Create and manage your group's calendar
        - Read your Google Sheets
        """)

        return False

    except ImportError:
        st.error("Google auth libraries not installed. Run: pip install google-auth-oauthlib")
        return False


def _get_redirect_uri() -> str:
    """Get the OAuth redirect URI based on current URL."""
    import os

    # 1. Check Streamlit secrets first
    try:
        redirect_uri = st.secrets.get("google", {}).get("redirect_uri")
        if redirect_uri:
            return redirect_uri
    except Exception:
        pass

    # 2. Check environment variable
    env_url = os.environ.get("STREAMLIT_URL")
    if env_url:
        return env_url

    # 3. Try to detect from Streamlit Cloud hostname
    try:
        # On Streamlit Cloud, check if we're on a .streamlit.app domain
        import streamlit.web.server.websocket_headers as headers
        host = headers._get_websocket_headers().get("Host", "")
        if "streamlit.app" in host:
            return f"https://{host}/"
    except Exception:
        pass

    # 4. Default to localhost for local development
    return "http://localhost:8501/"


def refresh_credentials_if_needed() -> bool:
    """
    Refresh Google credentials if they're expired.

    Returns True if credentials are valid (refreshed or not expired).
    """
    credentials = get_google_oauth_credentials()
    if not credentials:
        return False

    try:
        if credentials.expired and credentials.refresh_token:
            from google.auth.transport.requests import Request
            credentials.refresh(Request())

            # Update stored credentials
            stored = get_stored_credentials()
            stored.access_token = credentials.token
            stored.expiry = credentials.expiry.isoformat() if credentials.expiry else None
            store_credentials(stored)

        return True

    except Exception as e:
        st.warning(f"Failed to refresh credentials: {e}")
        clear_credentials()
        return False
