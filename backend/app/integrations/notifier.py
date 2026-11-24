from datetime import timedelta, timezone
import logging
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import utcnow
from app.integrations.http_client import request_with_retry
from app.models.entities import Notification, SyncRun, Task

logger = logging.getLogger("uniflow.notifier")


def _send_external_webhook(title: str, body: str) -> bool:
    """Envia alerta formatado para Webhook externo (Discord/Slack/Telegram bridge) se configurado."""
    settings = get_settings()
    webhook_url = settings.alert_webhook_url.strip()
    if not webhook_url:
        return False

    try:
        payload = {"content": f"**[UniFlow] {title}**\n{body}"}
        resp = request_with_retry("POST", webhook_url, json_body=payload, max_attempts=2)
        return 200 <= resp.status_code < 300
    except Exception as exc:
        logger.warning("Não foi possível enviar webhook de alerta: %s", exc)
        return False


def evaluate_deadlines_and_notify(
    db: Session, user_id: str, trigger: str = "scheduled"
) -> SyncRun:
    """
    Analisa tarefas pendentes/em andamento e aplica regras condicionais de alerta:
    - Tarefa atrasada (1 alerta por dia por tarefa)
    - Prazo em até 2 horas (urgente)
    - Prazo em até 24 horas (lembrete preventivo)
    Deduplicação garantida por deduplication_key única no banco.
    """
    run = SyncRun(user_id=user_id, provider="notifications", trigger=trigger, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        now = utcnow()
        today_key = now.strftime("%Y-%m-%d")

        tasks = (
            db.query(Task)
            .filter(
                Task.user_id == user_id,
                Task.deleted_at.is_(None),
                Task.status != "completed",
                Task.due_at.is_not(None),
            )
            .all()
        )

        for task in tasks:
            due = task.due_at
            if due is None:
                continue
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)

            delta = due - now
            notif_type: str | None = None
            dedup_key: str | None = None
            title = ""
            body = ""

            if delta.total_seconds() < 0:
                notif_type = "task_overdue"
                dedup_key = f"{user_id}:overdue:{task.id}:{today_key}"
                title = f"Tarefa atrasada: {task.title}"
                body = f"O prazo venceu em {due.strftime('%d/%m/%Y %H:%M')} UTC. Prioridade: {task.priority}."
            elif delta <= timedelta(hours=2):
                notif_type = "task_due_2h"
                dedup_key = f"{user_id}:due2h:{task.id}:{due.isoformat()}"
                title = f"Entrega em menos de 2h: {task.title}"
                body = f"Prazo final em {due.strftime('%d/%m/%Y %H:%M')} UTC."
            elif delta <= timedelta(hours=24):
                notif_type = "task_due_24h"
                dedup_key = f"{user_id}:due24h:{task.id}:{due.isoformat()}"
                title = f"Prazo nas próximas 24h: {task.title}"
                body = f"Lembrete preventivo para entrega em {due.strftime('%d/%m/%Y %H:%M')} UTC."

            if not notif_type or not dedup_key:
                run.items_unchanged += 1
                continue

            exists = (
                db.query(Notification)
                .filter(Notification.deduplication_key == dedup_key)
                .first()
            )
            if exists:
                run.items_unchanged += 1
                continue

            webhook_ok = _send_external_webhook(title, body)
            db.add(
                Notification(
                    user_id=user_id,
                    notification_type=notif_type,
                    title=title,
                    body=body,
                    deduplication_key=dedup_key,
                    related_task_id=task.id,
                    webhook_sent=webhook_ok,
                )
            )
            run.items_created += 1

        run.status = "completed"
        run.finished_at = utcnow()
        db.commit()
        return run

    except Exception as exc:
        logger.exception("Erro ao avaliar prazos.")
        run.status = "failed"
        run.finished_at = utcnow()
        run.error_summary = str(exc)[:500]
        db.commit()
        return run
