# Running Group App

A web app for running groups to manage their weekly schedules, generate social media messages, and sync to Google Calendar.

## Features

- 📝 **Message Composer** - Generate weekly messages for email, Facebook, and WhatsApp
- 📅 **Calendar Sync** - Automatically sync your schedule to a subscribable Google Calendar
- 🌤️ **Weather-aware** - Messages adapt based on weather forecasts
- 🔄 **Varied content** - Greetings and closings rotate weekly to keep things fresh
- 🏃 **Route enrichment** - Optional Strava integration for distance/elevation data

## Quick Start

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure secrets**
   ```bash
   mkdir -p .streamlit
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   # Edit secrets.toml with your OAuth credentials
   ```

3. **Run the app**
   ```bash
   streamlit run web/app.py
   ```

## Setup Guide

### Google OAuth (Required for Calendar)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable the Google Calendar API
4. Create OAuth 2.0 credentials (Web application)
5. Add `http://localhost:8501` to authorized redirect URIs
6. Copy client ID and secret to `.streamlit/secrets.toml`

### Strava OAuth (Optional)

1. Go to [Strava API Settings](https://www.strava.com/settings/api)
2. Create an application
3. Copy client ID and secret to `.streamlit/secrets.toml`

### Google Sheet Setup

1. Create a Google Sheet with your run schedule
2. Make sure it's shared as "Anyone with the link can view"
3. Copy the spreadsheet ID from the URL

## Project Structure

```
running-group-app/
├── core/                    # Business logic (UI-agnostic)
│   ├── config.py           # Configuration management
│   ├── schedule_reader.py  # Load schedule from Google Sheets
│   ├── message_generator.py # Generate messages
│   ├── calendar_sync.py    # Google Calendar sync
│   └── weather.py          # Weather forecasts
│
├── web/                     # Streamlit UI
│   ├── app.py              # Main entry point
│   ├── google_auth.py      # Google OAuth flow
│   └── strava_auth.py      # Strava OAuth flow
│
├── api/                     # Future: FastAPI for mobile app
│
├── requirements.txt
└── README.md
```

## Architecture

The app is designed with separation of concerns:

- **`core/`** - Pure Python business logic with no UI dependencies
- **`web/`** - Streamlit-specific UI code
- **`api/`** - Future FastAPI backend for mobile apps

This allows the core logic to be reused across different interfaces.

## For Running Groups

To use this app for your running group:

1. Fork or copy this repository
2. Set up your Google OAuth credentials
3. Configure your group settings in the app
4. Connect your Google Sheet with your schedule
5. The app will create a subscribable calendar for your runners

## License

MIT
