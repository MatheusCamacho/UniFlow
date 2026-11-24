from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import logging
from urllib.parse import urlencode
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decrypt_secret, encrypt_secret
from app.db.base import ensure_utc, utcnow
from app.integrations.http_client import ExternalServiceError, request_with_retry
from app.models.entities import (
    CalendarConnection,
    CalendarEvent,
    ExternalEventMapping,
    SyncRun,
)

logger = logging.getLogger("uniflow.google")

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"


def is_google_configured() -> bool:
    settings = get_settings()
    return bool(
        settings.google_client_id
        and settings.google_client_secret
        and "seu_google_client" not in settings.google_client_id
    )


def build_google_auth_url(state: str) -> str:
    """Monta URL de consentimento OAuth 2.0 do Google com escopo mínimo."""
    settings = get_settings()
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": settings.google_scopes,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def exchange_code_for_tokens(code: str) -> dict:
    """Troca o código de autorização OAuth por access_token e refresh_token."""
    settings = get_settings()
    response = request_with_retry(
        "POST",
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.google_redirect_uri,
            "grant_type": "authorization_code",
        },
    )
    if response.status_code != 200:
        raise ExternalServiceError(
            f"Erro ao trocar código OAuth (HTTP {response.status_code}).",
            status_code=response.status_code,
        )
    return response.json()


def _refresh_access_token(db: Session, conn: CalendarConnection) -> str:
    """Renova o access_token usando o refresh_token cifrado no banco."""
    if not conn.refresh_token_encrypted:
        conn.connection_status = "needs_reauth"
        conn.last_error = "Refresh token ausente. Reconecte a conta Google."
        db.commit()
        raise ExternalServiceError("Conexão Google exige reconexão (sem refresh token).", 401)

    settings = get_settings()
    refresh_token = decrypt_secret(conn.refresh_token_encrypted)

    response = request_with_retry(
        "POST",
        GOOGLE_TOKEN_URL,
        data={
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )

    if response.status_code in (400, 401):
        conn.connection_status = "needs_reauth"
        conn.last_error = "Token revogado ou expirado (em apps Testing expira em 7 dias). Reconecte."
        db.commit()
        raise ExternalServiceError("Token Google expirado/revogado. Reconecte a conta.", 401)

    if response.status_code != 200:
        raise ExternalServiceError(
            f"Falha ao renovar token Google (HTTP {response.status_code}).",
            status_code=response.status_code,
        )

    payload = response.json()
    access_token = payload["access_token"]
    expires_in = int(payload.get("expires_in", 3500))

    conn.access_token_encrypted = encrypt_secret(access_token)
    conn.token_expires_at = utcnow() + timedelta(seconds=max(60, expires_in - 60))
    conn.connection_status = "connected"
    conn.last_error = None
    db.commit()
    return access_token


def _get_valid_access_token(db: Session, conn: CalendarConnection) -> str:
    now = utcnow()
    if (
        conn.access_token_encrypted
        and conn.token_expires_at
        and ensure_utc(conn.token_expires_at) > now
    ):
        return decrypt_secret(conn.access_token_encrypted)
    return _refresh_access_token(db, conn)


def compute_event_hash(event: CalendarEvent) -> str:
    """Calcula hash determinístico dos campos relevantes para detectar mudanças reais."""
    canonical = {
        "title": event.title,
        "description": event.description or "",
        "location": event.location or "",
        "all_day": event.all_day,
        "start_at": ensure_utc(event.start_at).isoformat() if event.start_at else None,
        "end_at": ensure_utc(event.end_at).isoformat() if event.end_at else None,
        "start_date": event.start_date.isoformat() if event.start_date else None,
        "end_date": event.end_date.isoformat() if event.end_date else None,
        "deleted": event.deleted_at is not None,
    }
    raw = json.dumps(canonical, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _to_google_payload(event: CalendarEvent) -> dict:
    payload: dict = {
        "summary": event.title,
        "description": event.description or "",
        "location": event.location or "",
        "extendedProperties": {
            "private": {
                "uniflow_event_id": event.id,
                "uniflow_event_type": event.event_type,
            }
        },
    }
    if event.all_day and event.start_date:
        end_d = event.end_date or (event.start_date + timedelta(days=1))
        payload["start"] = {"date": event.start_date.isoformat()}
        payload["end"] = {"date": end_d.isoformat()}
    else:
        start_dt = ensure_utc(event.start_at) or utcnow()
        end_dt = ensure_utc(event.end_at) or (start_dt + timedelta(hours=1))
        payload["start"] = {
            "dateTime": start_dt.astimezone(timezone.utc).isoformat(),
            "timeZone": event.timezone,
        }
        payload["end"] = {
            "dateTime": end_dt.astimezone(timezone.utc).isoformat(),
            "timeZone": event.timezone,
        }
    return payload


def _parse_iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def sync_google_calendar(
    db: Session,
    user_id: str,
    trigger: str = "scheduled",
    simulate_failure: bool = False,
) -> SyncRun:
    """
    Sincronização bidirecional UniFlow <-> Google Calendar:
    1) Envia eventos locais marcados (criação, atualização e exclusão lógica).
    2) Busca alterações remotas de forma incremental via syncToken (recuperando HTTP 410).
    3) Registra métricas e possíveis falhas na tabela sync_runs.
    """
    run = SyncRun(user_id=user_id, provider="google", trigger=trigger, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        if simulate_failure:
            # Permite testar e demonstrar resiliência (Requisito 6) ao vivo
            raise ExternalServiceError(
                "Simulação controlada de indisponibilidade da Google Calendar API (HTTP 503 / Timeout).",
                status_code=503,
            )

        conn = (
            db.query(CalendarConnection)
            .filter(CalendarConnection.user_id == user_id, CalendarConnection.provider == "google")
            .first()
        )
        if not conn or conn.connection_status == "disconnected":
            run.status = "completed"
            run.finished_at = utcnow()
            run.error_summary = "Conta Google não conectada; sincronização ignorada."
            db.commit()
            return run

        access_token = _get_valid_access_token(db, conn)
        headers = {"Authorization": f"Bearer {access_token}"}
        cal_url = f"{GOOGLE_CALENDAR_API}/calendars/{conn.calendar_id}/events"

        # ------------------------------------------------------------------
        # ETAPA A: UniFlow -> Google (Push de eventos locais com sync ativo)
        # ------------------------------------------------------------------
        local_events = (
            db.query(CalendarEvent)
            .filter(
                CalendarEvent.user_id == user_id,
                CalendarEvent.sync_to_google.is_(True),
                CalendarEvent.is_read_only.is_(False),
            )
            .all()
        )

        for event in local_events:
            mapping = (
                db.query(ExternalEventMapping)
                .filter(
                    ExternalEventMapping.calendar_event_id == event.id,
                    ExternalEventMapping.provider == "google",
                )
                .first()
            )
            current_hash = compute_event_hash(event)

            # A1. Exclusão lógica (tombstone) propagada para o Google
            if event.deleted_at is not None:
                if mapping and mapping.last_synced_hash != current_hash:
                    resp = request_with_retry(
                        "DELETE", f"{cal_url}/{mapping.external_event_id}", headers=headers
                    )
                    if resp.status_code in (200, 204, 404, 410):
                        mapping.last_synced_hash = current_hash
                        run.items_deleted += 1
                    else:
                        raise ExternalServiceError(
                            f"Falha ao remover evento no Google (HTTP {resp.status_code}).",
                            resp.status_code,
                        )
                continue

            # A2. Criação no Google (evento novo sem mapping)
            if not mapping:
                resp = request_with_retry(
                    "POST", cal_url, headers=headers, json_body=_to_google_payload(event)
                )
                if resp.status_code not in (200, 201):
                    raise ExternalServiceError(
                        f"Falha ao criar evento no Google (HTTP {resp.status_code}).",
                        resp.status_code,
                    )
                remote = resp.json()
                db.add(
                    ExternalEventMapping(
                        calendar_event_id=event.id,
                        provider="google",
                        calendar_connection_id=conn.id,
                        external_event_id=remote["id"],
                        remote_etag=remote.get("etag"),
                        last_synced_hash=current_hash,
                    )
                )
                run.items_created += 1

            # A3. Atualização no Google (hash local mudou desde o último sync)
            elif mapping.last_synced_hash != current_hash:
                resp = request_with_retry(
                    "PATCH",
                    f"{cal_url}/{mapping.external_event_id}",
                    headers=headers,
                    json_body=_to_google_payload(event),
                )
                if resp.status_code == 200:
                    remote = resp.json()
                    mapping.remote_etag = remote.get("etag")
                    mapping.last_synced_hash = current_hash
                    run.items_updated += 1
                else:
                    raise ExternalServiceError(
                        f"Falha ao atualizar evento no Google (HTTP {resp.status_code}).",
                        resp.status_code,
                    )
            else:
                run.items_unchanged += 1

        db.commit()

        # ------------------------------------------------------------------
        # ETAPA B: Google -> UniFlow (Pull incremental com syncToken)
        # ------------------------------------------------------------------
        page_token: str | None = None
        next_sync_token: str | None = None
        retried_after_410 = False

        while True:
            params: dict = {"singleEvents": "true", "maxResults": 100}
            if conn.sync_token:
                # Requisito da Google API: nunca enviar timeMin/orderBy junto a syncToken
                params["syncToken"] = conn.sync_token
            else:
                # Sincronização inicial: últimos 30 dias em diante
                params["timeMin"] = (utcnow() - timedelta(days=30)).isoformat()

            if page_token:
                params["pageToken"] = page_token

            resp = request_with_retry("GET", cal_url, headers=headers, params=params)

            # Recuperação automática de syncToken inválido (HTTP 410 Gone)
            if resp.status_code == 410 and not retried_after_410:
                logger.warning("syncToken expirado (HTTP 410). Reiniciando sincronização completa.")
                conn.sync_token = None
                db.commit()
                retried_after_410 = True
                page_token = None
                continue

            if resp.status_code == 401:
                access_token = _refresh_access_token(db, conn)
                headers = {"Authorization": f"Bearer {access_token}"}
                continue

            if resp.status_code != 200:
                raise ExternalServiceError(
                    f"Erro ao consultar eventos do Google (HTTP {resp.status_code}).",
                    resp.status_code,
                )

            data = resp.json()
            for item in data.get("items", []):
                ext_id = item.get("id")
                if not ext_id:
                    continue

                mapping = (
                    db.query(ExternalEventMapping)
                    .filter(
                        ExternalEventMapping.provider == "google",
                        ExternalEventMapping.calendar_connection_id == conn.id,
                        ExternalEventMapping.external_event_id == ext_id,
                    )
                    .first()
                )

                # Evento cancelado/apagado no Google
                if item.get("status") == "cancelled":
                    if mapping and mapping.event and mapping.event.deleted_at is None:
                        mapping.event.deleted_at = utcnow()
                        mapping.last_synced_hash = compute_event_hash(mapping.event)
                        run.items_deleted += 1
                    continue

                start_obj = item.get("start", {})
                end_obj = item.get("end", {})
                all_day = "date" in start_obj

                start_at = _parse_iso_datetime(start_obj["dateTime"]) if not all_day and "dateTime" in start_obj else None
                end_at = _parse_iso_datetime(end_obj["dateTime"]) if not all_day and "dateTime" in end_obj else None
                start_date = date.fromisoformat(start_obj["date"]) if all_day else None
                end_date = date.fromisoformat(end_obj["date"]) if all_day and "date" in end_obj else None

                title = (item.get("summary") or "(Sem título)").strip()[:200]
                description = item.get("description")
                location = item.get("location")

                if mapping and mapping.event:
                    ev = mapping.event
                    ev.title = title
                    ev.description = description
                    ev.location = location
                    ev.all_day = all_day
                    ev.start_at = start_at
                    ev.end_at = end_at
                    ev.start_date = start_date
                    ev.end_date = end_date
                    ev.deleted_at = None
                    new_hash = compute_event_hash(ev)
                    if mapping.last_synced_hash != new_hash:
                        mapping.last_synced_hash = new_hash
                        mapping.remote_etag = item.get("etag")
                        run.items_updated += 1
                    else:
                        run.items_unchanged += 1
                else:
                    ev = CalendarEvent(
                        user_id=user_id,
                        title=title,
                        description=description,
                        location=location,
                        event_type="personal",
                        all_day=all_day,
                        start_at=start_at,
                        end_at=end_at,
                        start_date=start_date,
                        end_date=end_date,
                        origin="google",
                        sync_to_google=True,
                        is_read_only=False,
                    )
                    db.add(ev)
                    db.flush()
                    db.add(
                        ExternalEventMapping(
                            calendar_event_id=ev.id,
                            provider="google",
                            calendar_connection_id=conn.id,
                            external_event_id=ext_id,
                            remote_etag=item.get("etag"),
                            last_synced_hash=compute_event_hash(ev),
                        )
                    )
                    run.items_created += 1

            page_token = data.get("nextPageToken")
            if not page_token:
                next_sync_token = data.get("nextSyncToken")
                break

        if next_sync_token:
            conn.sync_token = next_sync_token
        conn.last_synced_at = utcnow()
        conn.connection_status = "connected"
        conn.last_error = None

        run.status = "completed"
        run.finished_at = utcnow()
        db.commit()
        return run

    except Exception as exc:
        logger.exception("Falha na sincronização Google Calendar.")
        run.status = "failed"
        run.finished_at = utcnow()
        run.error_summary = str(exc)[:500]
        db.commit()
        return run
