"""Thin wrapper around indianrailapi.com with an in-memory daily cache."""

import logging
from datetime import datetime, date
from functools import lru_cache
from typing import Optional

import requests

from config import RAIL_API_BASE, RAIL_API_KEY, CLASSES_TO_CHECK

logger = logging.getLogger(__name__)

# ── HTTP helper ───────────────────────────────────────────────────────────────

def _get(path: str) -> dict:
    url = f"{RAIL_API_BASE}/{path}"
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as e:
        logger.warning(f"HTTP {e.response.status_code} for {url}")
        return {}
    except Exception as e:
        logger.error(f"API error for {url}: {e}")
        return {}


# ── Train list (cached per route+date, refreshed daily) ──────────────────────

# Cache key includes today's date so the cache naturally expires each midnight.
@lru_cache(maxsize=64)
def _cached_trains(from_station: str, to_station: str, date_str: str, _cache_day: str) -> tuple:
    data = _get(
        f"TrainBetweenStation/apikey/{RAIL_API_KEY}"
        f"/From/{from_station}/To/{to_station}/Date/{date_str}"
    )
    if str(data.get("ResponseCode")) != "200":
        logger.warning(f"TrainBetweenStation non-200 for {from_station}→{to_station} on {date_str}: {data.get('Message', '')}")
        return ()
    return tuple(data.get("Trains", []))


def get_trains_between(from_station: str, to_station: str, travel_date: datetime) -> list[dict]:
    date_str = travel_date.strftime("%Y%m%d")
    cache_day = str(date.today())  # forces cache miss on a new calendar day
    trains = _cached_trains(from_station, to_station, date_str, cache_day)
    return list(trains)


# ── Seat availability ─────────────────────────────────────────────────────────

def parse_available_seats(availability_str: str) -> Optional[int]:
    """
    Parse IRCTC availability strings:
      'AVAILABLE-42'  → 42
      'GNWL28/WL15'  → None  (waitlisted)
      'REGRET/WL'    → None  (fully waitlisted)
    """
    s = (availability_str or "").strip().upper()
    if s.startswith("AVAILABLE-"):
        try:
            return int(s.split("-", 1)[1])
        except (IndexError, ValueError):
            pass
    return None


def get_seat_availability(
    train_no: str,
    from_station: str,
    to_station: str,
    travel_date: datetime,
) -> dict[str, int]:
    """
    Returns {class_code: seats_available} for all classes that have open seats.
    Classes where the train is waitlisted, doesn't exist, or the API errors
    are omitted from the result.
    """
    date_str = travel_date.strftime("%Y%m%d")
    results: dict[str, int] = {}

    for cls in CLASSES_TO_CHECK:
        data = _get(
            f"SeatAvailability/apikey/{RAIL_API_KEY}"
            f"/TrainNumber/{train_no}/From/{from_station}/To/{to_station}"
            f"/Date/{date_str}/Quota/GN/Class/{cls}"
        )
        if str(data.get("ResponseCode")) != "200":
            continue  # class doesn't exist on this train
        avail_list = data.get("Availability", [])
        if not avail_list:
            continue
        seats = parse_available_seats(avail_list[0].get("Availability", ""))
        if seats is not None:
            results[cls] = seats

    return results


# ── Departure time helper ─────────────────────────────────────────────────────

def departure_time(train: dict) -> str:
    """Best-effort extraction of departure time from a train record."""
    for key in ("DepartureTime", "DepTime", "Source_Departure_time", "Departure"):
        val = train.get(key, "")
        if val:
            return val.strip()
    return ""


def train_no(train: dict) -> str:
    for key in ("TrainNo", "Number", "Train_No"):
        val = train.get(key, "")
        if val:
            return str(val).strip()
    return ""


def train_name(train: dict) -> str:
    for key in ("TrainName", "Name", "Train_Name"):
        val = train.get(key, "")
        if val:
            return str(val).strip().title()
    return "Unknown"
