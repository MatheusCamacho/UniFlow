from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Auth ---
class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(ORMModel):
    id: str
    email: str
    display_name: str
    timezone: str


class AuthResponse(BaseModel):
    user: UserOut
    csrf_token: str


# --- Subjects ---
class SubjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    code: str | None = Field(default=None, max_length=60)
    professor: str | None = Field(default=None, max_length=160)
    term: str | None = Field(default=None, max_length=80)
    color: str = Field(default="#365D73", pattern=r"^#[0-9A-Fa-f]{6}$")
    description: str | None = None


class SubjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    code: str | None = None
    professor: str | None = None
    term: str | None = None
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    description: str | None = None
    is_archived: bool | None = None


class SubjectOut(ORMModel):
    id: str
    name: str
    code: str | None
    professor: str | None
    term: str | None
    color: str
    description: str | None
    is_archived: bool


# --- Tasks ---
TaskStatus = Literal["pending", "in_progress", "completed"]
TaskPriority = Literal["low", "normal", "high", "urgent"]


class TaskCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str | None = None
    subject_id: str | None = None
    status: TaskStatus = "pending"
    priority: TaskPriority = "normal"
    due_at: datetime | None = None
    estimated_minutes: int | None = Field(default=None, gt=0)
    sync_due_to_google: bool = False


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = None
    subject_id: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_at: datetime | None = None
    estimated_minutes: int | None = Field(default=None, gt=0)
    sync_due_to_google: bool | None = None


class TaskOut(ORMModel):
    id: str
    subject_id: str | None
    title: str
    description: str | None
    status: str
    priority: str
    due_at: datetime | None
    estimated_minutes: int | None
    sync_due_to_google: bool
    completed_at: datetime | None
    created_at: datetime
    subject: SubjectOut | None = None


# --- Calendar Events ---
EventType = Literal["class", "exam", "assignment", "academic", "personal", "other"]


class EventCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str | None = None
    location: str | None = None
    subject_id: str | None = None
    event_type: EventType = "academic"
    all_day: bool = False
    start_at: datetime | None = None
    end_at: datetime | None = None
    start_date: date | None = None
    end_date: date | None = None
    timezone: str = "America/Sao_Paulo"
    sync_to_google: bool = False

    @field_validator("end_at")
    @classmethod
    def check_timed_range(cls, v, info):
        start_at = info.data.get("start_at")
        if not info.data.get("all_day") and start_at and v and v <= start_at:
            raise ValueError("end_at deve ser posterior a start_at.")
        return v


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = None
    location: str | None = None
    subject_id: str | None = None
    event_type: EventType | None = None
    all_day: bool | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    start_date: date | None = None
    end_date: date | None = None
    sync_to_google: bool | None = None


class EventOut(ORMModel):
    id: str
    subject_id: str | None
    linked_task_id: str | None
    title: str
    description: str | None
    location: str | None
    event_type: str
    all_day: bool
    start_at: datetime | None
    end_at: datetime | None
    start_date: date | None
    end_date: date | None
    timezone: str
    origin: str
    sync_to_google: bool
    is_read_only: bool
    subject: SubjectOut | None = None


# --- Integrations & Sync ---
class CalendarSourceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    url: str = Field(min_length=8, max_length=2000)


class CalendarSourceOut(ORMModel):
    id: str
    name: str
    source_type: str
    last_fetched_at: datetime | None
    is_enabled: bool
    last_error: str | None


class GoogleStatusOut(BaseModel):
    configured: bool
    connection_status: str
    account_email: str | None = None
    calendar_id: str | None = None
    last_synced_at: datetime | None = None
    last_error: str | None = None


class SyncRunOut(ORMModel):
    id: str
    provider: str
    trigger: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    items_created: int
    items_updated: int
    items_deleted: int
    items_unchanged: int
    error_summary: str | None


class NotificationOut(ORMModel):
    id: str
    notification_type: str
    title: str
    body: str
    related_task_id: str | None
    related_event_id: str | None
    webhook_sent: bool
    read_at: datetime | None
    created_at: datetime


class DashboardOut(BaseModel):
    today_events: list[EventOut]
    overdue_tasks: list[TaskOut]
    upcoming_tasks: list[TaskOut]
    weekly_completed: int
    weekly_pending: int
    overdue_count: int
    google_status: GoogleStatusOut
    unread_notifications: int
