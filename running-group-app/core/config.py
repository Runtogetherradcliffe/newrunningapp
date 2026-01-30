"""
Configuration management for Running Group App.

This module handles all group-specific settings. Config can be loaded from:
- A "Settings" tab in the group's Google Sheet
- Environment variables / Streamlit secrets (for API keys)
- Defaults (sensible fallbacks)

Designed to be UI-agnostic so it works with both web (Streamlit) and future mobile API.
"""

from dataclasses import dataclass, field
from typing import Optional
import os


@dataclass
class GroupConfig:
    """Core group identity and settings."""
    name: str = "My Running Group"
    short_name: str = ""
    timezone: str = "Europe/London"

    # Location (for weather forecasts)
    latitude: float = 53.561  # Default: Radcliffe, UK
    longitude: float = -2.329

    # Meeting defaults
    default_meeting_location: str = "Town Centre"
    default_start_time: str = "19:00"

    # Run day (0=Monday, 3=Thursday, 6=Sunday)
    run_day_of_week: int = 3  # Thursday

    def __post_init__(self):
        if not self.short_name:
            # Generate short name from initials
            self.short_name = "".join(word[0].upper() for word in self.name.split() if word)


@dataclass
class SheetConfig:
    """Google Sheets data source configuration."""
    spreadsheet_id: str = ""
    schedule_tab_name: str = "Schedule"
    settings_tab_name: str = "Settings"

    # Column mappings (can be customised per group)
    columns: dict = field(default_factory=lambda: {
        "date": "Date (Thu)",
        "route_1_name": "Route 1 - Name",
        "route_1_url": "Route 1 - Route Link (Source URL)",
        "route_1_distance": "Route 1 - Distance (km)",
        "route_2_name": "Route 2 - Name",
        "route_2_url": "Route 2 - Route Link (Source URL)",
        "route_2_distance": "Route 2 - Distance (km)",
        "route_3_name": "Route 3 name",
        "route_3_url": "Route 3 URL",
        "route_3_description": "Route 3 description",
        "meeting_point": "Meeting Point",
        "notes": "Notes",
    })


@dataclass
class CalendarConfig:
    """Google Calendar configuration."""
    calendar_id: Optional[str] = None  # Created during setup
    calendar_name: str = ""  # e.g., "Townsville Runners Schedule"

    # Event defaults
    event_duration_minutes: int = 60
    description_marker: str = "Managed by Running Group App"


@dataclass
class BookingConfig:
    """Booking platform links (varies by group/platform)."""
    booking_url: str = ""
    cancellation_url: str = ""
    ios_app_url: str = ""
    android_app_url: str = ""
    web_schedule_url: str = ""


@dataclass
class MessageConfig:
    """Message content customisation."""
    # Safety notes
    dark_running_note: str = "As we are now running after dark, please remember lights and hi-viz, be safe, be seen!"

    # Temperature thresholds (Celsius)
    cold_threshold: float = 5.0
    hot_threshold: float = 22.0

    # Default messages (groups can override)
    cold_weather_note: str = "It's looking cold around session time – layer up, hats and gloves recommended ❄️"
    hot_weather_note: str = "It's going to be a warm one – bring water and dress for the heat ☀️"


@dataclass
class NoRunDates:
    """Dates when runs don't happen."""
    # Fixed annual dates as (month, day) tuples
    annual_holidays: list = field(default_factory=lambda: [
        (12, 25),  # Christmas Day
        (12, 26),  # Boxing Day
        (1, 1),    # New Year's Day
    ])

    # Specific dates (ISO format strings)
    specific_dates: list = field(default_factory=list)

    def is_no_run(self, date) -> bool:
        """Check if a given date is a no-run date."""
        if hasattr(date, 'month') and hasattr(date, 'day'):
            if (date.month, date.day) in self.annual_holidays:
                return True

        date_str = str(date)[:10]  # Get YYYY-MM-DD
        return date_str in self.specific_dates


@dataclass
class AppConfig:
    """Complete application configuration."""
    group: GroupConfig = field(default_factory=GroupConfig)
    sheet: SheetConfig = field(default_factory=SheetConfig)
    calendar: CalendarConfig = field(default_factory=CalendarConfig)
    booking: BookingConfig = field(default_factory=BookingConfig)
    messages: MessageConfig = field(default_factory=MessageConfig)
    no_run_dates: NoRunDates = field(default_factory=NoRunDates)

    # Feature flags
    strava_enabled: bool = True
    weather_enabled: bool = True
    calendar_sync_enabled: bool = True


# Global config instance (loaded once, used everywhere)
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """Get the current configuration. Creates default if not loaded."""
    global _config
    if _config is None:
        _config = AppConfig()
    return _config


def set_config(config: AppConfig):
    """Set the global configuration."""
    global _config
    _config = config


def load_config_from_dict(data: dict) -> AppConfig:
    """Load configuration from a dictionary (e.g., from Google Sheet settings tab)."""
    config = AppConfig()

    # Group settings
    if "group" in data:
        g = data["group"]
        config.group.name = g.get("name", config.group.name)
        config.group.short_name = g.get("short_name", "")
        config.group.timezone = g.get("timezone", config.group.timezone)
        config.group.latitude = float(g.get("latitude", config.group.latitude))
        config.group.longitude = float(g.get("longitude", config.group.longitude))
        config.group.default_meeting_location = g.get("meeting_location", config.group.default_meeting_location)
        config.group.default_start_time = g.get("start_time", config.group.default_start_time)

    # Sheet settings
    if "sheet" in data:
        s = data["sheet"]
        config.sheet.spreadsheet_id = s.get("spreadsheet_id", "")
        config.sheet.schedule_tab_name = s.get("schedule_tab", config.sheet.schedule_tab_name)
        if "columns" in s:
            config.sheet.columns.update(s["columns"])

    # Calendar settings
    if "calendar" in data:
        c = data["calendar"]
        config.calendar.calendar_id = c.get("calendar_id")
        config.calendar.calendar_name = c.get("calendar_name", f"{config.group.name} Schedule")

    # Booking settings
    if "booking" in data:
        b = data["booking"]
        config.booking.booking_url = b.get("booking_url", "")
        config.booking.cancellation_url = b.get("cancellation_url", "")
        config.booking.ios_app_url = b.get("ios_app_url", "")
        config.booking.android_app_url = b.get("android_app_url", "")
        config.booking.web_schedule_url = b.get("web_schedule_url", "")

    # No-run dates
    if "no_run_dates" in data:
        nr = data["no_run_dates"]
        if "annual" in nr:
            config.no_run_dates.annual_holidays = [(d["month"], d["day"]) for d in nr["annual"]]
        if "specific" in nr:
            config.no_run_dates.specific_dates = nr["specific"]

    return config


def get_secret(name: str, default: str = None) -> Optional[str]:
    """
    Get a secret value (API key, token, etc.).

    Tries multiple sources:
    1. Environment variables
    2. Streamlit secrets (if available)
    """
    # Try environment first
    value = os.environ.get(name)
    if value:
        return value

    # Try Streamlit secrets (will fail gracefully if not in Streamlit)
    try:
        import streamlit as st
        return st.secrets.get(name, default)
    except Exception:
        pass

    return default
