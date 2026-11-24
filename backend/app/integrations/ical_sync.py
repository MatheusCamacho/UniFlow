from datetime import date, datetime, timedelta, timezone
import ipaddress
import logging
import socket
from urllib.parse import urlparse
from icalendar import Calendar
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decrypt_secret
from app.db.base import utcnow
from app.integrations.google_calendar import compute_event_hash
from app.integrations.http_client import ExternalServiceError, request_with_retry
from app.models.entities import (
    CalendarEvent,
    CalendarSource,
    ExternalEventMapping,
    SyncRun,
)

logger = logging.getLogger("uniflow.ics")


def validate_public_ics_url(url: str) -> None:
    """
    Proteção contra SSRF: permite apenas HTTPS/HTTP públicos e bloqueia
    loopback, link-local, endereços privados e reservados.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http"):
        raise ValueError("A URL do calendário ICS deve usar protocolo HTTPS (ou HTTP).")
    if not parsed.hostname:
        raise ValueError("URL inválida: host ausente.")

    hostname = parsed.hostname.lower()
    if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        raise ValueError("Endereços locais (loopback) são bloqueados por segurança.")

    try:
        addr_info = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise ValueError(f"Não foi possível resolver o host '{hostname}'.") from exc

    for _, _, _, _, sockaddr in addr_info:
        ip_obj = ipaddress.ip_address(sockaddr[0])
        if (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_reserved
            or ip_obj.is_multicast
        ):
            raise ValueError(f"Destino bloqueado por política anti-SSRF ({ip_obj}).")


def _classify_event_type(summary: str, categories: str) -> str:
    text = f"{summary} {categories}".lower()
    if any(k in text for k in ("prova", "avaliação", "avaliacao", "exame", "exam")):
        return "exam"
    if any(k in text for k in ("trabalho", "entrega", "projeto", "assignment")):
        return "assignment"
    if any(k in text for k in ("aula", "class", "disciplina", "lab")):
        return "class"
    return "academic"


def _normalize_dt(dt_val) -> tuple[bool, datetime | None, date | None]:
    """Normaliza DTSTART/DTEND do RFC 5545 diferenciando dia inteiro vs instante UTC."""
    if isinstance(dt_val, datetime):
        if dt_val.tzinfo is None:
            dt_val = dt_val.replace(tzinfo=timezone(timedelta(hours=-3)))
        return False, dt_val.astimezone(timezone.utc), None
    if isinstance(dt_val, date):
        return True, None, dt_val
    return False, None, None


def import_ics_content(
    db: Session,
    user_id: str,
    source: CalendarSource,
    raw_bytes: bytes,
    trigger: str = "manual",
) -> SyncRun:
    """Faz o parse de conteúdo .ics (RFC 5545) e realiza upsert idempotente por UID."""
    run = SyncRun(user_id=user_id, provider="ics", trigger=trigger, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        cal = Calendar.from_ical(raw_bytes)
        seen_uids: set[str] = set()

        for component in cal.walk("VEVENT"):
            uid = str(component.get("uid") or "").strip()
            if not uid:
                continue

            recurrence_id = component.get("recurrence-id")
            ext_id = f"{uid}::{recurrence_id.dt.isoformat()}" if recurrence_id else uid
            seen_uids.add(ext_id)

            summary = str(component.get("summary") or "Evento acadêmico").strip()[:200]
            description = str(component.get("description") or "").strip() or None
            location = str(component.get("location") or "").strip()[:240] or None
            categories_raw = component.get("categories")
            categories = str(categories_raw.to_ical().decode("utf-8", errors="ignore")) if hasattr(categories_raw, "to_ical") else str(categories_raw or "")

            dtstart_prop = component.get("dtstart")
            if not dtstart_prop:
                continue

            all_day, start_at, start_date = _normalize_dt(dtstart_prop.dt)
            dtend_prop = component.get("dtend")
            if dtend_prop:
                _, end_at, end_date = _normalize_dt(dtend_prop.dt)
            else:
                end_at = (start_at + timedelta(hours=1)) if start_at else None
                end_date = (start_date + timedelta(days=1)) if start_date else None

            if not all_day and start_at and (not end_at or end_at <= start_at):
                end_at = start_at + timedelta(hours=1)
            if all_day and start_date and (not end_date or end_date <= start_date):
                end_date = start_date + timedelta(days=1)

            event_type = _classify_event_type(summary, categories)

            mapping = (
                db.query(ExternalEventMapping)
                .filter(
                    ExternalEventMapping.provider == "ics",
                    ExternalEventMapping.calendar_source_id == source.id,
                    ExternalEventMapping.external_event_id == ext_id,
                )
                .first()
            )

            if mapping and mapping.event:
                ev = mapping.event
                ev.title = summary
                ev.description = description
                ev.location = location
                ev.event_type = event_type
                ev.all_day = all_day
                ev.start_at = start_at
                ev.end_at = end_at
                ev.start_date = start_date
                ev.end_date = end_date
                ev.deleted_at = None
                ev.is_read_only = True
                new_hash = compute_event_hash(ev)
                if mapping.last_synced_hash != new_hash:
                    mapping.last_synced_hash = new_hash
                    run.items_updated += 1
                else:
                    run.items_unchanged += 1
            else:
                ev = CalendarEvent(
                    user_id=user_id,
                    title=summary,
                    description=description,
                    location=location,
                    event_type=event_type,
                    all_day=all_day,
                    start_at=start_at,
                    end_at=end_at,
                    start_date=start_date,
                    end_date=end_date,
                    origin="ics",
                    sync_to_google=False,
                    is_read_only=True,
                )
                db.add(ev)
                db.flush()
                db.add(
                    ExternalEventMapping(
                        calendar_event_id=ev.id,
                        provider="ics",
                        calendar_source_id=source.id,
                        external_event_id=ext_id,
                        last_synced_hash=compute_event_hash(ev),
                    )
                )
                run.items_created += 1

        # Remove logicamente eventos que desapareceram do feed ICS (sem tocar nos manuais)
        existing_mappings = (
            db.query(ExternalEventMapping)
            .filter(
                ExternalEventMapping.provider == "ics",
                ExternalEventMapping.calendar_source_id == source.id,
            )
            .all()
        )
        for m in existing_mappings:
            if m.external_event_id not in seen_uids and m.event and m.event.deleted_at is None:
                m.event.deleted_at = utcnow()
                run.items_deleted += 1

        source.last_fetched_at = utcnow()
        source.last_error = None
        run.status = "completed"
        run.finished_at = utcnow()
        db.commit()
        return run

    except Exception as exc:
        logger.exception("Erro ao importar ICS.")
        source.last_error = str(exc)[:500]
        run.status = "failed"
        run.finished_at = utcnow()
        run.error_summary = str(exc)[:500]
        db.commit()
        return run


def sync_ics_url_source(db: Session, source: CalendarSource, trigger: str = "scheduled") -> SyncRun:
    """Baixa feed ICS via HTTPS usando ETag/Last-Modified e validação anti-SSRF."""
    settings = get_settings()
    if source.source_type != "url" or not source.url_encrypted:
        run = SyncRun(
            user_id=source.user_id,
            provider="ics",
            trigger=trigger,
            status="completed",
            finished_at=utcnow(),
            error_summary="Fonte baseada em upload manual.",
        )
        db.add(run)
        db.commit()
        return run

    try:
        url = decrypt_secret(source.url_encrypted)
        validate_public_ics_url(url)

        headers: dict[str, str] = {"Accept": "text/calendar, text/plain"}
        if source.etag:
            headers["If-None-Match"] = source.etag
        if source.last_modified_header:
            headers["If-Modified-Since"] = source.last_modified_header

        response = request_with_retry("GET", url, headers=headers)

        if response.status_code == 304:
            source.last_fetched_at = utcnow()
            source.last_error = None
            run = SyncRun(
                user_id=source.user_id,
                provider="ics",
                trigger=trigger,
                status="completed",
                finished_at=utcnow(),
            )
            db.add(run)
            db.commit()
            return run

        if response.status_code != 200:
            raise ExternalServiceError(
                f"Feed ICS respondeu HTTP {response.status_code}.", response.status_code
            )

        if len(response.content) > settings.ics_max_bytes:
            raise ValueError("Arquivo ICS excede o limite de 5 MB.")

        if response.headers.get("ETag"):
            source.etag = response.headers["ETag"]
        if response.headers.get("Last-Modified"):
            source.last_modified_header = response.headers["Last-Modified"]
        db.commit()

        return import_ics_content(db, source.user_id, source, response.content, trigger=trigger)

    except Exception as exc:
        source.last_error = str(exc)[:500]
        run = SyncRun(
            user_id=source.user_id,
            provider="ics",
            trigger=trigger,
            status="failed",
            finished_at=utcnow(),
            error_summary=str(exc)[:500],
        )
        db.add(run)
        db.commit()
        return run
