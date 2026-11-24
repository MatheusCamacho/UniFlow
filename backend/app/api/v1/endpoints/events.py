from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.db.base import ensure_utc, utcnow
from app.db.session import get_db
from app.models.entities import CalendarEvent, User
from app.schemas.dto import EventCreate, EventOut, EventUpdate

router = APIRouter(prefix="/events", tags=["Calendário"])


@router.get("", response_model=list[EventOut])
def list_events(
    start: datetime | None = None,
    end: datetime | None = None,
    origin: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = (
        db.query(CalendarEvent)
        .options(joinedload(CalendarEvent.subject))
        .filter(CalendarEvent.user_id == user.id, CalendarEvent.deleted_at.is_(None))
    )
    if origin:
        q = q.filter(CalendarEvent.origin == origin)
    if start:
        q = q.filter((CalendarEvent.start_at >= start) | (CalendarEvent.start_date >= start.date()))
    if end:
        q = q.filter((CalendarEvent.start_at <= end) | (CalendarEvent.start_date <= end.date()))

    return q.order_by(CalendarEvent.start_at.asc().nullslast(), CalendarEvent.start_date.asc().nullslast()).all()


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
def create_event(
    payload: EventCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = CalendarEvent(
        user_id=user.id,
        origin="uniflow",
        is_read_only=False,
        **{**payload.model_dump(), 'start_at': ensure_utc(payload.start_at), 'end_at': ensure_utc(payload.end_at)},
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.patch("/{event_id}", response_model=EventOut)
def update_event(
    event_id: str,
    payload: EventUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = (
        db.query(CalendarEvent)
        .filter(CalendarEvent.id == event_id, CalendarEvent.user_id == user.id, CalendarEvent.deleted_at.is_(None))
        .first()
    )
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")
    if event.is_read_only:
        raise HTTPException(status_code=403, detail="Eventos importados de ICS são somente leitura.")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(event, field, value)
    db.commit()
    db.refresh(event)
    return event


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = (
        db.query(CalendarEvent)
        .filter(CalendarEvent.id == event_id, CalendarEvent.user_id == user.id, CalendarEvent.deleted_at.is_(None))
        .first()
    )
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")
    if event.is_read_only:
        raise HTTPException(status_code=403, detail="Eventos importados de ICS são somente leitura.")

    # Tombstone lógico para propagar exclusão ao Google Calendar no próximo sync
    event.deleted_at = utcnow()
    db.commit()
