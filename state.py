"""Persistent JSON state — tracks which threshold alerts have already fired today."""

import json
import logging
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

STATE_FILE = Path("state.json")


def _load() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception as e:
            logger.warning(f"Could not read state file: {e}")
    return {"alerts_fired": {}}


def _save(state: dict) -> None:
    try:
        STATE_FILE.write_text(json.dumps(state, indent=2))
    except Exception as e:
        logger.error(f"Could not write state file: {e}")


def _alert_key(train_no: str, from_station: str, date_str: str, cls: str, threshold: int) -> str:
    return f"{train_no}|{from_station}|{date_str}|{cls}|{threshold}"


def has_alert_fired(
    train_no: str, from_station: str, date_str: str, cls: str, threshold: int
) -> bool:
    today = str(date.today())
    return _load()["alerts_fired"].get(today, {}).get(
        _alert_key(train_no, from_station, date_str, cls, threshold), False
    )


def mark_alert_fired(
    train_no: str, from_station: str, date_str: str, cls: str, threshold: int
) -> None:
    s = _load()
    today = str(date.today())
    s["alerts_fired"].setdefault(today, {})[
        _alert_key(train_no, from_station, date_str, cls, threshold)
    ] = True
    # Prune entries older than 3 days
    cutoff = str(date.fromordinal(date.today().toordinal() - 3))
    s["alerts_fired"] = {d: v for d, v in s["alerts_fired"].items() if d >= cutoff}
    _save(s)
