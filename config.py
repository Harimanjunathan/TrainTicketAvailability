import os
from dotenv import load_dotenv

load_dotenv()

# ── API ───────────────────────────────────────────────────────────────────────
# Get your key at https://rapidapi.com/IRCTCAPI/api/irctc1
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")

# ── Email ─────────────────────────────────────────────────────────────────────
EMAIL_FROM = os.getenv("GMAIL_ADDRESS", "")
EMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
EMAIL_TO = os.getenv("NOTIFY_EMAIL", "harimanjunath@gmail.com")

# ── Schedule ──────────────────────────────────────────────────────────────────
# Comma-separated HH:MM times (IST) at which to run checks and send summaries.
CHECK_TIMES = os.getenv("CHECK_TIMES", "09:00,17:00")
LOOKAHEAD_DAYS = int(os.getenv("LOOKAHEAD_DAYS", "14"))

# ── Alert thresholds (seats remaining) ────────────────────────────────────────
# Fires one alert email per threshold per train/date/class per calendar day.
# Default: alert at ≤60 seats, alert again at ≤20 seats.
ALERT_THRESHOLDS = sorted(
    [int(x) for x in os.getenv("ALERT_THRESHOLDS", "60,20").split(",")],
    reverse=True,
)

# ── Routes ────────────────────────────────────────────────────────────────────
ROUTES = [
    {
        "name": "Chennai → Bangalore",
        "from_station": "MAS",  # Chennai Central
        "to_station": "SBC",   # KSR Bengaluru
        "days": ["Monday", "Tuesday"],
        "departure_window": (
            os.getenv("CHENNAI_BLR_WINDOW_START", "16:00"),
            os.getenv("CHENNAI_BLR_WINDOW_END", "22:00"),
        ),
    },
    {
        "name": "Bangalore → Chennai",
        "from_station": "SBC",
        "to_station": "MAS",
        "days": ["Thursday", "Friday"],
        "departure_window": (
            os.getenv("BLR_CHENNAI_WINDOW_START", "16:00"),
            os.getenv("BLR_CHENNAI_WINDOW_END", "22:00"),
        ),
    },
]

# All IRCTC class codes to attempt. Non-existent classes on a train are
# skipped (the API returns no valid availability for them).
CLASSES_TO_CHECK = ["1A", "2A", "3A", "SL", "CC", "EC", "2S"]
