from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.db.base import ensure_utc, utcnow
from app.db.session import get_db
from app.models.entities import CalendarEvent, Task, User
from app.schemas.dto import TaskCreate, TaskOut, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["Tarefas"])


def _sync_linked_event_for_task(db: Session, task: Task) -> None:
    """Mantém um evento no calendário vinculado ao prazo da tarefa quando habilitado."""
    existing = (
        db.query(CalendarEvent)
        .filter(CalendarEvent.linked_task_id == task.id, CalendarEvent.user_id == task.user_id)
        .first()
    )

    if task.deleted_at is not None or not task.due_at or not task.sync_due_to_google:
        if existing and existing.deleted_at is None:
            existing.deleted_at = utcnow()
        return

    due_utc = ensure_utc(task.due_at)
    start_at = due_utc - timedelta(hours=1)
    end_at = due_utc

    if existing:
        existing.title = f"[Entrega] {task.title}"
        existing.description = task.description
        existing.subject_id = task.subject_id
        existing.start_at = start_at
        existing.end_at = end_at
        existing.sync_to_google = True
        existing.deleted_at = None
    else:
        db.add(
            CalendarEvent(
                user_id=task.user_id,
                subject_id=task.subject_id,
                linked_task_id=task.id,
                title=f"[Entrega] {task.title}",
                description=task.description,
                event_type="assignment",
                all_day=False,
                start_at=start_at,
                end_at=end_at,
                origin="task",
                sync_to_google=True,
                is_read_only=False,
            )
        )


@router.get("", response_model=list[TaskOut])
def list_tasks(
    status_filter: str | None = None,
    priority: str | None = None,
    subject_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = (
        db.query(Task)
        .options(joinedload(Task.subject))
        .filter(Task.user_id == user.id, Task.deleted_at.is_(None))
    )
    if status_filter:
        q = q.filter(Task.status == status_filter)
    if priority:
        q = q.filter(Task.priority == priority)
    if subject_id:
        q = q.filter(Task.subject_id == subject_id)
    return q.order_by(Task.due_at.asc().nullslast(), Task.created_at.desc()).all()


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = payload.model_dump()
    data['due_at'] = ensure_utc(data.get('due_at'))
    task = Task(user_id=user.id, **data)
    if task.status == "completed":
        task.completed_at = utcnow()
    db.add(task)
    db.flush()
    _sync_linked_event_for_task(db, task)
    db.commit()
    db.refresh(task)
    return task


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: str,
    payload: TaskUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = (
        db.query(Task)
        .options(joinedload(Task.subject))
        .filter(Task.id == task_id, Task.user_id == user.id, Task.deleted_at.is_(None))
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")

    updates = payload.model_dump(exclude_unset=True)
    if 'due_at' in updates:
        updates['due_at'] = ensure_utc(updates['due_at'])
    for field, value in updates.items():
        setattr(task, field, value)

    if "status" in updates:
        task.completed_at = utcnow() if task.status == "completed" else None

    _sync_linked_event_for_task(db, task)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id, Task.deleted_at.is_(None)).first()
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")

    task.deleted_at = utcnow()
    _sync_linked_event_for_task(db, task)
    db.commit()
