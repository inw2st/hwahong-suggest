from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.email import is_email_delivery_configured
from app.db.session import get_db, SessionLocal
from app.deps import require_student_key
from app.models.push import PushSubscription
from app.models.suggestion import Suggestion
from app.routers.admin import send_push_notification_to_subscription
from app.schemas.suggestion import SuggestionCreateIn, SuggestionNotificationEmailIn, SuggestionOut, SuggestionUpdateIn


router = APIRouter(prefix="/api", tags=["public"])


@router.get("/health")
def health():
    return {"ok": True}


def _notify_admins(title: str):
    """관리자에게 push 알림 전송 (백그라운드 실행)."""
    db = SessionLocal()
    try:
        admin_subs = db.query(PushSubscription).filter(
            PushSubscription.admin_id.isnot(None)
        ).all()
        for sub in admin_subs:
            send_push_notification_to_subscription(
                sub,
                f"새 건의 등록: {title[:30]}",
                "학생이 새로운 건의사항을 등록했습니다.",
            )
    except Exception as e:
        print(f"Failed to notify admins: {e}")
    finally:
        db.close()


@router.post("/suggestions", response_model=SuggestionOut)
def create_suggestion(
    body: SuggestionCreateIn,
    background_tasks: BackgroundTasks,
    student_key: str = Depends(require_student_key),
    db: Session = Depends(get_db),
):
    s = Suggestion(
        student_key=student_key,
        grade=body.grade,
        title=body.title.strip(),
        content=body.content.strip(),
        status="pending",
    )
    db.add(s)
    db.commit()
    db.refresh(s)

    # push 알림은 응답 후 백그라운드에서 처리
    background_tasks.add_task(_notify_admins, body.title)

    return s


@router.get("/me/suggestions", response_model=list[SuggestionOut])
def list_my_suggestions(
    student_key: str = Depends(require_student_key),
    since_answered_at: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
):
    q = db.query(Suggestion).filter(Suggestion.student_key == student_key)
    if since_answered_at is not None:
        q = q.filter(Suggestion.answered_at.isnot(None)).filter(Suggestion.answered_at > since_answered_at)
    return q.order_by(Suggestion.created_at.desc()).all()


@router.patch("/me/suggestions/{suggestion_id}", response_model=SuggestionOut)
def update_my_suggestion(
    suggestion_id: int,
    body: SuggestionUpdateIn,
    student_key: str = Depends(require_student_key),
    db: Session = Depends(get_db),
):
    s = db.query(Suggestion).filter(Suggestion.id == suggestion_id, Suggestion.student_key == student_key).first()
    if not s:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    if s.status != "pending":
        raise HTTPException(status_code=409, detail="Answered suggestions cannot be edited")

    if body.grade is not None:
        s.grade = body.grade
    if body.title is not None:
        s.title = body.title.strip()
    if body.content is not None:
        s.content = body.content.strip()

    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.patch("/me/suggestions/{suggestion_id}/notification-email", response_model=SuggestionOut)
def set_notification_email(
    suggestion_id: int,
    body: SuggestionNotificationEmailIn,
    student_key: str = Depends(require_student_key),
    db: Session = Depends(get_db),
):
    if not is_email_delivery_configured():
        raise HTTPException(status_code=503, detail="Email notifications are not configured")

    s = db.query(Suggestion).filter(Suggestion.id == suggestion_id, Suggestion.student_key == student_key).first()
    if not s:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    if s.status != "pending":
        raise HTTPException(status_code=409, detail="Answered suggestions cannot be updated")

    s.notification_email = body.email
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.delete("/me/suggestions/{suggestion_id}")
def delete_my_suggestion(
    suggestion_id: int,
    student_key: str = Depends(require_student_key),
    db: Session = Depends(get_db),
):
    s = db.query(Suggestion).filter(Suggestion.id == suggestion_id, Suggestion.student_key == student_key).first()
    if not s:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    if s.status != "pending":
        raise HTTPException(status_code=409, detail="Answered suggestions cannot be deleted")

    db.delete(s)
    db.commit()
    return {"ok": True}
