"""
Running Group App - Main Entry Point

A Streamlit app for running groups to:
- Generate weekly messages (email, Facebook, WhatsApp)
- Sync schedule to Google Calendar
- Manage group settings

Run with: streamlit run web/app.py
"""

import streamlit as st
import sys
from pathlib import Path

# Add directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))  # For core imports
sys.path.insert(0, str(Path(__file__).parent))  # For web imports (google_auth, strava_auth)

from core import get_config, set_config, load_config_from_dict

# Page config must be first Streamlit command
st.set_page_config(
    page_title="Running Group App",
    page_icon="🏃",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
# Session State Initialization
# ============================================================================

def init_session_state():
    """Initialize session state variables."""
    if "setup_complete" not in st.session_state:
        st.session_state.setup_complete = False

    if "google_connected" not in st.session_state:
        st.session_state.google_connected = False

    if "strava_connected" not in st.session_state:
        st.session_state.strava_connected = False

    if "config_data" not in st.session_state:
        st.session_state.config_data = {}


init_session_state()


# ============================================================================
# Sidebar Navigation
# ============================================================================

def render_sidebar():
    """Render the sidebar with navigation and status."""
    with st.sidebar:
        st.title("🏃 Running Group App")

        # Connection status
        st.subheader("Status")

        if st.session_state.google_connected:
            st.success("✅ Google connected")
        else:
            st.warning("⚠️ Google not connected")

        if st.session_state.strava_connected:
            st.success("✅ Strava connected")
        else:
            st.info("ℹ️ Strava not connected (optional)")

        st.divider()

        # Navigation
        st.subheader("Navigation")

        page = st.radio(
            "Go to",
            options=["🏠 Home", "⚙️ Settings", "📝 Compose Messages", "📅 Calendar Sync"],
            label_visibility="collapsed",
        )

        st.divider()

        # Help
        with st.expander("ℹ️ Help"):
            st.markdown("""
            **First time?**
            1. Go to Settings
            2. Connect your Google account
            3. Enter your Google Sheet ID
            4. Set up your group details

            **Weekly workflow:**
            1. Go to Compose Messages
            2. Select the date
            3. Copy messages to email/FB/WhatsApp
            """)

        return page


# ============================================================================
# Pages
# ============================================================================

def render_home():
    """Render the home page."""
    config = get_config()

    st.title(f"🏃 {config.group.name}")

    if not st.session_state.setup_complete:
        st.warning("👋 Welcome! Please complete the setup in **Settings** to get started.")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.info("**Step 1**\n\nConnect Google for calendar sync")

        with col2:
            st.info("**Step 2**\n\nEnter your Google Sheet ID")

        with col3:
            st.info("**Step 3**\n\nConfigure your group settings")

        if st.button("Go to Settings →", type="primary"):
            st.session_state.nav_to = "settings"
            st.rerun()

    else:
        # Show next run info
        st.subheader("Next Run")

        try:
            from core import get_next_run, load_schedule, format_date_uk

            runs = load_schedule()
            next_run = get_next_run(runs)

            if next_run:
                col1, col2 = st.columns(2)

                with col1:
                    st.metric("Date", format_date_uk(next_run.date))
                    st.metric("Meeting Point", next_run.meeting_point)

                with col2:
                    if next_run.route_1:
                        st.write(f"**8K:** {next_run.route_1.name}")
                    if next_run.route_2:
                        st.write(f"**5K:** {next_run.route_2.name}")
                    if next_run.route_3:
                        st.write(f"**Walk:** {next_run.route_3.name}")

                st.divider()

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("📝 Compose Messages", type="primary"):
                        st.session_state.nav_to = "compose"
                        st.rerun()
                with col2:
                    if st.button("📅 Sync Calendar"):
                        st.session_state.nav_to = "calendar"
                        st.rerun()
            else:
                st.info("No upcoming runs found in the schedule.")

        except Exception as e:
            st.error(f"Failed to load schedule: {e}")
            st.info("Check your Google Sheet settings.")


def render_settings():
    """Render the settings page."""
    st.title("⚙️ Settings")

    # Tabs for different setting categories
    tab1, tab2, tab3, tab4 = st.tabs(["🔗 Connections", "👥 Group", "📊 Spreadsheet", "📅 Calendar"])

    with tab1:
        render_connections_settings()

    with tab2:
        render_group_settings()

    with tab3:
        render_sheet_settings()

    with tab4:
        render_calendar_settings()


def render_connections_settings():
    """Render the connections tab."""
    from google_auth import render_google_oauth_button, clear_credentials as clear_google
    from strava_auth import render_strava_oauth_button, clear_credentials as clear_strava

    st.subheader("Google Connection")
    st.caption("Required for calendar sync and private sheet access")

    if st.session_state.google_connected:
        st.success("✅ Connected to Google")
        if st.button("Disconnect Google"):
            clear_google()
            st.rerun()
    else:
        render_google_oauth_button()

    st.divider()

    st.subheader("Strava Connection (Optional)")
    st.caption("For route distance and elevation data")

    if st.session_state.strava_connected:
        st.success("✅ Connected to Strava")
        if st.button("Disconnect Strava"):
            clear_strava()
            st.rerun()
    else:
        render_strava_oauth_button()


def render_group_settings():
    """Render the group settings tab."""
    config = get_config()

    st.subheader("Group Identity")

    name = st.text_input("Group Name", value=config.group.name)
    short_name = st.text_input("Short Name (optional)", value=config.group.short_name)

    st.subheader("Location")

    col1, col2 = st.columns(2)
    with col1:
        latitude = st.number_input("Latitude", value=config.group.latitude, format="%.4f")
    with col2:
        longitude = st.number_input("Longitude", value=config.group.longitude, format="%.4f")

    st.caption("Used for weather forecasts. Find your coordinates at latlong.net")

    timezone = st.selectbox(
        "Timezone",
        options=["Europe/London", "Europe/Dublin", "America/New_York", "America/Los_Angeles", "Australia/Sydney"],
        index=0 if config.group.timezone == "Europe/London" else 0,
    )

    st.subheader("Run Defaults")

    meeting_location = st.text_input(
        "Default Meeting Location",
        value=config.group.default_meeting_location,
    )

    start_time = st.time_input(
        "Default Start Time",
        value=None,  # TODO: Parse from config
    )

    run_day = st.selectbox(
        "Run Day",
        options=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        index=config.group.run_day_of_week,
    )

    if st.button("Save Group Settings", type="primary"):
        # Update config
        config.group.name = name
        config.group.short_name = short_name
        config.group.latitude = latitude
        config.group.longitude = longitude
        config.group.timezone = timezone
        config.group.default_meeting_location = meeting_location
        config.group.run_day_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].index(run_day)

        st.success("✅ Group settings saved!")
        st.session_state.setup_complete = True


def render_sheet_settings():
    """Render the spreadsheet settings tab."""
    config = get_config()

    st.subheader("Google Sheet")

    sheet_url = st.text_input(
        "Google Sheet URL or ID",
        value=config.sheet.spreadsheet_id,
        help="Paste the full URL or just the spreadsheet ID",
    )

    # Extract ID from URL if needed
    if sheet_url and "docs.google.com" in sheet_url:
        import re
        match = re.search(r"/spreadsheets/d/([^/]+)", sheet_url)
        if match:
            sheet_id = match.group(1)
            st.caption(f"Detected Sheet ID: `{sheet_id}`")
        else:
            sheet_id = sheet_url
    else:
        sheet_id = sheet_url

    tab_name = st.text_input(
        "Schedule Tab Name",
        value=config.sheet.schedule_tab_name,
        help="The name of the tab containing your run schedule",
    )

    st.info("💡 Make sure your sheet is shared as **'Anyone with the link can view'**")

    if st.button("Test Connection"):
        if sheet_id:
            try:
                from core import load_schedule_dataframe
                # Temporarily update config
                config.sheet.spreadsheet_id = sheet_id
                config.sheet.schedule_tab_name = tab_name

                df = load_schedule_dataframe()
                st.success(f"✅ Connected! Found {len(df)} rows.")
                st.dataframe(df.head())
            except Exception as e:
                st.error(f"❌ Failed to connect: {e}")
        else:
            st.warning("Please enter a Sheet URL or ID")

    st.divider()

    st.subheader("Column Mapping")
    st.caption("Map your spreadsheet columns to the expected fields")

    with st.expander("Advanced: Column Mapping"):
        st.info("Column mapping UI coming soon. Using defaults for now.")


def render_calendar_settings():
    """Render the calendar settings tab."""
    config = get_config()

    st.subheader("Google Calendar")

    if not st.session_state.google_connected:
        st.warning("Please connect Google first (in Connections tab)")
        return

    if config.calendar.calendar_id:
        st.success(f"✅ Calendar connected")
        st.code(config.calendar.calendar_id)

        st.subheader("Subscribe Link")
        st.caption("Share this with your runners so they can add the calendar")

        from core import get_subscribe_url, get_web_view_url
        subscribe_url = get_subscribe_url(config.calendar.calendar_id)
        web_url = get_web_view_url(config.calendar.calendar_id)

        st.code(subscribe_url)

        col1, col2 = st.columns(2)
        with col1:
            st.link_button("Open Web View", web_url)
        with col2:
            if st.button("Copy Subscribe Link"):
                st.write("Link copied!")  # TODO: Actual clipboard

    else:
        st.info("No calendar connected yet.")

        calendar_name = st.text_input(
            "Calendar Name",
            value=f"{config.group.name} Schedule",
            help="This will be the name of the public calendar runners subscribe to",
        )

        if st.button("Create Calendar", type="primary"):
            # TODO: Implement calendar creation
            st.info("Calendar creation will be implemented with Google OAuth")


def render_compose():
    """Render the message composer page."""
    st.title("📝 Compose Messages")

    try:
        from core import load_schedule, get_upcoming_runs, generate_messages, format_date_uk

        runs = load_schedule()
        upcoming = get_upcoming_runs(runs)

        if not upcoming:
            st.warning("No upcoming runs found in the schedule.")
            return

        # Date selector
        date_options = {format_date_uk(r.date): r for r in upcoming[:8]}
        selected_date = st.selectbox("Select Date", options=list(date_options.keys()))

        run = date_options[selected_date]

        # Options
        col1, col2 = st.columns(2)
        with col1:
            include_jeffing = st.checkbox("Include Jeffing option", value=True)
        with col2:
            pass  # Space for future options

        st.divider()

        # Generate messages
        messages = generate_messages(run, include_jeffing=include_jeffing)

        # Display in tabs
        tab1, tab2, tab3 = st.tabs(["📧 Email", "📘 Facebook", "💬 WhatsApp"])

        with tab1:
            st.subheader(messages.email.subject)
            st.text_area(
                "Email body",
                value=messages.email.body,
                height=400,
                key="email_body",
            )
            if st.button("Copy Email", key="copy_email"):
                st.success("Copied! (Clipboard functionality coming soon)")

        with tab2:
            st.text_area(
                "Facebook post",
                value=messages.facebook.body,
                height=400,
                key="fb_body",
            )
            if st.button("Copy Facebook", key="copy_fb"):
                st.success("Copied! (Clipboard functionality coming soon)")

        with tab3:
            st.text_area(
                "WhatsApp message",
                value=messages.whatsapp.body,
                height=400,
                key="wa_body",
            )
            if st.button("Copy WhatsApp", key="copy_wa"):
                st.success("Copied! (Clipboard functionality coming soon)")

    except Exception as e:
        st.error(f"Failed to load schedule: {e}")
        st.info("Check your Google Sheet settings in ⚙️ Settings")


def render_calendar():
    """Render the calendar sync page."""
    st.title("📅 Calendar Sync")

    config = get_config()

    if not st.session_state.google_connected:
        st.warning("Please connect Google first in ⚙️ Settings")
        return

    if not config.calendar.calendar_id:
        st.warning("Please set up your calendar first in ⚙️ Settings → Calendar")
        return

    try:
        from core import load_schedule, get_upcoming_runs, format_date_uk

        runs = load_schedule()
        upcoming = get_upcoming_runs(runs, include_cancelled=True)

        st.subheader("Upcoming Runs")

        for run in upcoming[:8]:
            col1, col2, col3 = st.columns([2, 2, 1])

            with col1:
                st.write(f"**{format_date_uk(run.date)}**")

            with col2:
                if run.is_cancelled:
                    st.write("❌ Cancelled")
                elif run.route_1:
                    st.write(run.route_1.name)
                else:
                    st.write("No route set")

            with col3:
                st.write("✅" if not run.is_cancelled else "—")

        st.divider()

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Preview Sync", type="secondary"):
                st.info("Sync preview (dry run) coming soon")

        with col2:
            if st.button("Sync Now", type="primary"):
                st.info("Calendar sync coming soon (requires Google OAuth)")

    except Exception as e:
        st.error(f"Failed to load schedule: {e}")


# ============================================================================
# Main
# ============================================================================

def main():
    """Main app entry point."""
    page = render_sidebar()

    # Handle navigation from buttons
    if "nav_to" in st.session_state:
        nav = st.session_state.nav_to
        del st.session_state.nav_to
        if nav == "settings":
            page = "⚙️ Settings"
        elif nav == "compose":
            page = "📝 Compose Messages"
        elif nav == "calendar":
            page = "📅 Calendar Sync"

    # Render selected page
    if page == "🏠 Home":
        render_home()
    elif page == "⚙️ Settings":
        render_settings()
    elif page == "📝 Compose Messages":
        render_compose()
    elif page == "📅 Calendar Sync":
        render_calendar()


if __name__ == "__main__":
    main()
