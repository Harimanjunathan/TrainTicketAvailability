"""Core logic: gather availability data, fire threshold alerts, send check summary."""

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
from notifier import send_check_summary, send_threshold_alert
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
    return _parse_time(window[0]) <= dep <= _parse_time(window[1])


def _collect_route(route: dict) -> list[dict]:
    """Fetch availability for all in-window trains across all monitored dates."""
    rows = []
    for travel_date in _relevant_dates(route):
        try:
            trains = get_trains_between(route["from_station"], route["to_station"], travel_date)
        except Exception as e:
            logger.error(f"Failed to fetch trains for {route['name']} on {travel_date.date()}: {e}")
            continue
        for t in trains:
            dep = departure_time(t)
            if not _in_window(dep, route["departure_window"]):
                continue
            t_no = train_no(t)
            t_name = train_name(t)
            try:
                avail = get_seat_availability(
                    t_no, route["from_station"], route["to_station"], travel_date
                )
            except Exception as e:
                logger.error(f"Failed to fetch seat availability for train {t_no}: {e}")
                continue
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


def run_check() -> None:
    """
    Runs at each scheduled time (9 AM and 5 PM IST):
    1. Fetches availability for all monitored routes/dates/classes.
    2. Fires threshold alert emails for newly crossed thresholds.
    3. Sends a full availability summary email.
    """
    now_label = datetime.now().strftime("%d %b %Y, %I:%M %p")
    logger.info(f"Running availability check at {now_label}...")

    all_rows: list[dict] = []
    for route in ROUTES:
        all_rows.extend(_collect_route(route))

    # ── Threshold alerts ──────────────────────────────────────────────────────
    alerts_fired = 0
    for row in all_rows:
        date_key = row["travel_date"].strftime("%Y%m%d")
        for threshold in ALERT_THRESHOLDS:
            if row["seats"] <= threshold and not state.has_alert_fired(
                row["train_no"], row["route"]["from_station"], date_key, row["cls"], threshold
            ):
                state.mark_alert_fired(
                    row["train_no"], row["route"]["from_station"], date_key, row["cls"], threshold
                )
                send_threshold_alert(
                    route_name=row["route"]["name"],
                    train_no=row["train_no"],
                    train_name=row["train_name"],
                    travel_date=row["travel_date"].strftime("%d %b %Y (%A)"),
                    departure=row["departure"],
                    cls=row["cls"],
                    seats_available=row["seats"],
                    threshold=threshold,
                )
                alerts_fired += 1

    # ── Summary email ─────────────────────────────────────────────────────────
    summary_rows = sorted(
        [
            {
                "date": r["travel_date"].strftime("%d %b (%a)"),
                "route": r["route"]["name"],
                "train_no": r["train_no"],
                "train_name": r["train_name"],
                "departure": r["departure"],
                "cls": r["cls"],
                "seats": r["seats"],
            }
            for r in all_rows
        ],
        key=lambda r: (r["date"], r["route"], r["departure"]),
    )
    send_check_summary(now_label, summary_rows)

    logger.info(
        f"Check complete — {len(all_rows)} combinations checked, "
        f"{alerts_fired} new threshold alert(s) fired."
    )
