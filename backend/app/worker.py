"""Background collection scheduler.

Polls enabled connectors with an interval and runs those that are due. DB-based scheduling keeps
the modular monolith simple; swap for Celery/RQ + Redis if job volume grows.
Run: python -m app.worker"""
import logging
import time
from datetime import timedelta

from sqlalchemy import select

import app.services.market_data  # noqa: F401
from app.core.database import SessionLocal
from app.models import DataConnector
from app.models.base import utcnow
from app.services.geo import aware
from app.services.market_data.pipeline import run_collection

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("tradeflow.worker")
POLL_SECONDS = 60
PUSH_ONLY = {"file_import", "supplier_submission", "manual_entry"}


def run_due_once() -> int:
    db = SessionLocal()
    ran = 0
    try:
        conns = db.scalars(select(DataConnector).where(DataConnector.is_enabled.is_(True),
                                                       DataConnector.interval_minutes.is_not(None))).all()
        now = utcnow()
        for c in conns:
            if c.connector_type in PUSH_ONLY or not c.data_source.is_active:
                continue
            last = aware(c.last_run_at)
            if last and now - last < timedelta(minutes=c.interval_minutes):
                continue
            log.info("Running connector %s (%s)", c.id, c.name)
            job = run_collection(db, source=c.data_source, connector=c, user=None, trigger="schedule")
            log.info("Connector %s finished: %s collected=%s rejected=%s error=%s", c.id, job.status,
                     job.records_collected, job.records_rejected, job.error)
            ran += 1
    finally:
        db.close()
    return ran


def main() -> None:
    log.info("TradeFlow worker started (poll every %ss)", POLL_SECONDS)
    while True:
        try:
            run_due_once()
        except Exception:  # noqa: BLE001
            log.exception("Worker iteration failed")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
