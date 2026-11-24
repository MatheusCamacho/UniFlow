from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.entities import Subject, User
from app.schemas.dto import SubjectCreate, SubjectOut, SubjectUpdate

router = APIRouter(prefix="/subjects", tags=["Disciplinas"])


@router.get("", response_model=list[SubjectOut])
def list_subjects(
    include_archived: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Subject).filter(Subject.user_id == user.id)
    if not include_archived:
        q = q.filter(Subject.is_archived.is_(False))
    return q.order_by(Subject.name.asc()).all()


@router.post("", response_model=SubjectOut, status_code=status.HTTP_201_CREATED)
def create_subject(
    payload: SubjectCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subject = Subject(user_id=user.id, **payload.model_dump())
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return subject


@router.patch("/{subject_id}", response_model=SubjectOut)
def update_subject(
    subject_id: str,
    payload: SubjectUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subject = db.query(Subject).filter(Subject.id == subject_id, Subject.user_id == user.id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Disciplina não encontrada.")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(subject, field, value)
    db.commit()
    db.refresh(subject)
    return subject


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_subject(
    subject_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subject = db.query(Subject).filter(Subject.id == subject_id, Subject.user_id == user.id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Disciplina não encontrada.")
    subject.is_archived = True
    db.commit()
