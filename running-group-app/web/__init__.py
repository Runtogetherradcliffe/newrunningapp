"""
Web UI for Running Group App.

Streamlit-based interface for:
- Group settings and setup
- Message composition
- Calendar sync management
"""

from .google_auth import (
    render_google_oauth_button,
    get_google_oauth_credentials,
    clear_credentials as clear_google_credentials,
)

from .strava_auth import (
    render_strava_oauth_button,
    get_access_token as get_strava_token,
    clear_credentials as clear_strava_credentials,
)

__all__ = [
    "render_google_oauth_button",
    "get_google_oauth_credentials",
    "clear_google_credentials",
    "render_strava_oauth_button",
    "get_strava_token",
    "clear_strava_credentials",
]
