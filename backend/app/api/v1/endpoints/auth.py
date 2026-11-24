from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import SESSION_COOKIE_NAME, get_current_session, get_current_user
from app.core.config import get_settings
from app.core.security import generate_token, hash_token, verify_password
from app.db.base import utcnow
from app.db.session import get_db
from app.models.entities import User, UserSession
from app.schemas.dto import AuthResponse, LoginRequest, UserOut

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.strip().lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha inválidos.",
        )

    settings = get_settings()
    raw_token = generate_token(32)
    csrf_token = generate_token(24)

    session = UserSession(
        user_id=user.id,
        session_token_hash=hash_token(raw_token),
        csrf_token=csrf_token,
        expires_at=utcnow() + timedelta(hours=settings.session_ttl_hours),
    )
    db.add(session)
    db.commit()

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        samesite="lax",
        secure=settings.app_env == "production",
        max_age=settings.session_ttl_hours * 3600,
        path="/",
    )
    return AuthResponse(user=UserOut.model_validate(user), csrf_token=csrf_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    session.revoked_at = utcnow()
    db.commit()
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


@router.get("/me", response_model=AuthResponse)
def me(
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
):
    return AuthResponse(user=UserOut.model_validate(user), csrf_token=session.csrf_token)
