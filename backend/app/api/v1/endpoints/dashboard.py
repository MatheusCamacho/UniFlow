from datetime import timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.db.base import ensure_utc, utcnow
from app.db.session import get_db
from app.integrations.google_calendar import is_google_configured
from app.models.entities import CalendarConnection, CalendarEvent, Notification, Task, User
from app.schemas.dto import DashboardOut, GoogleStatusOut

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("", response_model=DashboardOut)
def get_dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = utcnow()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    week_ago = now - timedelta(days=7)

    all_events = (
        db.query(CalendarEvent)
        .options(joinedload(CalendarEvent.subject))
        .filter(CalendarEvent.user_id == user.id, CalendarEvent.deleted_at.is_(None))
        .all()
    )
    today_events = [
        ev
        for ev in all_events
        if (ev.start_at and day_start <= ensure_utc(ev.start_at) < day_end)
        or (ev.all_day and ev.start_date == now.date())
    ]
    today_events.sort(key=lambda e: ensure_utc(e.start_at) or day_start)

    all_tasks = (
        db.query(Task)
        .options(joinedload(Task.subject))
        .filter(Task.user_id == user.id, Task.deleted_at.is_(None))
        .all()
    )

    overdue_tasks = [
        t for t in all_tasks
        if t.status != "completed" and t.due_at and ensure_utc(t.due_at) < now
    ]
    overdue_tasks.sort(key=lambda t: ensure_utc(t.due_at))

    upcoming_tasks = [
        t for t in all_tasks
        if t.status != "completed" and (t.due_at is None or ensure_utc(t.due_at) >= now)
    ]
    upcoming_tasks.sort(key=lambda t: ensure_utc(t.due_at) or (now + timedelta(days=3650)))

    weekly_completed = sum(
        1 for t in all_tasks
        if t.status == "completed" and t.completed_at and ensure_utc(t.completed_at) >= week_ago
    )
    weekly_pending = sum(1 for t in all_tasks if t.status != "completed")

    conn = (
        db.query(CalendarConnection)
        .filter(CalendarConnection.user_id == user.id, CalendarConnection.provider == "google")
        .first()
    )
    google_status = (
        GoogleStatusOut(
            configured=is_google_configured(),
            connection_status=conn.connection_status,
            account_email=conn.account_email,
            calendar_id=conn.calendar_id,
            last_synced_at=conn.last_synced_at,
            last_error=conn.last_error,
        )
        if conn
        else GoogleStatusOut(configured=is_google_configured(), connection_status="disconnected")
    )

    unread_notifications = (
        db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.read_at.is_(None))
        .count()
    )

    return DashboardOut(
        today_events=today_events,
        overdue_tasks=overdue_tasks,
        upcoming_tasks=upcoming_tasks[:8],
        weekly_completed=weekly_completed,
        weekly_pending=weekly_pending,
        overdue_count=len(overdue_tasks),
        google_status=google_status,
        unread_notifications=unread_notifications,
    )
