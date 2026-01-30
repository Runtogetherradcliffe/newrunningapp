"""
Weather forecast functionality.

Uses Open-Meteo API (free, no API key required) to get weather forecasts
for the run location and time.

Designed to be UI-agnostic.
"""

from datetime import datetime, date
from typing import Optional, Tuple
import requests

from .config import get_config


def get_forecast_for_date(
    run_date: date,
    hour: int = 19,
    latitude: float = None,
    longitude: float = None,
    timezone: str = None,
) -> Optional[dict]:
    """
    Get weather forecast for a specific date and hour.

    Args:
        run_date: The date to get forecast for
        hour: Hour of day (24hr format, default 19:00)
        latitude: Override config latitude
        longitude: Override config longitude
        timezone: Override config timezone

    Returns:
        Dictionary with weather data or None if unavailable:
        {
            "temperature": float (Celsius),
            "precipitation_probability": int (0-100),
            "weather_code": int,
            "weather_description": str,
            "wind_speed": float (km/h),
        }
    """
    config = get_config()

    lat = latitude or config.group.latitude
    lon = longitude or config.group.longitude
    tz = timezone or config.group.timezone

    try:
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,precipitation_probability,weather_code,wind_speed_10m",
            "timezone": tz,
            "start_date": run_date.isoformat(),
            "end_date": run_date.isoformat(),
        }

        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params=params,
            timeout=8
        )

        if not response.ok:
            return None

        data = response.json()
        hourly = data.get("hourly", {})

        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        precip = hourly.get("precipitation_probability", [])
        codes = hourly.get("weather_code", [])
        wind = hourly.get("wind_speed_10m", [])

        if not times:
            return None

        # Find the closest hour to target
        target = datetime.combine(run_date, datetime.min.time()).replace(hour=hour)
        best_idx = 0
        best_diff = float('inf')

        for i, t_str in enumerate(times):
            try:
                t_dt = datetime.fromisoformat(t_str)
                diff = abs((t_dt - target).total_seconds())
                if diff < best_diff:
                    best_diff = diff
                    best_idx = i
            except Exception:
                continue

        return {
            "temperature": temps[best_idx] if best_idx < len(temps) else None,
            "precipitation_probability": precip[best_idx] if best_idx < len(precip) else None,
            "weather_code": codes[best_idx] if best_idx < len(codes) else None,
            "weather_description": _weather_code_to_description(codes[best_idx] if best_idx < len(codes) else None),
            "wind_speed": wind[best_idx] if best_idx < len(wind) else None,
        }

    except Exception:
        return None


def _weather_code_to_description(code: Optional[int]) -> str:
    """Convert WMO weather code to human description."""
    if code is None:
        return "unknown"

    descriptions = {
        0: "clear",
        1: "mainly clear",
        2: "partly cloudy",
        3: "overcast",
        45: "foggy",
        48: "foggy",
        51: "light drizzle",
        53: "drizzle",
        55: "heavy drizzle",
        61: "light rain",
        63: "rain",
        65: "heavy rain",
        71: "light snow",
        73: "snow",
        75: "heavy snow",
        80: "rain showers",
        81: "rain showers",
        82: "heavy showers",
        95: "thunderstorm",
    }
    return descriptions.get(code, "unknown")


def classify_weather(forecast: dict) -> str:
    """
    Classify weather into categories for message selection.

    Returns one of: "nice", "wet", "cold", "windy", "hot", "generic"
    """
    if not forecast:
        return "generic"

    temp = forecast.get("temperature")
    precip = forecast.get("precipitation_probability", 0)
    wind = forecast.get("wind_speed", 0)
    desc = (forecast.get("weather_description") or "").lower()
    config = get_config()

    # Check precipitation first
    if precip and precip > 50:
        return "wet"
    if any(w in desc for w in ["rain", "drizzle", "shower", "snow", "sleet"]):
        return "wet"

    # Temperature
    if temp is not None:
        if temp <= config.messages.cold_threshold:
            return "cold"
        if temp >= config.messages.hot_threshold:
            return "hot"

    # Wind
    if wind and wind > 30:  # km/h
        return "windy"

    # Nice conditions
    if any(w in desc for w in ["clear", "sunny", "mainly clear"]):
        return "nice"

    return "generic"


def get_weather_advice(run_date: date) -> Optional[str]:
    """
    Get weather-based clothing/preparation advice for a run date.

    Returns a short advisory string or None if no special advice needed.
    """
    forecast = get_forecast_for_date(run_date)
    if not forecast:
        return None

    config = get_config()
    temp = forecast.get("temperature")

    if temp is not None:
        if temp <= config.messages.cold_threshold:
            return config.messages.cold_weather_note
        if temp >= config.messages.hot_threshold:
            return config.messages.hot_weather_note

    return None


def get_weather_blurb_for_date(run_date) -> Optional[str]:
    """
    Legacy compatibility wrapper for get_weather_advice.

    Accepts various date formats (datetime, date, pandas Timestamp, string).
    """
    # Normalize to date object
    if hasattr(run_date, 'date'):
        d = run_date.date()
    elif isinstance(run_date, date):
        d = run_date
    else:
        try:
            d = datetime.strptime(str(run_date)[:10], "%Y-%m-%d").date()
        except Exception:
            return None

    return get_weather_advice(d)
