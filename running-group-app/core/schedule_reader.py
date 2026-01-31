"""
Schedule data reader.

Reads run schedule from Google Sheets. Handles column mapping
and data normalisation.

Designed to be UI-agnostic.
"""

from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional, List
import urllib.parse
import re

import pandas as pd
import requests

from .config import get_config, get_secret


@dataclass
class Route:
    """A single route option for a run."""
    name: str
    url: str = ""
    distance_km: Optional[float] = None
    elevation_m: Optional[float] = None
    terrain: str = ""  # road, trail, mixed
    area: str = ""
    strava_id: Optional[str] = None

    def __post_init__(self):
        # Extract Strava route ID from URL if present
        if self.url and not self.strava_id:
            match = re.search(r"/routes/(\d+)", self.url)
            if match:
                self.strava_id = match.group(1)


@dataclass
class ScheduledRun:
    """A single scheduled run with all its details."""
    date: date
    route_1: Optional[Route] = None
    route_2: Optional[Route] = None
    route_3: Optional[Route] = None  # Walk/C25K option
    meeting_point: str = ""
    meeting_point_url: str = ""
    start_time: str = "19:00"
    notes: str = ""
    special_event: str = ""
    is_on_tour: bool = False
    is_cancelled: bool = False

    @property
    def routes(self) -> List[Route]:
        """Return all defined routes as a list."""
        return [r for r in [self.route_1, self.route_2, self.route_3] if r]

    @property
    def has_routes(self) -> bool:
        """Check if any routes are defined."""
        return bool(self.routes)


def _clean_value(val) -> str:
    """Clean a cell value, handling NaN and None."""
    if val is None:
        return ""
    s = str(val).strip()
    if s.lower() in ("nan", "nat", "none"):
        return ""
    return s


def _try_float(val) -> Optional[float]:
    """Try to convert value to float."""
    try:
        if val is None or val == "":
            return None
        return float(val)
    except (TypeError, ValueError):
        return None


def _make_https(url: str) -> str:
    """Ensure URL uses HTTPS."""
    if not url:
        return ""
    url = url.strip()
    if url.startswith("http://"):
        url = "https://" + url[7:]
    return url


def build_csv_url(spreadsheet_id: str, sheet_name: str = "Schedule") -> str:
    """Build the Google Sheets CSV export URL."""
    encoded_name = urllib.parse.quote(sheet_name)
    return (
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
        f"/gviz/tq?tqx=out:csv&sheet={encoded_name}"
    )


def load_schedule_dataframe(
    spreadsheet_id: str = None,
    sheet_name: str = None,
) -> pd.DataFrame:
    """
    Load the schedule from Google Sheets as a pandas DataFrame.

    Args:
        spreadsheet_id: Google Sheet ID (uses config if not provided)
        sheet_name: Tab name (uses config if not provided)

    Returns:
        DataFrame with schedule data

    Raises:
        ValueError if sheet cannot be loaded
    """
    config = get_config()
    sid = spreadsheet_id or config.sheet.spreadsheet_id
    tab = sheet_name or config.sheet.schedule_tab_name

    if not sid:
        raise ValueError("No spreadsheet_id configured")

    url = build_csv_url(sid, tab)

    try:
        df = pd.read_csv(url)
        return df
    except Exception as e:
        raise ValueError(
            f"Failed to load Google Sheet. Make sure it's shared as "
            f"'Anyone with the link can view'.\n\nError: {e}"
        )


def parse_schedule(df: pd.DataFrame) -> List[ScheduledRun]:
    """
    Parse a schedule DataFrame into a list of ScheduledRun objects.

    Uses column mappings from config.
    """
    config = get_config()
    cols = config.sheet.columns
    runs = []

    # Find date column
    date_col = cols.get("date", "Date (Thu)")
    if date_col not in df.columns:
        # Try to find a column containing "date"
        for col in df.columns:
            if "date" in col.lower():
                date_col = col
                break

    if date_col not in df.columns:
        raise ValueError(f"Date column '{date_col}' not found in sheet")

    # Parse dates
    df["_parsed_date"] = pd.to_datetime(df[date_col], errors="coerce")

    for _, row in df.iterrows():
        parsed_date = row.get("_parsed_date")
        if pd.isna(parsed_date):
            continue

        run_date = parsed_date.date()

        # Check if cancelled
        notes = _clean_value(row.get(cols.get("notes", "Notes"), ""))
        is_cancelled = bool(re.search(r"no\s*run|cancel|skip|off", notes, re.IGNORECASE))

        # Check if no-run date
        if config.no_run_dates.is_no_run(run_date):
            is_cancelled = True

        # Build routes
        route_1 = None
        route_2 = None
        route_3 = None

        # Helper to find column value with fallbacks
        def get_col(key: str, fallbacks: list = None) -> str:
            """Try to get column value, with fallback column names."""
            # First try the configured column name
            col_name = cols.get(key, "")
            if col_name and col_name in df.columns:
                return _clean_value(row.get(col_name, ""))

            # Try fallbacks
            if fallbacks:
                for fb in fallbacks:
                    if fb in df.columns:
                        return _clean_value(row.get(fb, ""))

            return ""

        # Route 1
        r1_name = get_col("route_1_name", ["Route 1 - Name", "Route 1 Name", "Route1"])
        if r1_name:
            route_1 = Route(
                name=r1_name,
                url=_make_https(get_col("route_1_url", ["Route 1 URL", "Route 1 - URL", "Route1 URL"])),
                distance_km=_try_float(get_col("route_1_distance", ["Route 1 Distance", "Route 1 - Distance"])),
            )

        # Route 2
        r2_name = get_col("route_2_name", ["Route 2 - Name", "Route 2 Name", "Route2"])
        if r2_name:
            route_2 = Route(
                name=r2_name,
                url=_make_https(get_col("route_2_url", ["Route 2 URL", "Route 2 - URL", "Route2 URL"])),
                distance_km=_try_float(get_col("route_2_distance", ["Route 2 Distance", "Route 2 - Distance"])),
            )

        # Route 3 (optional walk/C25K)
        r3_name = get_col("route_3_name", ["Route 3 name", "Route 3 - Name", "Route 3 Name"])
        r3_desc = get_col("route_3_description", ["Route 3 description", "Route 3 - Description"])
        if r3_name or r3_desc:
            route_3 = Route(
                name=r3_name or r3_desc,
                url=_make_https(get_col("route_3_url", ["Route 3 URL", "Route 3 - URL"])),
            )

        # Meeting point
        meeting_point = _clean_value(row.get(cols.get("meeting_point", "Meeting Point"), ""))
        if not meeting_point:
            # Try to parse from notes
            match = re.search(r"Meeting:\s*([^|\n]+)", notes, re.IGNORECASE)
            if match:
                meeting_point = match.group(1).strip()

        if not meeting_point:
            meeting_point = config.group.default_meeting_location

        # Check if "on tour" (not at usual location)
        # Normalize both strings for comparison (lowercase, strip whitespace)
        default_location = config.group.default_meeting_location.lower().strip()
        current_location = meeting_point.lower().strip()

        # Only consider "on tour" if:
        # 1. There's a default location set (not empty)
        # 2. The current location is different from the default
        # 3. The notes don't contain "tour" (explicit override)
        is_on_tour = (
            bool(default_location) and
            bool(current_location) and
            current_location != default_location and
            "tour" not in notes.lower()  # Don't double-flag if already noted
        )

        scheduled_run = ScheduledRun(
            date=run_date,
            route_1=route_1,
            route_2=route_2,
            route_3=route_3,
            meeting_point=meeting_point,
            start_time=config.group.default_start_time,
            notes=notes,
            is_on_tour=is_on_tour,
            is_cancelled=is_cancelled,
        )

        runs.append(scheduled_run)

    return runs


def load_schedule() -> List[ScheduledRun]:
    """
    Load and parse the complete schedule.

    Convenience function that combines load_schedule_dataframe and parse_schedule.
    """
    df = load_schedule_dataframe()
    return parse_schedule(df)


def get_upcoming_runs(
    runs: List[ScheduledRun] = None,
    include_cancelled: bool = False,
    run_day_only: bool = True,
) -> List[ScheduledRun]:
    """
    Filter to only upcoming runs.

    Args:
        runs: List of runs (loads from sheet if not provided)
        include_cancelled: Include cancelled runs
        run_day_only: Only return runs on the configured run days (e.g., Thursdays and Sundays)
    """
    if runs is None:
        runs = load_schedule()

    config = get_config()
    today = date.today()

    upcoming = [r for r in runs if r.date >= today]

    if not include_cancelled:
        upcoming = [r for r in upcoming if not r.is_cancelled]

    if run_day_only:
        # Filter to only configured run days (supports multiple days)
        run_days = config.group.run_days
        upcoming = [r for r in upcoming if r.date.weekday() in run_days]

    return sorted(upcoming, key=lambda r: r.date)


def get_next_run(runs: List[ScheduledRun] = None) -> Optional[ScheduledRun]:
    """Get the next upcoming run."""
    upcoming = get_upcoming_runs(runs)
    return upcoming[0] if upcoming else None
