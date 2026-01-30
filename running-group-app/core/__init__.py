"""
Core business logic for Running Group App.

This module contains all the business logic, independent of any UI framework.
It can be used by:
- Streamlit web app (current)
- FastAPI backend (future mobile app)
- CLI tools
- Automated scripts

Main modules:
- config: Configuration management
- schedule_reader: Load run schedule from Google Sheets
- message_generator: Generate weekly messages for email/FB/WhatsApp
- calendar_sync: Sync schedule to Google Calendar
- weather: Weather forecasts and advice
"""

from .config import (
    AppConfig,
    GroupConfig,
    SheetConfig,
    CalendarConfig,
    BookingConfig,
    MessageConfig,
    NoRunDates,
    get_config,
    set_config,
    load_config_from_dict,
    get_secret,
)

from .schedule_reader import (
    Route,
    ScheduledRun,
    load_schedule,
    load_schedule_dataframe,
    parse_schedule,
    get_upcoming_runs,
    get_next_run,
)

from .message_generator import (
    GeneratedMessage,
    MessageSet,
    generate_messages,
    format_date_uk,
)

from .calendar_sync import (
    CalendarEvent,
    SyncResult,
    build_calendar_event,
    build_event_description,
    get_calendar_service,
    create_calendar,
    get_subscribe_url,
    get_web_view_url,
    sync_schedule_to_calendar,
)

from .weather import (
    get_forecast_for_date,
    get_weather_advice,
    classify_weather,
)

__all__ = [
    # Config
    "AppConfig",
    "GroupConfig",
    "SheetConfig",
    "CalendarConfig",
    "BookingConfig",
    "MessageConfig",
    "NoRunDates",
    "get_config",
    "set_config",
    "load_config_from_dict",
    "get_secret",
    # Schedule
    "Route",
    "ScheduledRun",
    "load_schedule",
    "load_schedule_dataframe",
    "parse_schedule",
    "get_upcoming_runs",
    "get_next_run",
    # Messages
    "GeneratedMessage",
    "MessageSet",
    "generate_messages",
    "format_date_uk",
    # Calendar
    "CalendarEvent",
    "SyncResult",
    "build_calendar_event",
    "build_event_description",
    "get_calendar_service",
    "create_calendar",
    "get_subscribe_url",
    "get_web_view_url",
    "sync_schedule_to_calendar",
    # Weather
    "get_forecast_for_date",
    "get_weather_advice",
    "classify_weather",
]
