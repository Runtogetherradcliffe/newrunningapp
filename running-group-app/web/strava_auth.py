"""
Strava OAuth authentication for Streamlit.

Handles the OAuth flow for Strava API access to get route data.
This is optional - the app works without Strava, just with less route detail.
"""

from typing import Optional
from dataclasses import dataclass
import requests
import streamlit as st


@dataclass
class StravaCredentials:
    """Stored Strava OAuth credentials."""
    access_token: str
    refresh_token: str
    expires_at: int = 0


def get_strava_client_config() -> tuple[Optional[str], Optional[str]]:
    """
    Get Strava OAuth client configuration.

    Returns (client_id, client_secret) or (None, None) if not configured.
    """
    # Try Streamlit secrets first
    try:
        client_id = st.secrets.get("strava", {}).get("client_id")
        client_secret = st.secrets.get("strava", {}).get("client_secret")

        if client_id and client_secret:
            return str(client_id), str(client_secret)
    except Exception:
        pass

    # Try environment variables
    import os
    client_id = os.environ.get("STRAVA_CLIENT_ID")
    client_secret = os.environ.get("STRAVA_CLIENT_SECRET")

    if client_id and client_secret:
        return client_id, client_secret

    return None, None


def get_stored_credentials() -> Optional[StravaCredentials]:
    """Get stored Strava credentials from session state."""
    if "strava_credentials" in st.session_state:
        creds_data = st.session_state.strava_credentials
        if isinstance(creds_data, dict):
            return StravaCredentials(**creds_data)
        return creds_data
    return None


def store_credentials(credentials: StravaCredentials):
    """Store Strava credentials in session state."""
    st.session_state.strava_credentials = {
        "access_token": credentials.access_token,
        "refresh_token": credentials.refresh_token,
        "expires_at": credentials.expires_at,
    }
    st.session_state.strava_connected = True


def clear_credentials():
    """Clear stored Strava credentials."""
    if "strava_credentials" in st.session_state:
        del st.session_state.strava_credentials
    st.session_state.strava_connected = False


def get_access_token() -> Optional[str]:
    """
    Get a valid Strava access token.

    Refreshes the token if needed.
    Returns None if not authenticated.
    """
    stored = get_stored_credentials()
    if not stored:
        return None

    # Check if token is expired (with 5 min buffer)
    import time
    if stored.expires_at < time.time() + 300:
        # Refresh the token
        if not refresh_token():
            return None
        stored = get_stored_credentials()

    return stored.access_token if stored else None


def refresh_token() -> bool:
    """
    Refresh the Strava access token.

    Returns True if successful.
    """
    stored = get_stored_credentials()
    if not stored or not stored.refresh_token:
        return False

    client_id, client_secret = get_strava_client_config()
    if not client_id or not client_secret:
        return False

    try:
        response = requests.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
                "refresh_token": stored.refresh_token,
            },
            timeout=15,
        )

        if response.ok:
            data = response.json()
            store_credentials(StravaCredentials(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token", stored.refresh_token),
                expires_at=data.get("expires_at", 0),
            ))
            return True

    except Exception as e:
        st.warning(f"Failed to refresh Strava token: {e}")

    return False


def render_strava_oauth_button() -> bool:
    """
    Render the Strava OAuth connect button and handle the flow.

    Returns True if successfully connected.
    """
    client_id, client_secret = get_strava_client_config()

    if not client_id:
        st.info("""
        **Strava not configured** (optional)

        To enable Strava route enrichment, add to your Streamlit secrets:
        ```toml
        [strava]
        client_id = "your-client-id"
        client_secret = "your-client-secret"
        ```
        """)
        return False

    # Check if we already have credentials
    if get_stored_credentials():
        return True

    # Check for auth code in URL params (callback from OAuth)
    query_params = st.query_params
    auth_code = query_params.get("code")
    scope = query_params.get("scope", "")

    # Only process if it looks like a Strava callback (has activity scope)
    if auth_code and "activity" in scope:
        try:
            response = requests.post(
                "https://www.strava.com/oauth/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": auth_code,
                    "grant_type": "authorization_code",
                },
                timeout=15,
            )

            if response.ok:
                data = response.json()
                store_credentials(StravaCredentials(
                    access_token=data["access_token"],
                    refresh_token=data["refresh_token"],
                    expires_at=data.get("expires_at", 0),
                ))

                st.query_params.clear()
                st.success("✅ Connected to Strava!")
                st.rerun()
                return True
            else:
                st.error(f"Strava OAuth failed: {response.text}")

        except Exception as e:
            st.error(f"Failed to complete Strava OAuth: {e}")

        st.query_params.clear()
        return False

    # Show connect button
    redirect_uri = _get_redirect_uri()
    auth_url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&approval_prompt=auto"
        f"&scope=read,activity:read,read_all"
    )

    st.link_button("🔗 Connect Strava", auth_url)

    st.caption("""
    Strava connection allows the app to:
    - Get route distance and elevation
    - Display route details in messages

    This is optional - the app works without it.
    """)

    return False


def _get_redirect_uri() -> str:
    """Get the OAuth redirect URI."""
    import os
    return os.environ.get("STREAMLIT_URL", "http://localhost:8501")
