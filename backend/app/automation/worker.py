import logging
import signal
import sys
from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy import text

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.integrations.google_calendar import sync_google_calendar
from app.integrations.ical_sync import sync_ics_url_source
from app.integrations.notifier import evaluate_deadlines_and_notify
from app.models.entities import CalendarSource, User

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("uniflow.worker")


def _run_with_advisory_lock(lock_id: int, job_name: str, fn) -> None:
    """Usa PostgreSQL advisory lock para evitar execuções simultâneas do mesmo job."""
    db = SessionLocal()
    acquired = False
    try:
        if engine.dialect.name == "postgresql":
            acquired = bool(db.execute(text("SELECT pg_try_advisory_lock(:id)"), {"id": lock_id}).scalar())
            if not acquired:
                logger.info("Job '%s' já está em execução em outro processo. Pulando.", job_name)
                return
        fn(db)
    except Exception:
        logger.exception("Erro não tratado no job '%s'.", job_name)
    finally:
        if acquired and engine.dialect.name == "postgresql":
            db.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": lock_id})
            db.commit()
        db.close()


def job_sync_google() -> None:
    def _execute(db):
        users = db.query(User).filter(User.is_active.is_(True)).all()
        for user in users:
            run = sync_google_calendar(db, user.id, trigger="scheduled")
            logger.info(
                "Google sync user=%s status=%s +%d ~%d -%d",
                user.email,
                run.status,
                run.items_created,
                run.items_updated,
                run.items_deleted,
            )

    _run_with_advisory_lock(1001, "google_sync", _execute)


def job_sync_ics() -> None:
    def _execute(db):
        sources = (
            db.query(CalendarSource)
            .filter(CalendarSource.is_enabled.is_(True), CalendarSource.source_type == "url")
            .all()
        )
        for source in sources:
            run = sync_ics_url_source(db, source, trigger="scheduled")
            logger.info("ICS sync source=%s status=%s +%d", source.name, run.status, run.items_created)

    _run_with_advisory_lock(1002, "ics_sync", _execute)


def job_check_deadlines() -> None:
    def _execute(db):
        users = db.query(User).filter(User.is_active.is_(True)).all()
        for user in users:
            run = evaluate_deadlines_and_notify(db, user.id, trigger="scheduled")
            logger.info("Deadlines check user=%s novos_alertas=%d", user.email, run.items_created)

    _run_with_advisory_lock(1003, "deadline_check", _execute)


def main() -> None:
    settings = get_settings()
    Base.metadata.create_all(bind=engine)

    scheduler = BlockingScheduler(timezone=settings.default_timezone)
    scheduler.add_job(
        job_sync_google,
        "interval",
        minutes=settings.google_sync_interval_minutes,
        id="google_sync",
        max_instances=1,
    )
    scheduler.add_job(
        job_sync_ics,
        "interval",
        minutes=settings.ics_sync_interval_minutes,
        id="ics_sync",
        max_instances=1,
    )
    scheduler.add_job(
        job_check_deadlines,
        "interval",
        minutes=settings.deadline_check_interval_minutes,
        id="deadline_check",
        max_instances=1,
    )

    def _shutdown(signum, frame):
        logger.info("Encerrando worker de automação UniFlow...")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    logger.info(
        "Worker UniFlow iniciado (Google=%dm, ICS=%dm, Prazos=%dm).",
        settings.google_sync_interval_minutes,
        settings.ics_sync_interval_minutes,
        settings.deadline_check_interval_minutes,
    )
    scheduler.start()


if __name__ == "__main__":
    main()
