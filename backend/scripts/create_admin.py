"""
Script administrativo para provisionar a conta pessoal do UniFlow.
Uso:
    python scripts/create_admin.py --seed
"""
import argparse
from datetime import timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.base import Base, utcnow
from app.db.session import SessionLocal, engine
from app.models.entities import CalendarEvent, Subject, Task, User


def main():
    parser = argparse.ArgumentParser(description="Cria a conta inicial do UniFlow.")
    parser.add_argument("--seed", action="store_true", help="Popula disciplinas, tarefas e eventos de exemplo.")
    args = parser.parse_args()

    settings = get_settings()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        email = settings.admin_email.strip().lower()
        password = settings.admin_password
        name = settings.admin_name

        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                email=email,
                display_name=name,
                password_hash=hash_password(password),
                timezone=settings.default_timezone,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"[OK] Usuário inicial criado: {email}")
        else:
            print(f"[INFO] Usuário já existe: {email}")

        if args.seed and db.query(Subject).filter(Subject.user_id == user.id).count() == 0:
            now = utcnow()
            s1 = Subject(
                user_id=user.id,
                name="Automação e Programabilidade em Redes",
                code="APR-2026",
                professor="Prof. Me. Wagner Loch",
                term="2026/2",
                color="#365D73",
            )
            s2 = Subject(
                user_id=user.id,
                name="Programação Full Stack",
                code="PFS-2026",
                professor="Coordenação ADS",
                term="2026/2",
                color="#52745D",
            )
            s3 = Subject(
                user_id=user.id,
                name="Banco de Dados II",
                code="BD2-2026",
                professor="Docente de Dados",
                term="2026/2",
                color="#8A6B42",
            )
            db.add_all([s1, s2, s3])
            db.flush()

            tasks = [
                Task(
                    user_id=user.id,
                    subject_id=s1.id,
                    title="Preparar Live Demo do UniFlow (5 minutos)",
                    description="Validar sincronização Google Calendar, importação .ics e simulação de erro HTTP 503.",
                    priority="urgent",
                    status="in_progress",
                    due_at=now + timedelta(hours=18),
                    estimated_minutes=90,
                    sync_due_to_google=True,
                ),
                Task(
                    user_id=user.id,
                    subject_id=s2.id,
                    title="Revisar cobertura de testes da API REST",
                    description="Garantir testes passando no pytest antes de publicar no GitHub.",
                    priority="high",
                    status="pending",
                    due_at=now + timedelta(days=3),
                    estimated_minutes=120,
                    sync_due_to_google=False,
                ),
                Task(
                    user_id=user.id,
                    subject_id=s3.id,
                    title="Entregar lista de modelagem relacional",
                    description="Revisar índices compostos e integridade referencial.",
                    priority="normal",
                    status="pending",
                    due_at=now - timedelta(hours=5),
                    estimated_minutes=60,
                    sync_due_to_google=False,
                ),
            ]
            db.add_all(tasks)

            events = [
                CalendarEvent(
                    user_id=user.id,
                    subject_id=s1.id,
                    title="Aula — Automação e Programabilidade em Redes",
                    location="Campus Pelotas — Lab 302",
                    event_type="class",
                    all_day=False,
                    start_at=now + timedelta(hours=1),
                    end_at=now + timedelta(hours=3),
                    origin="uniflow",
                    sync_to_google=True,
                ),
                CalendarEvent(
                    user_id=user.id,
                    subject_id=s2.id,
                    title="Entrega do Projeto Integrador",
                    event_type="exam",
                    all_day=False,
                    start_at=now + timedelta(days=5),
                    end_at=now + timedelta(days=5, hours=2),
                    origin="uniflow",
                    sync_to_google=True,
                ),
            ]
            db.add_all(events)
            db.commit()
            print("[OK] Dados acadêmicos de demonstração inseridos.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
