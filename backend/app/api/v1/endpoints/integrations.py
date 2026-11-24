from datetime import timedelta
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.security import encrypt_secret, generate_token
from app.db.base import utcnow
from app.db.session import get_db
from app.integrations.google_calendar import (
    build_google_auth_url,
    exchange_code_for_tokens,
    is_google_configured,
    sync_google_calendar,
)
from app.integrations.ical_sync import (
    import_ics_content,
    sync_ics_url_source,
    validate_public_ics_url,
)
from app.integrations.notifier import evaluate_deadlines_and_notify
from app.models.entities import CalendarConnection, CalendarSource, SyncRun, User
from app.schemas.dto import (
    CalendarSourceCreate,
    CalendarSourceOut,
    GoogleStatusOut,
    SyncRunOut,
)

router = APIRouter(prefix="/integrations", tags=["Integrações e Automação"])

# Estado OAuth em memória (para uso pessoal/single-instance)
_oauth_states: dict[str, str] = {}


@router.get("/google/status", response_model=GoogleStatusOut)
def google_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conn = (
        db.query(CalendarConnection)
        .filter(CalendarConnection.user_id == user.id, CalendarConnection.provider == "google")
        .first()
    )
    if not conn:
        return GoogleStatusOut(configured=is_google_configured(), connection_status="disconnected")
    return GoogleStatusOut(
        configured=is_google_configured(),
        connection_status=conn.connection_status,
        account_email=conn.account_email,
        calendar_id=conn.calendar_id,
        last_synced_at=conn.last_synced_at,
        last_error=conn.last_error,
    )


@router.get("/google/connect")
def google_connect(user: User = Depends(get_current_user)):
    if not is_google_configured():
        raise HTTPException(
            status_code=400,
            detail="Configure GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET no arquivo .env.",
        )
    state = generate_token(24)
    _oauth_states[state] = user.id
    return {"auth_url": build_google_auth_url(state)}


@router.get("/google/callback")
def google_callback(code: str | None = None, state: str | None = None, error: str | None = None, db: Session = Depends(get_db)):
    settings = get_settings()
    if error or not code or not state or state not in _oauth_states:
        return RedirectResponse(url=f"{settings.frontend_origin}/integrations?google=error")

    user_id = _oauth_states.pop(state)
    tokens = exchange_code_for_tokens(code)

    conn = (
        db.query(CalendarConnection)
        .filter(CalendarConnection.user_id == user_id, CalendarConnection.provider == "google")
        .first()
    )
    if not conn:
        conn = CalendarConnection(user_id=user_id, provider="google", calendar_id="primary")
        db.add(conn)

    conn.access_token_encrypted = encrypt_secret(tokens["access_token"])
    if tokens.get("refresh_token"):
        conn.refresh_token_encrypted = encrypt_secret(tokens["refresh_token"])
    conn.token_expires_at = utcnow() + timedelta(seconds=int(tokens.get("expires_in", 3500)) - 60)
    conn.connection_status = "connected"
    conn.last_error = None
    db.commit()

    # Executa sincronização inicial imediatamente após conectar
    sync_google_calendar(db, user_id, trigger="manual")
    return RedirectResponse(url=f"{settings.frontend_origin}/integrations?google=connected")


@router.post("/google/disconnect", status_code=status.HTTP_204_NO_CONTENT)
def google_disconnect(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conn = (
        db.query(CalendarConnection)
        .filter(CalendarConnection.user_id == user.id, CalendarConnection.provider == "google")
        .first()
    )
    if conn:
        conn.access_token_encrypted = None
        conn.refresh_token_encrypted = None
        conn.sync_token = None
        conn.connection_status = "disconnected"
        conn.last_error = None
        db.commit()


@router.post("/google/sync", response_model=SyncRunOut)
def trigger_google_sync(
    simulate_failure: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    trigger = "simulation" if simulate_failure else "manual"
    return sync_google_calendar(db, user.id, trigger=trigger, simulate_failure=simulate_failure)


@router.post("/deadlines/check", response_model=SyncRunOut)
def trigger_deadline_check(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return evaluate_deadlines_and_notify(db, user.id, trigger="manual")


# --- Fontes ICS ---
@router.get("/ics", response_model=list[CalendarSourceOut])
def list_ics_sources(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(CalendarSource)
        .filter(CalendarSource.user_id == user.id)
        .order_by(CalendarSource.created_at.desc())
        .all()
    )


@router.post("/ics/url", response_model=SyncRunOut, status_code=status.HTTP_201_CREATED)
def add_ics_url_source(
    payload: CalendarSourceCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        validate_public_ics_url(payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    source = CalendarSource(
        user_id=user.id,
        name=payload.name,
        source_type="url",
        url_encrypted=encrypt_secret(payload.url),
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return sync_ics_url_source(db, source, trigger="manual")


@router.post("/ics/upload", response_model=SyncRunOut, status_code=status.HTTP_201_CREATED)
async def upload_ics_file(
    name: str = Form("Calendário Acadêmico (.ics)"),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raw = await file.read()
    settings = get_settings()
    if len(raw) > settings.ics_max_bytes:
        raise HTTPException(status_code=400, detail="Arquivo .ics excede 5 MB.")

    source = (
        db.query(CalendarSource)
        .filter(CalendarSource.user_id == user.id, CalendarSource.name == name, CalendarSource.source_type == "upload")
        .first()
    )
    if not source:
        source = CalendarSource(user_id=user.id, name=name, source_type="upload")
        db.add(source)
        db.commit()
        db.refresh(source)

    return import_ics_content(db, user.id, source, raw, trigger="manual")


@router.post("/ics/{source_id}/sync", response_model=SyncRunOut)
def sync_single_ics(source_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    source = (
        db.query(CalendarSource)
        .filter(CalendarSource.id == source_id, CalendarSource.user_id == user.id)
        .first()
    )
    if not source:
        raise HTTPException(status_code=404, detail="Fonte ICS não encontrada.")
    return sync_ics_url_source(db, source, trigger="manual")


@router.delete("/ics/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ics_source(source_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    source = (
        db.query(CalendarSource)
        .filter(CalendarSource.id == source_id, CalendarSource.user_id == user.id)
        .first()
    )
    if not source:
        raise HTTPException(status_code=404, detail="Fonte ICS não encontrada.")
    db.delete(source)
    db.commit()


# --- Histórico de Execuções (Sync Runs) ---
@router.get("/sync-runs", response_model=list[SyncRunOut])
def list_sync_runs(
    limit: int = 30,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(SyncRun)
        .filter(SyncRun.user_id == user.id)
        .order_by(SyncRun.started_at.desc())
        .limit(min(limit, 100))
        .all()
    )
