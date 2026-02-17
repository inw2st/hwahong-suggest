from __future__ import annotations

import base64
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict

import jwt
import requests
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.deps import get_current_admin
from app.models.admin import Admin
from app.models.push import PushSubscription
from app.models.suggestion import Suggestion
from app.schemas.admin import AdminLoginIn, AdminOut, TokenOut
from app.schemas.suggestion import SuggestionAnswerIn, SuggestionOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _load_vapid_private_key():
    """
    Load VAPID private key from settings.

    지원 포맷:
    - EC PEM 문자열 (-----BEGIN ... 로 시작)
    - URL-safe base64 (web-push, node-web-push 가 출력하는 43/44자짜리 키)
    """
    raw = settings.VAPID_PRIVATE_KEY.strip()
    if not raw:
        raise RuntimeError("VAPID_PRIVATE_KEY is not configured")

    # 1) PEM 포맷인 경우 그대로 파싱
    if raw.startswith("-----BEGIN"):
        return serialization.load_pem_private_key(raw.encode("utf-8"), password=None)

    # 2) URL-safe base64 → 32바이트 시드 → EC 프라이빗 키로 변환
    key_b64 = raw.replace("-", "+").replace("_", "/")
    padding = 4 - len(key_b64) % 4
    if padding != 4:
        key_b64 += "=" * padding
    seed = base64.b64decode(key_b64)

    if len(seed) != 32:
        # SECP256R1 에 맞는 32바이트 키가 아니면 명확히 에러를 던진다
        raise ValueError("VAPID private key must be 32 bytes when given as base64")

    # RFC8292 (VAPID) 는 P-256(SECP256R1)을 사용
    return ec.derive_private_key(int.from_bytes(seed, "big"), ec.SECP256R1())


def _create_vapid_jwt(endpoint: str) -> tuple[str, str]:
    """Create VAPID JWT for push authentication."""
    # cryptography EC 키 객체로 생성 (PEM / base64 모두 지원)
    private_key = _load_vapid_private_key()

    # Get audience from endpoint (scheme://host)
    # endpoint: https://fcm.googleapis.com/fcm/send/xxx
    # aud: https://fcm.googleapis.com
    from urllib.parse import urlparse
    parsed = urlparse(endpoint)
    aud = f"{parsed.scheme}://{parsed.netloc}"

    # Create JWT (12시간 유효)
    now = int(time.time())
    payload = {
        "aud": aud,
        "exp": now + 12 * 3600,
        "sub": "mailto:admin@school.local",
    }

    token = jwt.encode(payload, private_key, algorithm="ES256")
    return token, settings.VAPID_PUBLIC_KEY


def send_push_notification_to_subscription(sub: PushSubscription, title: str, body: str) -> bool:
    """Send a single push notification to a subscription."""
    if not settings.VAPID_PRIVATE_KEY or not settings.VAPID_PUBLIC_KEY:
        logger.warning("VAPID keys not configured, skipping push")
        return False
    
    try:
        # Create VAPID JWT
        vapid_token, vapid_key = _create_vapid_jwt(sub.endpoint)
        
        # Prepare push message
        message = json.dumps({
            "title": title,
            "body": body,
            "icon": "/assets/icon.png",
            "tag": f"suggestion-{sub.id}"
        })
        
        # Send push
        response = requests.post(
            sub.endpoint,
            data=message,
            headers={
                "Content-Type": "application/json",
                "TTL": "86400",
                "Authorization": f"vapid t={vapid_token}, k={vapid_key}"
            },
            timeout=10
        )
        
        if response.status_code in (200, 201, 202):
            logger.info(f"Push sent to {sub.endpoint[:50]}...")
            return True
        else:
            logger.warning(f"Push failed: {response.status_code} - {response.text[:100]}")
            return False
            
    except Exception as e:
        logger.error(f"Push error: {e}")
        return False


def send_push_notifications(student_key: str, suggestion_title: str):
    """Send push notifications to all subscriptions for a student."""
    if not settings.VAPID_PRIVATE_KEY or not settings.VAPID_PUBLIC_KEY:
        logger.warning("VAPID keys not configured, skipping push")
        return
    
    subscriptions = None
    try:
        from app.db.session import SessionLocal
        db = SessionLocal()
        try:
            subscriptions = db.query(PushSubscription).filter(
                PushSubscription.student_key == student_key
            ).all()
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to get subscriptions: {e}")
        return
    
    if not subscriptions:
        logger.warning("No subscriptions found")
        return
    
    for sub in subscriptions:
        send_push_notification_to_subscription(
            sub,
            "새 답변이 도착했어요",
            suggestion_title
        )


@router.post("/login", response_model=TokenOut)
def admin_login(body: AdminLoginIn, db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.username == body.username).first()
    if not admin or not verify_password(body.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    admin.last_login_at = datetime.now(timezone.utc)
    db.add(admin)
    db.commit()

    token = create_access_token(subject=admin.username)
    return TokenOut(access_token=token)


@router.get("/me", response_model=AdminOut)
def admin_me(current_admin: Admin = Depends(get_current_admin)):
    return current_admin


@router.get("/suggestions", response_model=list[SuggestionOut])
def admin_list_suggestions(
    grade: int | None = Query(default=None, ge=1, le=3),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=80),
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    query = db.query(Suggestion)
    if grade is not None:
        query = query.filter(Suggestion.grade == grade)
    if status in {"pending", "answered"}:
        query = query.filter(Suggestion.status == status)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter((Suggestion.title.ilike(like)) | (Suggestion.content.ilike(like)))
    return query.order_by(Suggestion.created_at.desc()).all()


@router.patch("/suggestions/{suggestion_id}/answer", response_model=SuggestionOut)
def admin_answer_suggestion(
    suggestion_id: int,
    body: SuggestionAnswerIn,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    s = db.query(Suggestion).filter(Suggestion.id == suggestion_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    old_status = s.status
    s.answer = body.answer.strip()
    s.status = "answered"
    s.answered_at = datetime.now(timezone.utc)

    db.add(s)
    db.commit()
    db.refresh(s)
    
    # Send push notification if this is a new answer
    if old_status != "answered":
        send_push_notifications(s.student_key, s.title)
    
    return s
