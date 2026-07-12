"""Entry point — starts the APScheduler and runs immediately on launch."""

import logging
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config import (
    CHECK_INTERVAL_MINUTES,
    DAILY_DIGEST_TIME,
    EMAIL_FROM,
    EMAIL_PASSWORD,
    RAIL_API_KEY,
)
from alert_engine import run_checks, run_daily_digest

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
    if not RAIL_API_KEY:
        errors.append("RAIL_API_KEY is not set (register at https://indianrailapi.com/registration)")
    if not EMAIL_FROM:
        errors.append("GMAIL_ADDRESS is not set")
    if not EMAIL_PASSWORD:
        errors.append("GMAIL_APP_PASSWORD is not set (create one at https://myaccount.google.com/apppasswords)")
    if errors:
        for e in errors:
            logger.error(f"Config error: {e}")
        sys.exit(1)


def main() -> None:
    _validate_config()

    digest_hour, digest_minute = map(int, DAILY_DIGEST_TIME.split(":"))

    scheduler = BlockingScheduler(timezone=TIMEZONE)

    scheduler.add_job(
        run_checks,
        "interval",
        minutes=CHECK_INTERVAL_MINUTES,
        id="hourly_checks",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        run_daily_digest,
        CronTrigger(hour=digest_hour, minute=digest_minute, timezone=TIMEZONE),
        id="daily_digest",
        max_instances=1,
    )

    logger.info(
        f"Scheduler starting — "
        f"availability checks every {CHECK_INTERVAL_MINUTES} min, "
        f"daily digest at {DAILY_DIGEST_TIME} IST"
    )

    # Run once immediately so there's no wait on first launch
    run_checks()

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
