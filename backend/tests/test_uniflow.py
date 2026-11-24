from datetime import timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import decrypt_secret, encrypt_secret, hash_password, verify_password
from app.db.base import Base, utcnow
from app.integrations.google_calendar import compute_event_hash, sync_google_calendar
from app.integrations.ical_sync import import_ics_content, validate_public_ics_url
from app.integrations.notifier import evaluate_deadlines_and_notify
from app.models.entities import CalendarEvent, CalendarSource, Notification, Task, User


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def demo_user(db_session):
    user = User(
        email="teste@uniflow.local",
        display_name="Matheus Teste",
        password_hash=hash_password("senha-segura-123"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_security_password_and_encryption():
    hashed = hash_password("minha-senha")
    assert verify_password("minha-senha", hashed) is True
    assert verify_password("errada", hashed) is False

    token = "ya29.token-secreto-oauth"
    encrypted = encrypt_secret(token)
    assert encrypted != token
    assert decrypt_secret(encrypted) == token


def test_ssrf_blocks_private_and_loopback():
    with pytest.raises(ValueError):
        validate_public_ics_url("http://localhost:8000/calendar.ics")
    with pytest.raises(ValueError):
        validate_public_ics_url("http://127.0.0.1/secret.ics")
    with pytest.raises(ValueError):
        validate_public_ics_url("ftp://example.com/cal.ics")


def test_ics_import_idempotent_without_duplicates(db_session, demo_user):
    ics_bytes = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//UniFlow Test//PT-BR
BEGIN:VEVENT
UID:prova-test-001@uniflow
DTSTART:20261210T220000Z
DTEND:20261211T000000Z
SUMMARY:Prova de Redes
LOCATION:Sala 201
END:VEVENT
END:VCALENDAR"""

    source = CalendarSource(user_id=demo_user.id, name="Demo ICS", source_type="upload")
    db_session.add(source)
    db_session.commit()

    run1 = import_ics_content(db_session, demo_user.id, source, ics_bytes, trigger="manual")
    assert run1.status == "completed"
    assert run1.items_created == 1

    # Segunda execução com o mesmo conteúdo NÃO pode duplicar
    run2 = import_ics_content(db_session, demo_user.id, source, ics_bytes, trigger="manual")
    assert run2.status == "completed"
    assert run2.items_created == 0
    assert run2.items_unchanged == 1

    events = db_session.query(CalendarEvent).filter(CalendarEvent.user_id == demo_user.id).all()
    assert len(events) == 1
    assert events[0].is_read_only is True
    assert events[0].event_type == "exam"


def test_deadline_notifications_deduplication(db_session, demo_user):
    now = utcnow()
    task_overdue = Task(
        user_id=demo_user.id,
        title="Entrega atrasada",
        status="pending",
        priority="high",
        due_at=now - timedelta(hours=3),
    )
    task_soon = Task(
        user_id=demo_user.id,
        title="Entrega urgente",
        status="pending",
        priority="urgent",
        due_at=now + timedelta(minutes=45),
    )
    db_session.add_all([task_overdue, task_soon])
    db_session.commit()

    run1 = evaluate_deadlines_and_notify(db_session, demo_user.id, trigger="manual")
    assert run1.items_created == 2

    # Rodar novamente não cria notificações duplicadas
    run2 = evaluate_deadlines_and_notify(db_session, demo_user.id, trigger="manual")
    assert run2.items_created == 0
    assert db_session.query(Notification).count() == 2


def test_simulated_google_failure_is_logged_safely(db_session, demo_user):
    run = sync_google_calendar(db_session, demo_user.id, trigger="simulation", simulate_failure=True)
    assert run.status == "failed"
    assert run.error_summary is not None
    assert "503" in run.error_summary


def test_event_hash_detects_change():
    now = utcnow()
    ev = CalendarEvent(
        user_id="u1",
        title="Aula 1",
        all_day=False,
        start_at=now,
        end_at=now + timedelta(hours=1),
    )
    h1 = compute_event_hash(ev)
    ev.title = "Aula 1 — Sala alterada"
    h2 = compute_event_hash(ev)
    assert h1 != h2
