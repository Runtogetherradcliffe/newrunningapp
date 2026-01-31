"""
Message generation for weekly run announcements.

Generates messages for email, Facebook, and WhatsApp with:
- Weather-aware intro variants
- Varied greetings and closings (rotated weekly)
- Safety notes for dark/cold conditions
- Route information with distance and terrain descriptions

Designed to be UI-agnostic.
"""

from dataclasses import dataclass
from datetime import date
from typing import List, Optional
import hashlib
import random

from .config import get_config
from .schedule_reader import ScheduledRun, Route
from .weather import get_forecast_for_date, classify_weather, get_weather_advice


# ============================================================================
# Message Content Pools
# ============================================================================

INTRO_VARIANTS = [
    "We've got {num_routes} routes lined up and {num_options} great options this week:",
    "This {day_name} we've got {num_routes} routes planned and {num_options} great options to choose from:",
    "{num_routes} routes, {num_options} great options – something for everyone this {day_name}:",
    "Fancy joining us this week? We've planned {num_routes} routes and {num_options} options for you this {day_name}:",
    "Come and join us on {day_name} for a chatty run, we've got {num_routes} routes and {num_options} options to pick from:",
    "Your {day_name} is sorted – {num_routes} routes and {num_options} options waiting for you:",
    "We've planned another great {day_name} meetup with {num_routes} routes and {num_options} options to suit how you're feeling:",
    "From gentle chats to stretch-your-legs runs, we've got {num_routes} routes and {num_options} options this week:",
    "Looking for some miles and smiles? We've lined up {num_routes} routes and {num_options} options:",
    "Once again we've got {num_routes} routes and {num_options} options ready – just book on and join the fun:",
]

NICE_WEATHER_INTROS = [
    "Looks like a decent day for it – we've planned {num_routes} routes and {num_options} options for you this {day_name}:",
    "With the weather playing nicely, it's a great week to join us for {num_routes} routes and {num_options} options:",
    "Perfect excuse to get outside – {num_routes} routes and {num_options} friendly options waiting for you this {day_name}:",
]

WET_WEATHER_INTROS = [
    "It might be a bit soggy out there, but we'll be braving the elements with {num_routes} routes and {num_options} options – come splash through the puddles with us:",
    "Rain on the forecast? All the more reason to join us – {num_routes} routes and {num_options} options to keep things fun whatever the weather:",
    "Grab your waterproofs – we've still got {num_routes} routes and {num_options} options lined up for a proper {day_name} outing:",
]

COLD_WEATHER_INTROS = [
    "Chilly day ahead, but we'll soon warm up with {num_routes} routes and {num_options} options to choose from:",
    "Layer up and join us this {day_name} – {num_routes} routes and {num_options} cosy, chatty options to keep you moving:",
    "Gloves and hats at the ready! We've planned {num_routes} routes and {num_options} options for a crisp {day_name}:",
]

WINDY_WEATHER_INTROS = [
    "It could be a bit breezy, but we'll lean into it together – {num_routes} routes and {num_options} options this {day_name}:",
    "Wind in the hair, smiles all round – we've got {num_routes} routes and {num_options} options lined up:",
]

HOT_WEATHER_INTROS = [
    "It's looking warm out there – {num_routes} routes and {num_options} options, just remember your water:",
    "A warm day ahead! We've got {num_routes} routes and {num_options} options – stay hydrated:",
]

CLOSING_VARIANTS_EMAIL = [
    "Grab your spot and come run/walk with us! 🧡",
    "Fancy joining us this week? Book your spot and come along! 🧡",
    "We'd love to see you there – grab a place and join the fun! 🧡",
]

CLOSING_VARIANTS_FACEBOOK = [
    "Tag a friend who might like to join us and share the running love! 🧡",
    "Know someone who'd enjoy this? Tag them and bring them along! 🧡",
    "New faces always welcome – tag a friend and spread the word! 🧡",
]

CLOSING_VARIANTS_WHATSAPP = [
    "*We set off at 7:00pm – please book on and arrive a few minutes early.*",
    "*We set off at 7:00pm – book your spot and come a little early to say hi.*",
    "*We set off at 7:00pm – grab a place and aim to arrive a few minutes before.*",
]

TERRAIN_PHRASES = {
    "flat": ["flat and friendly 🏁", "fast & flat 🏁", "pan-flat cruise 💨"],
    "rolling": ["gently rolling 🌱", "undulating and friendly 🌿", "rolling countryside vibes 🌳"],
    "hilly": ["a hilly tester! ⛰️", "spicy climbs ahead 🌶️", "some punchy hills 🚵"],
}

FALLBACK_TERRAIN = ["a great midweek spin", "perfect for all paces", "midweek miles made easy"]


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class GeneratedMessage:
    """A generated message for a specific platform."""
    platform: str  # "email", "facebook", "whatsapp"
    subject: str  # For email
    body: str
    html_body: Optional[str] = None  # HTML version for email


@dataclass
class MessageSet:
    """Complete set of messages for all platforms."""
    run_date: date
    email: GeneratedMessage
    facebook: GeneratedMessage
    whatsapp: GeneratedMessage


# ============================================================================
# Helper Functions
# ============================================================================

def _ordinal(n: int) -> str:
    """Convert number to ordinal (1st, 2nd, 3rd, etc.)."""
    n = int(n)
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def format_date_uk(d: date) -> str:
    """Format date as '5th January' style."""
    return f"{_ordinal(d.day)} {d.strftime('%B')}"


def format_time_12h(time_str: str) -> str:
    """
    Format time string to 12-hour format.

    Examples:
        "19:00" -> "7pm"
        "19:30" -> "7:30pm"
        "09:00" -> "9am"
    """
    if not time_str:
        return "7pm"  # Default

    try:
        # Handle HH:MM format
        parts = time_str.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0

        # Convert to 12-hour
        period = "am" if hour < 12 else "pm"
        hour_12 = hour % 12
        if hour_12 == 0:
            hour_12 = 12

        if minute == 0:
            return f"{hour_12}{period}"
        else:
            return f"{hour_12}:{minute:02d}{period}"
    except (ValueError, IndexError):
        return time_str  # Return as-is if parsing fails


def _get_seeded_rng(run_date: date, offset: int = 0) -> random.Random:
    """Get a random generator seeded by date for consistent weekly variation."""
    seed_str = str(run_date)
    seed = int(hashlib.sha1(seed_str.encode()).hexdigest()[:8], 16) + offset
    return random.Random(seed)


def _get_hilliness_blurb(distance_km: Optional[float], elevation_m: Optional[float], rng: random.Random) -> str:
    """Generate terrain description based on elevation gain per km."""
    if not distance_km or not elevation_m:
        return rng.choice(FALLBACK_TERRAIN)

    try:
        m_per_km = float(elevation_m) / max(float(distance_km), 0.1)
    except Exception:
        return rng.choice(FALLBACK_TERRAIN)

    if m_per_km < 10:
        key = "flat"
    elif m_per_km < 20:
        key = "rolling"
    else:
        key = "hilly"

    return rng.choice(TERRAIN_PHRASES[key])


def _get_day_name(d: date) -> str:
    """Get the day name for a date (e.g., 'Thursday', 'Sunday')."""
    return d.strftime("%A")


def _select_intro(
    rng: random.Random,
    weather_category: str,
    num_routes: int,
    num_options: int,
    day_name: str,
) -> str:
    """Select an intro based on weather and variety."""
    pool_map = {
        "nice": NICE_WEATHER_INTROS + INTRO_VARIANTS,
        "wet": WET_WEATHER_INTROS + INTRO_VARIANTS,
        "cold": COLD_WEATHER_INTROS + INTRO_VARIANTS,
        "windy": WINDY_WEATHER_INTROS + INTRO_VARIANTS,
        "hot": HOT_WEATHER_INTROS + INTRO_VARIANTS,
    }

    pool = pool_map.get(weather_category, INTRO_VARIANTS)
    template = rng.choice(pool)

    return template.format(num_routes=num_routes, num_options=num_options, day_name=day_name)


def _build_route_line(label: str, route: Route, include_url: bool = True) -> str:
    """Build a formatted line describing a route."""
    parts = [f"• {label} – {route.name}"]

    if include_url and route.url:
        parts[0] += f": {route.url}"

    details = []
    if route.distance_km:
        details.append(f"{route.distance_km:.1f} km")
    if route.elevation_m:
        details.append(f"{route.elevation_m:.0f}m elevation")

    if details:
        parts.append(f"  {' with '.join(details)}")

    return "\n".join(parts)


# ============================================================================
# Main Message Generation
# ============================================================================

def generate_messages(
    run: ScheduledRun,
    include_jeffing: bool = True,
    custom_intros: dict = None,
    custom_closings: dict = None,
) -> MessageSet:
    """
    Generate complete message set for all platforms.

    Args:
        run: The scheduled run to generate messages for
        include_jeffing: Whether to include Jeffing as an option
        custom_intros: Override intro pools (dict of weather_category -> list)
        custom_closings: Override closing pools (dict of platform -> list)

    Returns:
        MessageSet with email, facebook, and whatsapp messages
    """
    config = get_config()

    # Get weather-based context
    forecast = get_forecast_for_date(run.date)
    weather_category = classify_weather(forecast)
    weather_advice = get_weather_advice(run.date)

    # Count routes and options
    num_routes = len(run.routes)
    # Options are: Walk (if route_3) + Jeffing (if enabled) + 5k + 8k
    # Always show 5k and 8k as base options
    num_options = 2  # 5k + 8k always listed
    if run.route_3:
        num_options += 1  # Walk option
    if include_jeffing:
        num_options += 1  # Jeffing option

    # Get seeded RNGs for each platform (consistent per date, varied per platform)
    rng_email = _get_seeded_rng(run.date, 0)
    rng_fb = _get_seeded_rng(run.date, 1)
    rng_wa = _get_seeded_rng(run.date, 2)

    # Generate each platform's message
    email = _generate_email(run, rng_email, weather_category, weather_advice, num_routes, num_options, include_jeffing)
    facebook = _generate_facebook(run, rng_fb, weather_category, weather_advice, num_routes, num_options, include_jeffing)
    whatsapp = _generate_whatsapp(run, rng_wa, weather_category, weather_advice, num_routes, num_options, include_jeffing)

    return MessageSet(
        run_date=run.date,
        email=email,
        facebook=facebook,
        whatsapp=whatsapp,
    )


def _get_route_label(route: Route) -> str:
    """Get a display label for a route (distance or name)."""
    if route.distance_km:
        # Format as "8k" or "5.5k"
        dist = route.distance_km
        if dist == int(dist):
            return f"{int(dist)}k"
        else:
            return f"{dist:.1f}k"
    return route.name or "Route"


def _generate_email(
    run: ScheduledRun,
    rng: random.Random,
    weather_category: str,
    weather_advice: Optional[str],
    num_routes: int,
    num_options: int,
    include_jeffing: bool,
) -> GeneratedMessage:
    """Generate email message."""
    config = get_config()
    date_str = format_date_uk(run.date)
    day_name = _get_day_name(run.date)
    lines = []

    # Intro
    lines.append(_select_intro(rng, weather_category, num_routes, num_options, day_name))

    # Options list - use actual route names/distances
    if run.route_3:
        label = run.route_3.name or "Walk"
        emoji = "🚶" if "walk" in label.lower() else "🏃"
        lines.append(f"{emoji} {label}")
    if include_jeffing:
        lines.append("🏃 Jeffing")
    if run.route_2:
        label_2 = _get_route_label(run.route_2)
        lines.append(f"🏃 {label_2}")
    if run.route_1:
        label_1 = _get_route_label(run.route_1)
        lines.append(f"🏃‍♀️ {label_1}")

    lines.append("")

    # Meeting details
    if run.is_on_tour:
        lines.append(f"📍 This week we're On Tour – meeting at {run.meeting_point} at {format_time_12h(run.start_time)}")
    else:
        lines.append(f"📍 Meeting at: {run.meeting_point} at {format_time_12h(run.start_time)}")

    lines.append("")

    # Route details
    lines.append("This week's routes")
    lines.append("")
    if run.route_1:
        label_1 = _get_route_label(run.route_1)
        lines.append(_build_route_line(label_1, run.route_1))
    if run.route_2:
        label_2 = _get_route_label(run.route_2)
        lines.append(_build_route_line(label_2, run.route_2))
    if run.route_3:
        lines.append(_build_route_line(run.route_3.name or "Walk", run.route_3))

    lines.append("")

    # Booking info (only show if there's something to show)
    if config.booking.booking_url or config.booking.cancellation_url:
        lines.append("How to book")
        lines.append("")
        if config.booking.booking_url:
            lines.append(f"📲 Book your place: {config.booking.booking_url}")
        if config.booking.cancellation_url:
            lines.append(f"To cancel: {config.booking.cancellation_url}")
        lines.append("")

    # Safety and weather
    lines.append("Additional information")
    lines.append("")

    safety_note = config.messages.dark_running_note
    if safety_note and weather_advice:
        # Combine them
        wa_lower = weather_advice[0].lower() + weather_advice[1:] if weather_advice else ""
        lines.append(f"{safety_note} Also {wa_lower}")
    elif safety_note:
        lines.append(safety_note)
    elif weather_advice:
        lines.append(weather_advice)

    lines.append("")

    # Closing
    lines.append(rng.choice(CLOSING_VARIANTS_EMAIL))

    body = "\n".join(lines)

    return GeneratedMessage(
        platform="email",
        subject=f"{config.group.name} – this {day_name} {date_str}",
        body=body,
        html_body=_convert_to_html(body),
    )


def _generate_facebook(
    run: ScheduledRun,
    rng: random.Random,
    weather_category: str,
    weather_advice: Optional[str],
    num_routes: int,
    num_options: int,
    include_jeffing: bool,
) -> GeneratedMessage:
    """Generate Facebook post."""
    config = get_config()
    date_str = format_date_uk(run.date)
    day_name = _get_day_name(run.date)
    lines = []

    # Header
    lines.append(f"{config.group.name} – this {day_name} {date_str}")
    lines.append("")

    # Intro
    lines.append(_select_intro(rng, weather_category, num_routes, num_options, day_name))

    # Options list - use actual route names/distances
    if run.route_3:
        label = run.route_3.name or "Walk"
        emoji = "🚶" if "walk" in label.lower() else "🏃"
        lines.append(f"{emoji} {label}")
    if include_jeffing:
        lines.append("🏃 Jeffing")
    if run.route_2:
        label_2 = _get_route_label(run.route_2)
        lines.append(f"🏃 {label_2}")
    if run.route_1:
        label_1 = _get_route_label(run.route_1)
        lines.append(f"🏃‍♀️ {label_1}")

    lines.append("")

    # Meeting details
    if run.is_on_tour:
        lines.append(f"📍 This week we're On Tour – meeting at {run.meeting_point} at {format_time_12h(run.start_time)}")
    else:
        lines.append(f"📍 Meeting at: {run.meeting_point} at {format_time_12h(run.start_time)}")

    lines.append("")

    # Booking info
    if config.booking.booking_url:
        lines.append(f"📲 Book your place: {config.booking.booking_url}")

    lines.append("")

    # Route details
    if run.route_1:
        label_1 = _get_route_label(run.route_1)
        lines.append(_build_route_line(label_1, run.route_1))
    if run.route_2:
        label_2 = _get_route_label(run.route_2)
        lines.append(_build_route_line(label_2, run.route_2))

    lines.append("")

    # Safety and weather
    if config.messages.dark_running_note:
        lines.append(config.messages.dark_running_note)
    if weather_advice:
        lines.append(weather_advice)

    lines.append("")

    # Closing
    lines.append(rng.choice(CLOSING_VARIANTS_FACEBOOK))

    body = "\n".join(lines)

    return GeneratedMessage(
        platform="facebook",
        subject="",
        body=body,
    )


def _generate_whatsapp(
    run: ScheduledRun,
    rng: random.Random,
    weather_category: str,
    weather_advice: Optional[str],
    num_routes: int,
    num_options: int,
    include_jeffing: bool,
) -> GeneratedMessage:
    """Generate WhatsApp message."""
    config = get_config()
    date_str = format_date_uk(run.date)
    day_name = _get_day_name(run.date)
    lines = []

    # Header (bold in WhatsApp)
    lines.append(f"*{config.group.name} – {day_name} {date_str}*")
    lines.append("")

    # Intro
    lines.append(_select_intro(rng, weather_category, num_routes, num_options, day_name))

    # Options list - use actual route names/distances
    if run.route_3:
        label = run.route_3.name or "Walk"
        emoji = "🚶" if "walk" in label.lower() else "🏃"
        lines.append(f"- {emoji} {label}")
    if include_jeffing:
        lines.append("- 🏃 Jeffing")
    if run.route_2:
        label_2 = _get_route_label(run.route_2)
        lines.append(f"- 🏃 {label_2}")
    if run.route_1:
        label_1 = _get_route_label(run.route_1)
        lines.append(f"- 🏃‍♀️ {label_1}")

    lines.append("")

    # Meeting details
    if run.is_on_tour:
        lines.append(f"📍 This week we're On Tour – meeting at {run.meeting_point} at {format_time_12h(run.start_time)}")
    else:
        lines.append(f"📍 Meeting at: {run.meeting_point} at {format_time_12h(run.start_time)}")

    lines.append("")

    # Route links
    if config.booking.web_schedule_url:
        lines.append("Route links for this week (and future runs):")
        lines.append(config.booking.web_schedule_url)
        lines.append("")

    # Safety and weather
    if config.messages.dark_running_note:
        lines.append(config.messages.dark_running_note)
    if weather_advice:
        lines.append(weather_advice)

    lines.append("")

    # Closing
    lines.append(rng.choice(CLOSING_VARIANTS_WHATSAPP))

    body = "\n".join(lines)

    return GeneratedMessage(
        platform="whatsapp",
        subject="",
        body=body,
    )


def _convert_to_html(text: str) -> str:
    """Convert plain text to simple HTML."""
    import html

    lines = text.split("\n")
    html_lines = []

    for line in lines:
        stripped = line.strip()

        # Bold section headings
        if stripped in ("This week's routes", "How to book", "Additional information"):
            html_lines.append(f"<b>{html.escape(stripped)}</b>")
        else:
            html_lines.append(html.escape(line))

    return "<br>".join(html_lines)
