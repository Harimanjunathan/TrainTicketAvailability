import os
from dotenv import load_dotenv

load_dotenv()

# ── Email ─────────────────────────────────────────────────────────────────────
EMAIL_FROM = os.getenv("GMAIL_ADDRESS", "")
EMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
EMAIL_TO = os.getenv("NOTIFY_EMAIL", "harimanjunath@gmail.com")

# ── Schedule ──────────────────────────────────────────────────────────────────
# Comma-separated HH:MM times (IST) to run checks and send summaries.
CHECK_TIMES = os.getenv("CHECK_TIMES", "09:00,17:00")
LOOKAHEAD_DAYS = int(os.getenv("LOOKAHEAD_DAYS", "14"))

# ── Alert thresholds (seats remaining) ────────────────────────────────────────
# One alert email per threshold per train/date/class per calendar day.
# Default: alert when ≤60 seats left, alert again at ≤20 seats left.
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
# silently skipped (the API returns an empty/error response for them).
CLASSES_TO_CHECK = ["1A", "2A", "3A", "SL", "CC", "EC", "2S"]

# Hardcoded fallback train list used when the live trains-between-stations
# API returns empty results. departTime is from the FROM station (HH:MM, 24h).
# Only trains whose departTime falls inside the route's departure_window are
# actually checked — add extras freely, they'll be filtered harmlessly.
KNOWN_TRAINS: dict[tuple[str, str], list[dict]] = {
    ("MAS", "SBC"): [
        {"trainNo": "12027", "trainName": "Shatabdi Express",           "departTime": "06:00"},
        {"trainNo": "22625", "trainName": "AC Double Decker Express",    "departTime": "16:30"},
        {"trainNo": "12677", "trainName": "Ernakulam Bangalore Express", "departTime": "18:45"},
        {"trainNo": "12609", "trainName": "Chennai Mysore Express",      "departTime": "22:30"},
    ],
    ("SBC", "MAS"): [
        {"trainNo": "12028", "trainName": "Shatabdi Express",            "departTime": "15:30"},
        {"trainNo": "22626", "trainName": "AC Double Decker Express",    "departTime": "18:00"},
        {"trainNo": "12610", "trainName": "Mysore Chennai Express",      "departTime": "18:30"},
        {"trainNo": "12678", "trainName": "Ernakulam Express",           "departTime": "19:30"},
    ],
}
