"""Entry point — two daily check runs at configurable times (default 9 AM and 5 PM IST)."""

import logging
import shutil
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config import CHECK_TIMES, EMAIL_FROM, EMAIL_PASSWORD
from alert_engine import run_check

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

TIMEZONE = "Asia/Kolkata"


def _validate_config() -> None:
    errors = []
    if not shutil.which("tesseract"):
        errors.append(
            "Tesseract not found. Install with: sudo apt-get install tesseract-ocr  "
            "(or brew install tesseract on macOS)"
        )
    if not EMAIL_FROM:
        errors.append("GMAIL_ADDRESS is not set in .env")
    if not EMAIL_PASSWORD:
        errors.append(
            "GMAIL_APP_PASSWORD is not set in .env "
            "(generate at https://myaccount.google.com/apppasswords)"
        )
    if errors:
        for e in errors:
            logger.error(f"Config error: {e}")
        sys.exit(1)


def _parse_check_times(times_str: str) -> list[tuple[int, int]]:
    result = []
    for t in times_str.split(","):
        try:
            h, m = map(int, t.strip().split(":"))
            result.append((h, m))
        except ValueError:
            logger.warning(f"Ignoring invalid CHECK_TIMES entry: {t!r}")
    return result


def main() -> None:
    _validate_config()

    check_times = _parse_check_times(CHECK_TIMES)
    if not check_times:
        logger.error("No valid CHECK_TIMES configured. Example: CHECK_TIMES=09:00,17:00")
        sys.exit(1)

    scheduler = BlockingScheduler(timezone=TIMEZONE)

    for hour, minute in check_times:
        label = f"{hour:02d}:{minute:02d}"
        scheduler.add_job(
            run_check,
            CronTrigger(hour=hour, minute=minute, timezone=TIMEZONE),
            id=f"check_{label}",
            max_instances=1,
            coalesce=True,
        )
        logger.info(f"Scheduled check at {label} IST")

    logger.info("Running initial check on startup…")
    run_check()

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
