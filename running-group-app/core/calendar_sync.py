"""
Google Calendar synchronisation.

Creates and updates calendar events based on the run schedule.
Replaces the functionality of the Google Apps Script.

Designed to be UI-agnostic.
"""

from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict
import re

from .config import get_config
from .schedule_reader import ScheduledRun, Route


@dataclass
class CalendarEvent:
    """Represents a Google Calendar event."""
    id: Optional[str] = None
    title: str = ""
    description: str = ""
    location: str = ""
    start_time: datetime = None
    end_time: datetime = None
    timezone: str = "Europe/London"


@dataclass
class SyncResult:
    """Result of a calendar sync operation."""
    created: int = 0
    updated: int = 0
    deleted: int = 0
    skipped: int = 0
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


def build_event_description(run: ScheduledRun) -> str:
    """
    Build the calendar event description from a scheduled run.

    Includes route names, Strava links, and meeting point.
    """
    config = get_config()
    lines = [config.calendar.description_marker]

    if run.route_1:
        lines.append(f"8K Route: {run.route_1.name}")
        if run.route_1.url:
            lines.append(f"8K Link: {run.route_1.url}")

    if run.route_2:
        lines.append(f"5K Route: {run.route_2.name}")
        if run.route_2.url:
            lines.append(f"5K Link: {run.route_2.url}")

    if run.route_3:
        label = run.route_3.name or "Walk"
        dist_part = f" ({run.route_3.distance_km} km)" if run.route_3.distance_km else ""
        lines.append(f"Social Walk Route: {label}{dist_part}")
        if run.route_3.url:
            lines.append(f"Social Walk Link: {run.route_3.url}")

    lines.append(f"Meeting: {run.meeting_point}")

    if run.notes:
        lines.append(run.notes)

    return "\n".join(lines)


def build_calendar_event(run: ScheduledRun) -> CalendarEvent:
    """
    Build a CalendarEvent object from a ScheduledRun.
    """
    config = get_config()

    # Parse start time
    try:
        hour, minute = map(int, run.start_time.split(":"))
    except Exception:
        hour, minute = 19, 0

    start_dt = datetime.combine(run.date, datetime.min.time().replace(hour=hour, minute=minute))
    end_dt = start_dt + timedelta(minutes=config.calendar.event_duration_minutes)

    # Use calendar name or group name for title
    title = config.calendar.calendar_name or f"{config.group.name}"

    return CalendarEvent(
        title=title,
        description=build_event_description(run),
        location=run.meeting_point,
        start_time=start_dt,
        end_time=end_dt,
        timezone=config.group.timezone,
    )


def is_managed_event(event: dict, description_marker: str = None) -> bool:
    """
    Check if a calendar event was created/managed by this app.

    Looks for the description marker in the event description.
    """
    if description_marker is None:
        config = get_config()
        description_marker = config.calendar.description_marker

    desc = event.get("description", "")
    return description_marker in desc


# ============================================================================
# Google Calendar API Integration
# ============================================================================
# These functions require google-api-python-client and valid OAuth credentials

def get_calendar_service(credentials):
    """
    Build the Google Calendar API service.

    Args:
        credentials: google.oauth2.credentials.Credentials object

    Returns:
        googleapiclient.discovery.Resource for Calendar API
    """
    try:
        from googleapiclient.discovery import build
        return build("calendar", "v3", credentials=credentials)
    except ImportError:
        raise ImportError(
            "Google API client not installed. "
            "Run: pip install google-api-python-client google-auth-oauthlib"
        )


def create_calendar(service, name: str, timezone: str = "Europe/London") -> str:
    """
    Create a new Google Calendar.

    Args:
        service: Google Calendar API service
        name: Calendar name (e.g., "Townsville Runners Schedule")
        timezone: Calendar timezone

    Returns:
        Calendar ID of the created calendar
    """
    calendar_body = {
        "summary": name,
        "timeZone": timezone,
    }

    created = service.calendars().insert(body=calendar_body).execute()
    calendar_id = created["id"]

    # Make it public (so runners can subscribe)
    rule = {
        "scope": {"type": "default"},
        "role": "reader",
    }
    service.acl().insert(calendarId=calendar_id, body=rule).execute()

    return calendar_id


def get_subscribe_url(calendar_id: str) -> str:
    """
    Get the public iCal subscribe URL for a calendar.

    This URL can be used by runners to add the calendar to their own
    calendar apps (Google Calendar, Apple Calendar, Outlook, etc.)
    """
    # URL-encode the calendar ID
    import urllib.parse
    encoded_id = urllib.parse.quote(calendar_id)

    return f"https://calendar.google.com/calendar/ical/{encoded_id}/public/basic.ics"


def get_web_view_url(calendar_id: str) -> str:
    """Get the public web view URL for a calendar."""
    import urllib.parse
    encoded_id = urllib.parse.quote(calendar_id)

    return f"https://calendar.google.com/calendar/embed?src={encoded_id}"


def list_events(
    service,
    calendar_id: str,
    start_date: date,
    end_date: date,
) -> List[dict]:
    """
    List calendar events in a date range.

    Args:
        service: Google Calendar API service
        calendar_id: Calendar ID
        start_date: Start of range
        end_date: End of range

    Returns:
        List of event dictionaries
    """
    config = get_config()

    time_min = datetime.combine(start_date, datetime.min.time()).isoformat() + "Z"
    time_max = datetime.combine(end_date, datetime.max.time()).isoformat() + "Z"

    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    return events_result.get("items", [])


def create_event(service, calendar_id: str, event: CalendarEvent) -> str:
    """
    Create a new calendar event.

    Returns:
        Event ID of the created event
    """
    body = {
        "summary": event.title,
        "description": event.description,
        "location": event.location,
        "start": {
            "dateTime": event.start_time.isoformat(),
            "timeZone": event.timezone,
        },
        "end": {
            "dateTime": event.end_time.isoformat(),
            "timeZone": event.timezone,
        },
    }

    created = service.events().insert(calendarId=calendar_id, body=body).execute()
    return created.get("id")


def update_event(service, calendar_id: str, event_id: str, event: CalendarEvent):
    """Update an existing calendar event."""
    body = {
        "summary": event.title,
        "description": event.description,
        "location": event.location,
        "start": {
            "dateTime": event.start_time.isoformat(),
            "timeZone": event.timezone,
        },
        "end": {
            "dateTime": event.end_time.isoformat(),
            "timeZone": event.timezone,
        },
    }

    service.events().update(
        calendarId=calendar_id,
        eventId=event_id,
        body=body,
    ).execute()


def delete_event(service, calendar_id: str, event_id: str):
    """Delete a calendar event."""
    service.events().delete(calendarId=calendar_id, eventId=event_id).execute()


# ============================================================================
# Sync Logic
# ============================================================================

def sync_schedule_to_calendar(
    service,
    calendar_id: str,
    runs: List[ScheduledRun],
    dry_run: bool = False,
) -> SyncResult:
    """
    Synchronise a list of scheduled runs to the Google Calendar.

    - Creates events for new runs
    - Updates events for changed runs
    - Deletes events for cancelled runs or no-run dates
    - Removes orphan events not in the schedule

    Args:
        service: Google Calendar API service
        calendar_id: Target calendar ID
        runs: List of scheduled runs
        dry_run: If True, don't make any changes (just report what would happen)

    Returns:
        SyncResult with counts of operations performed
    """
    config = get_config()
    result = SyncResult()

    if not runs:
        return result

    # Determine date range
    dates = [r.date for r in runs]
    start_date = min(dates) - timedelta(days=1)
    end_date = max(dates) + timedelta(days=1)

    # Get existing events
    try:
        existing_events = list_events(service, calendar_id, start_date, end_date)
    except Exception as e:
        result.errors.append(f"Failed to list events: {e}")
        return result

    # Filter to only managed events
    managed_events = [e for e in existing_events if is_managed_event(e)]

    # Index existing events by date
    events_by_date: Dict[date, dict] = {}
    for event in managed_events:
        try:
            start_str = event.get("start", {}).get("dateTime", "")
            event_date = datetime.fromisoformat(start_str.replace("Z", "+00:00")).date()
            events_by_date[event_date] = event
        except Exception:
            continue

    # Process each run
    for run in runs:
        existing_event = events_by_date.get(run.date)

        # Handle cancelled/no-run dates
        if run.is_cancelled or config.no_run_dates.is_no_run(run.date):
            if existing_event:
                if not dry_run:
                    try:
                        delete_event(service, calendar_id, existing_event["id"])
                        result.deleted += 1
                    except Exception as e:
                        result.errors.append(f"Failed to delete event for {run.date}: {e}")
                else:
                    result.deleted += 1
            else:
                result.skipped += 1
            continue

        # Build the event we want
        desired_event = build_calendar_event(run)

        if existing_event:
            # Update existing event
            if not dry_run:
                try:
                    update_event(service, calendar_id, existing_event["id"], desired_event)
                    result.updated += 1
                except Exception as e:
                    result.errors.append(f"Failed to update event for {run.date}: {e}")
            else:
                result.updated += 1

            # Remove from tracking dict so we know it's handled
            del events_by_date[run.date]
        else:
            # Create new event
            if not dry_run:
                try:
                    create_event(service, calendar_id, desired_event)
                    result.created += 1
                except Exception as e:
                    result.errors.append(f"Failed to create event for {run.date}: {e}")
            else:
                result.created += 1

    # Delete orphan events (managed events not in the schedule)
    for orphan_date, orphan_event in events_by_date.items():
        if not dry_run:
            try:
                delete_event(service, calendar_id, orphan_event["id"])
                result.deleted += 1
            except Exception as e:
                result.errors.append(f"Failed to delete orphan event for {orphan_date}: {e}")
        else:
            result.deleted += 1

    return result
