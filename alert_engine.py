"""Core logic: gather availability data, fire threshold alerts, build daily digest."""

import logging
from datetime import datetime, timedelta

from config import ALERT_THRESHOLDS, LOOKAHEAD_DAYS, ROUTES
from fetcher import (
    departure_time,
    get_seat_availability,
    get_trains_between,
    train_name,
    train_no,
)
from notifier import send_daily_digest, send_threshold_alert
import state

logger = logging.getLogger(__name__)


def _relevant_dates(route: dict) -> list[datetime]:
    today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
    return [
        today + timedelta(days=i)
        for i in range(LOOKAHEAD_DAYS)
        if (today + timedelta(days=i)).strftime("%A") in route["days"]
    ]


def _parse_time(time_str: str):
    """Parse HH:MM or HH:MM:SS, return a comparable time object or None."""
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(time_str.strip(), fmt).time()
        except ValueError:
            continue
    return None


def _in_window(dep_str: str, window: tuple[str, str]) -> bool:
    dep = _parse_time(dep_str)
    if dep is None:
        return False
    start = _parse_time(window[0])
    end = _parse_time(window[1])
    return start <= dep <= end


def _collect_route(route: dict) -> list[dict]:
    """Return availability rows for all trains/dates/classes on one route."""
    rows = []
    for travel_date in _relevant_dates(route):
        trains = get_trains_between(route["from_station"], route["to_station"], travel_date)
        for t in trains:
            dep = departure_time(t)
            if not _in_window(dep, route["departure_window"]):
                continue
            t_no = train_no(t)
            t_name = train_name(t)
            avail = get_seat_availability(t_no, route["from_station"], route["to_station"], travel_date)
            for cls, seats in avail.items():
                rows.append(
                    {
                        "route": route,
                        "travel_date": travel_date,
                        "train_no": t_no,
                        "train_name": t_name,
                        "departure": dep,
                        "cls": cls,
                        "seats": seats,
                    }
                )
    return rows


def run_checks() -> None:
    """Hourly job: check all routes and fire threshold alerts if needed."""
    logger.info("Running availability checks...")
    total_checked = 0

    for route in ROUTES:
        rows = _collect_route(route)
        total_checked += len(rows)
        for row in rows:
            date_str_key = row["travel_date"].strftime("%Y%m%d")
            for threshold in ALERT_THRESHOLDS:
                if row["seats"] <= threshold and not state.has_alert_fired(
                    row["train_no"], route["from_station"], date_str_key, row["cls"], threshold
                ):
                    state.mark_alert_fired(
                        row["train_no"], route["from_station"], date_str_key, row["cls"], threshold
                    )
                    send_threshold_alert(
                        route_name=route["name"],
                        train_no=row["train_no"],
                        train_name=row["train_name"],
                        travel_date=row["travel_date"].strftime("%d %b %Y (%A)"),
                        departure=row["departure"],
                        cls=row["cls"],
                        seats_available=row["seats"],
                        threshold=threshold,
                    )

    logger.info(f"Check complete — {total_checked} train/class combinations checked.")


def run_daily_digest() -> None:
    """Daily digest job: send one summary email of all upcoming trains."""
    today_str = datetime.today().strftime("%Y-%m-%d")
    if state.has_daily_digest_fired(today_str):
        logger.debug("Daily digest already sent today, skipping.")
        return

    logger.info("Sending daily digest...")
    digest_rows = []

    for route in ROUTES:
        rows = _collect_route(route)
        for row in rows:
            digest_rows.append(
                {
                    "date": row["travel_date"].strftime("%d %b (%a)"),
                    "route": route["name"],
                    "train_no": row["train_no"],
                    "train_name": row["train_name"],
                    "departure": row["departure"],
                    "cls": row["cls"],
                    "seats": row["seats"],
                }
            )

    # Sort by date then route then departure
    digest_rows.sort(key=lambda r: (r["date"], r["route"], r["departure"]))

    send_daily_digest(today_str, digest_rows)
    state.mark_daily_digest_fired(today_str)
