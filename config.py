import os
from dotenv import load_dotenv

load_dotenv()

# ── API ──────────────────────────────────────────────────────────────────────
RAIL_API_KEY = os.getenv("RAIL_API_KEY", "")
RAIL_API_BASE = "https://indianrailapi.com/api/v2"

# ── Email ────────────────────────────────────────────────────────────────────
EMAIL_FROM = os.getenv("GMAIL_ADDRESS", "")
EMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
EMAIL_TO = os.getenv("NOTIFY_EMAIL", "harimanjunath@gmail.com")

# ── Schedule ─────────────────────────────────────────────────────────────────
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "60"))
# HH:MM in IST — time to send the daily availability digest
DAILY_DIGEST_TIME = os.getenv("DAILY_DIGEST_TIME", "08:00")
LOOKAHEAD_DAYS = int(os.getenv("LOOKAHEAD_DAYS", "14"))

# ── Alert thresholds (seats remaining) ───────────────────────────────────────
# Fires one email per threshold per train/date/class per day.
# Default: alert when ≤60 seats left, alert again when ≤20 seats left.
ALERT_THRESHOLDS = sorted(
    [int(x) for x in os.getenv("ALERT_THRESHOLDS", "60,20").split(",")],
    reverse=True,
)

# ── Routes ───────────────────────────────────────────────────────────────────
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

# All IRCTC class codes to attempt per train. Classes a train doesn't have
# are silently skipped (the API returns a non-200 ResponseCode).
CLASSES_TO_CHECK = ["1A", "2A", "3A", "SL", "CC", "EC", "2S"]
