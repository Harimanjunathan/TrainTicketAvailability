"""RapidAPI IRCTC wrapper with an in-memory daily cache for the train list."""

import logging
from datetime import date, datetime
from functools import lru_cache
from typing import Optional

import requests

from config import CLASSES_TO_CHECK, RAPIDAPI_KEY

logger = logging.getLogger(__name__)

_RAPIDAPI_HOST = "irctc1.p.rapidapi.com"
_RAPIDAPI_BASE = "https://irctc1.p.rapidapi.com/api/v1"


def _headers() -> dict:
    return {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": _RAPIDAPI_HOST,
    }


def _get(endpoint: str, params: dict) -> dict:
    url = f"{_RAPIDAPI_BASE}/{endpoint}"
    try:
        r = requests.get(url, headers=_headers(), params=params, timeout=20)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as e:
        logger.warning(f"HTTP {e.response.status_code} for {endpoint} {params}")
        return {}
    except Exception as e:
        logger.error(f"API error for {endpoint}: {e}")
        return {}


# ── Response field extraction (defensive against provider field name changes) ─

def _extract_list(data: dict | list, *keys: str) -> list:
    """Walk nested dicts looking for the first key that holds a list."""
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for key in keys:
        val = data.get(key)
        if isinstance(val, list):
            return val
        if isinstance(val, dict):
            # one level deeper (e.g. body.avlDayList)
            for inner_key in keys:
                inner = val.get(inner_key)
                if isinstance(inner, list):
                    return inner
    return []


def _str_field(obj: dict, *keys: str) -> str:
    for key in keys:
        val = obj.get(key, "")
        if val:
            return str(val).strip()
    return ""


# ── Train list (cached per route+date, auto-expires at midnight) ─────────────

@lru_cache(maxsize=64)
def _cached_trains(
    from_station: str, to_station: str, date_str: str, _cache_day: str
) -> tuple:
    data = _get(
        "getTrainsBetweenStations",
        {
            "fromStationCode": from_station,
            "toStationCode": to_station,
            "dateOfJourney": date_str,
        },
    )
    trains = _extract_list(data, "data", "body", "trains", "Trains")
    if not trains:
        logger.warning(
            f"No trains returned for {from_station}→{to_station} on {date_str}. "
            f"Raw response keys: {list(data.keys()) if isinstance(data, dict) else type(data)}"
        )
    return tuple(trains)


def get_trains_between(
    from_station: str, to_station: str, travel_date: datetime
) -> list[dict]:
    date_str = travel_date.strftime("%Y%m%d")
    cache_day = str(date.today())
    return list(_cached_trains(from_station, to_station, date_str, cache_day))


# ── Seat availability ─────────────────────────────────────────────────────────

def parse_available_seats(availability_str: str) -> Optional[int]:
    """
    Parse IRCTC availability strings:
      'AVAILABLE-42'  → 42
      'GNWL28/WL15'   → None  (waitlisted)
      'REGRET/WL'     → None  (fully booked)
    """
    s = (availability_str or "").strip().upper()
    if s.startswith("AVAILABLE-"):
        try:
            return int(s.split("-", 1)[1])
        except (IndexError, ValueError):
            pass
    return None


def _parse_availability_response(data: dict | list) -> Optional[int]:
    """Extract seat count from whatever shape the RapidAPI response takes."""
    avail_list = _extract_list(
        data, "data", "body", "avlDayList", "Availability", "availability"
    )
    if not avail_list:
        return None
    first = avail_list[0]
    raw = _str_field(
        first,
        "availablityStatus",   # IRCTC spelling (sic)
        "availabilityStatus",
        "avail_status",
        "Availability",
        "status",
    )
    return parse_available_seats(raw) if raw else None


def get_seat_availability(
    train_no: str,
    from_station: str,
    to_station: str,
    travel_date: datetime,
) -> dict[str, int]:
    """
    Returns {class_code: seats_available} for classes with open seats.
    Waitlisted / non-existent classes are omitted.
    """
    date_str = travel_date.strftime("%Y%m%d")
    results: dict[str, int] = {}

    for cls in CLASSES_TO_CHECK:
        data = _get(
            "checkSeatAvailability",
            {
                "fromStationCode": from_station,
                "toStationCode": to_station,
                "trainNo": train_no,
                "date": date_str,
                "classType": cls,
                "quota": "GN",
            },
        )
        seats = _parse_availability_response(data)
        if seats is not None:
            results[cls] = seats

    return results


# ── Train record field helpers ────────────────────────────────────────────────

def departure_time(train: dict) -> str:
    return _str_field(
        train,
        "from_time", "departureTime", "DepartureTime",
        "DepTime", "Source_Departure_time", "Departure",
    )


def train_no(train: dict) -> str:
    return _str_field(train, "train_no", "trainNumber", "TrainNo", "Number", "Train_No")


def train_name(train: dict) -> str:
    raw = _str_field(train, "train_name", "trainName", "TrainName", "Name", "Train_Name")
    return raw.title() if raw else "Unknown"
