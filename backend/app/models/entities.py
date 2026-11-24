from datetime import date, datetime
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, new_uuid, utcnow


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="America/Sao_Paulo", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    csrf_token: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped[User] = relationship("User")


class Subject(Base, TimestampMixin):
    __tablename__ = "subjects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    professor: Mapped[str | None] = mapped_column(String(160), nullable=True)
    term: Mapped[str | None] = mapped_column(String(80), nullable=True)
    color: Mapped[str] = mapped_column(String(7), default="#365D73", nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (Index("ix_subjects_user_archived_name", "user_id", "is_archived", "name"),)


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subject_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # status: pending | in_progress | completed
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    # priority: low | normal | high | urgent
    priority: Mapped[str] = mapped_column(String(20), default="normal", nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sync_due_to_google: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    subject: Mapped[Subject | None] = relationship("Subject")

    __table_args__ = (Index("ix_tasks_user_status_due", "user_id", "status", "due_at"),)


class CalendarEvent(Base, TimestampMixin):
    __tablename__ = "calendar_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subject_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    linked_task_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(240), nullable=True)
    # event_type: class | exam | assignment | academic | personal | other
    event_type: Mapped[str] = mapped_column(String(30), default="academic", nullable=False)

    all_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="America/Sao_Paulo", nullable=False)

    # origin: uniflow | google | ics | task
    origin: Mapped[str] = mapped_column(String(20), default="uniflow", nullable=False)
    sync_to_google: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_read_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    subject: Mapped[Subject | None] = relationship("Subject")


class CalendarConnection(Base, TimestampMixin):
    __tablename__ = "calendar_connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), default="google", nullable=False)
    account_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    calendar_id: Mapped[str] = mapped_column(String(255), default="primary", nullable=False)
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # connected | needs_reauth | disconnected | error
    connection_status: Mapped[str] = mapped_column(String(30), default="disconnected", nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class CalendarSource(Base, TimestampMixin):
    __tablename__ = "calendar_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    # source_type: url | upload
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    url_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_modified_header: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ExternalEventMapping(Base, TimestampMixin):
    __tablename__ = "external_event_mappings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    calendar_event_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("calendar_events.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)  # google | ics
    calendar_connection_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("calendar_connections.id", ondelete="CASCADE"), nullable=True
    )
    calendar_source_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("calendar_sources.id", ondelete="CASCADE"), nullable=True
    )
    external_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    remote_etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_synced_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    event: Mapped[CalendarEvent] = relationship("CalendarEvent")

    __table_args__ = (
        UniqueConstraint("provider", "external_event_id", "calendar_source_id", name="uq_mapping_ics_ext"),
    )


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)  # google | ics | notifications
    trigger: Mapped[str] = mapped_column(String(30), default="scheduled", nullable=False)  # scheduled | manual | simulation
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)  # running | completed | failed
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    items_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_deleted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_unchanged: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    notification_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    deduplication_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    related_task_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    related_event_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("calendar_events.id", ondelete="SET NULL"), nullable=True)
    webhook_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
