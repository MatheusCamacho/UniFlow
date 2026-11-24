from datetime import timezone
from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.security import hash_token
from app.db.base import utcnow
from app.db.session import get_db
from app.models.entities import User, UserSession

SESSION_COOKIE_NAME = "uniflow_session"


def get_current_session(
    request: Request,
    uniflow_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    db: Session = Depends(get_db),
) -> UserSession:
    if not uniflow_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado.")

    token_hash = hash_token(uniflow_session)
    session = (
        db.query(UserSession)
        .filter(
            UserSession.session_token_hash == token_hash,
            UserSession.revoked_at.is_(None),
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão inválida.")

    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão expirada.")

    # Valida proteção CSRF em métodos de escrita
    if request.method in ("POST", "PATCH", "PUT", "DELETE"):
        if not x_csrf_token or x_csrf_token != session.csrf_token:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token CSRF inválido.")

    return session


def get_current_user(session: UserSession = Depends(get_current_session)) -> User:
    if not session.user or not session.user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário inativo.")
    return session.user
