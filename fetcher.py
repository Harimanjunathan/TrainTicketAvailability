"""
Scraper for the official Indian Railways enquiry system.

Site:  https://www.indianrail.gov.in/enquiry
Flow:  GET page to acquire session cookies
       GET captchaDraw.png → Tesseract OCR
       POST /CommonCaptcha with form payload + solved CAPTCHA
       Retry automatically when CAPTCHA is rejected (up to 4 attempts)
"""

import io
import logging
import time
from datetime import date, datetime
from functools import lru_cache
from typing import Optional

import requests
from PIL import Image, ImageFilter, ImageOps
import pytesseract

from config import CLASSES_TO_CHECK, KNOWN_TRAINS

logger = logging.getLogger(__name__)

_BASE = "https://www.indianrail.gov.in/enquiry"
_CAPTCHA_URL = f"{_BASE}/captchaDraw.png"
_API_URL = f"{_BASE}/CommonCaptcha"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.indianrail.gov.in",
    "Referer": f"{_BASE}/SEAT/SeatAvailability.html",
    "Content-Type": "application/json;charset=UTF-8",
}


# ── Session ───────────────────────────────────────────────────────────────────

def _new_session(page: str = "SEAT/SeatAvailability.html") -> requests.Session:
    """Create a session seeded with cookies from the given enquiry page."""
    s = requests.Session()
    headers = dict(_HEADERS)
    headers["Referer"] = f"{_BASE}/{page}"
    s.headers.update(headers)
    try:
        s.get(f"{_BASE}/{page}", timeout=20)
    except Exception as e:
        logger.warning(f"Session init warning (non-fatal): {e}")
    return s


# ── CAPTCHA ───────────────────────────────────────────────────────────────────

def _preprocess(img: Image.Image) -> Image.Image:
    img = img.convert("L")
    img = img.resize((img.width * 3, img.height * 3), Image.LANCZOS)
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.SHARPEN)
    img = img.point(lambda p: 255 if p > 128 else 0, "1")
    return img


def _solve_captcha(session: requests.Session) -> str:
    ts = int(time.time() * 1000)
    r = session.get(f"{_CAPTCHA_URL}?{ts}", timeout=15)
    img = Image.open(io.BytesIO(r.content))
    img = _preprocess(img)
    text = pytesseract.image_to_string(
        img,
        config=(
            "--psm 8 --oem 3 "
            "-c tessedit_char_whitelist="
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        ),
    )
    return text.strip().replace(" ", "")


def _post(session: requests.Session, payload: dict, max_retries: int = 4) -> dict:
    """POST to CommonCaptcha, refreshing the CAPTCHA on each rejection."""
    for attempt in range(max_retries):
        captcha_text = _solve_captcha(session)
        try:
            r = session.post(
                _API_URL,
                json={**payload, "captcha": captcha_text},
                timeout=20,
            )
            data = r.json() if r.text.strip() else {}
        except Exception as e:
            logger.warning(f"POST error attempt {attempt + 1}: {e}")
            time.sleep(1)
            continue

        err = str(data.get("errorMessage", "")).lower()
        if "captcha" in err or "invalid" in err or "wrong" in err:
            logger.debug(f"CAPTCHA rejected (attempt {attempt + 1}), retrying…")
            time.sleep(0.5)
            continue

        return data

    logger.error(f"Giving up after {max_retries} CAPTCHA failures for payload: {payload}")
    return {}


# ── Train list (cached per route+date, expires at midnight) ──────────────────

def _extract_trains(data: dict) -> list:
    return (
        data.get("trainBtwnStnsList")
        or data.get("trainsList")
        or data.get("trains")
        or []
    )


def _tbs_payload(from_station: str, to_station: str, date_str: str) -> dict:
    """Build the trains-between-stations POST payload (YYYYMMDD date)."""
    return {
        "pageId": "TBS",
        "inputPage": "TBS",
        "trainFromStn": from_station,
        "trainToStn": to_station,
        "datOfJourney": date_str,
        "flexiFlag": "N",
        "ticketType": "E",
        "trainClass": "ALL",
        "quota": "GN",
        "language": "en",
    }


@lru_cache(maxsize=32)
def _cached_trains(
    from_station: str, to_station: str, date_str: str, _cache_day: str
) -> tuple:
    """date_str is YYYYMMDD."""
    session = _new_session("TBS/TrainBetweenStation.html")

    # First attempt: YYYYMMDD date format (used by seat-availability endpoint)
    data = _post(session, _tbs_payload(from_station, to_station, date_str))
    trains = _extract_trains(data)

    if not trains:
        # Second attempt: DD-MM-YYYY date format (some TBS versions expect this)
        try:
            from datetime import datetime as _dt
            alt_date = _dt.strptime(date_str, "%Y%m%d").strftime("%d-%m-%Y")
            data2 = _post(session, _tbs_payload(from_station, to_station, alt_date))
            trains = _extract_trains(data2)
        except Exception as e:
            logger.debug(f"Alt date format attempt failed: {e}")

    if not trains:
        logger.warning(
            f"Live API returned no trains for {from_station}→{to_station} on {date_str} "
            f"(response keys: {list(data.keys())}). Falling back to hardcoded list."
        )
        trains = list(KNOWN_TRAINS.get((from_station, to_station), []))
        if trains:
            logger.info(
                f"Using {len(trains)} hardcoded trains for {from_station}→{to_station}"
            )
        else:
            logger.error(
                f"No hardcoded trains configured for {from_station}→{to_station}. "
                "Add entries to KNOWN_TRAINS in config.py."
            )

    return tuple(trains)


def get_trains_between(
    from_station: str, to_station: str, travel_date: datetime
) -> list[dict]:
    date_str = travel_date.strftime("%Y%m%d")
    cache_day = str(date.today())
    return list(_cached_trains(from_station, to_station, date_str, cache_day))


# ── Seat availability ─────────────────────────────────────────────────────────

def parse_available_seats(s: str) -> Optional[int]:
    s = (s or "").strip().upper()
    if s.startswith("AVAILABLE-"):
        try:
            return int(s.split("-", 1)[1])
        except (IndexError, ValueError):
            pass
    return None


def get_seat_availability(
    t_no: str,
    from_station: str,
    to_station: str,
    travel_date: datetime,
) -> dict[str, int]:
    """Returns {class_code: seats_available} for classes with open seats."""
    date_str = travel_date.strftime("%Y%m%d")
    session = _new_session()
    results: dict[str, int] = {}

    for cls in CLASSES_TO_CHECK:
        data = _post(
            session,
            {
                "pageId": "SeatAvailability",
                "trainNo": t_no,
                "fromStn": from_station,
                "toStn": to_station,
                "journeyDate": date_str,
                "classType": cls,
                "quota": "GN",
                "language": "en",
            },
        )
        avl_list = (
            data.get("avlDayList")
            or data.get("availabilityList")
            or data.get("Availability")
            or []
        )
        if not avl_list:
            continue
        first = avl_list[0]
        raw = ""
        for key in ("availablityStatus", "availabilityStatus", "avail_status", "Availability"):
            raw = first.get(key, "")
            if raw:
                break
        seats = parse_available_seats(raw)
        if seats is not None:
            results[cls] = seats

    return results


# ── Train record field helpers ────────────────────────────────────────────────

def _str_field(obj: dict, *keys: str) -> str:
    for key in keys:
        val = obj.get(key, "")
        if val:
            return str(val).strip()
    return ""


def departure_time(train: dict) -> str:
    return _str_field(
        train,
        "departTime", "departureTime", "from_time",
        "DepartureTime", "DepTime", "Departure",
    )


def train_no(train: dict) -> str:
    return _str_field(train, "trainNo", "train_no", "trainNumber", "TrainNo", "Number")


def train_name(train: dict) -> str:
    raw = _str_field(train, "trainName", "train_name", "TrainName", "Name")
    return raw.title() if raw else "Unknown"
