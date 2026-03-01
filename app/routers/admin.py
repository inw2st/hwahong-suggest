from __future__ import annotations

import base64
import html
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict
from urllib.parse import urlencode

import jwt
import requests
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.email import send_email
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


def _resolve_public_base_url() -> str:
    base_url = settings.PUBLIC_BASE_URL.strip()
    if base_url:
        return base_url.rstrip("/")

    origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]
    if origins:
        return origins[0].rstrip("/")

    return "http://localhost:8000"


def send_answer_email(
    notification_email: str,
    student_key: str,
    suggestion_id: int,
    suggestion_title: str,
    answer: str,
) -> bool:
    public_base_url = _resolve_public_base_url()
    answer_link = public_base_url + "/me.html?" + urlencode({"sk": student_key, "sid": suggestion_id})
    logo_url = public_base_url + "/assets/logo.png"
    safe_title = html.escape(suggestion_title)
    safe_answer = html.escape(answer).replace("\n", "<br />")
    safe_link = html.escape(answer_link)
    safe_logo_url = html.escape(logo_url)
    body = (
        "안녕하세요.\n\n"
        "학생회에서 건의에 답변을 보냈어요.\n\n"
        f"건의 제목: {suggestion_title}\n\n"
        "답변 내용:\n"
        f"{answer}\n\n"
        "답변 확인:\n"
        f"{answer_link}\n\n"
        "위 링크를 열면 바로 '내 건의' 페이지에서 답변을 확인할 수 있습니다."
    )
    html_body = f"""
<!doctype html>
<html lang="ko">
  <body style="margin: 0; padding: 0; background: #f8fafc; color: #0f172a; font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', Arial, sans-serif;">
    <div style="display: none; max-height: 0; overflow: hidden; opacity: 0;">
      학생회에서 건의에 답변을 보냈어요. 버튼을 눌러 바로 확인할 수 있어요.
    </div>
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background: #f8fafc; margin: 0; padding: 24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width: 640px; margin: 0 auto;">
            <tr>
              <td style="padding: 0 16px;">
                <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background: linear-gradient(135deg, #1e3a8a 0%, #1d4ed8 60%, #2563eb 100%); border-radius: 28px 28px 0 0;">
                  <tr>
                    <td style="padding: 28px 28px 24px 28px;">
                      <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                        <tr>
                          <td style="vertical-align: middle;">
                            <img src="{safe_logo_url}" alt="화홍고 로고" width="56" height="56" style="display: block; width: 56px; height: 56px; border-radius: 16px; background: rgba(255,255,255,0.16); padding: 6px;" />
                          </td>
                          <td style="padding-left: 14px; vertical-align: middle; color: #ffffff;">
                            <div style="font-size: 14px; font-weight: 700; opacity: 0.92;">화홍고등학교 학생회</div>
                            <div style="font-size: 26px; font-weight: 800; line-height: 1.25; margin-top: 6px;">건의 답변이 도착했어요</div>
                            <div style="font-size: 14px; line-height: 1.5; color: #dbeafe; margin-top: 8px;">사이트와 같은 톤으로 바로 확인할 수 있게 준비해 두었습니다.</div>
                          </td>
                        </tr>
                      </table>
                    </td>
                  </tr>
                </table>

                <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background: #ffffff; border-radius: 0 0 28px 28px; box-shadow: 0 18px 40px rgba(15, 23, 42, 0.08);">
                  <tr>
                    <td style="padding: 28px;">
                      <div style="font-size: 16px; line-height: 1.7; color: #334155;">
                        안녕하세요.<br />
                        학생회에서 남겨주신 건의에 답변을 보냈습니다.
                      </div>

                      <div style="margin-top: 22px; border-radius: 24px; background: #f8fafc; border: 1px solid #e2e8f0; padding: 20px;">
                        <div style="font-size: 12px; letter-spacing: 0.04em; font-weight: 800; color: #64748b; text-transform: uppercase;">건의 제목</div>
                        <div style="font-size: 22px; line-height: 1.4; font-weight: 800; color: #0f172a; margin-top: 10px;">{safe_title}</div>
                      </div>

                      <div style="margin-top: 18px; border-radius: 24px; background: #eff6ff; border: 1px solid #bfdbfe; padding: 20px;">
                        <div style="font-size: 12px; letter-spacing: 0.04em; font-weight: 800; color: #1d4ed8; text-transform: uppercase;">학생회 답변</div>
                        <div style="font-size: 16px; line-height: 1.8; color: #1e293b; margin-top: 12px;">{safe_answer}</div>
                      </div>

                      <div style="margin-top: 24px;">
                        <a href="{safe_link}" style="display: inline-block; padding: 14px 22px; border-radius: 18px; background: #1d4ed8; color: #ffffff; text-decoration: none; font-size: 15px; font-weight: 800;">
                          답변 확인하러 가기
                        </a>
                      </div>

                      <div style="margin-top: 18px; font-size: 14px; line-height: 1.7; color: #475569;">
                        버튼을 누르면 바로 <strong>내 건의</strong> 페이지로 이동하고, 해당 답변을 강조해서 보여줍니다.
                      </div>

                      <div style="margin-top: 26px; padding-top: 18px; border-top: 1px solid #e2e8f0; font-size: 13px; line-height: 1.8; color: #64748b;">
                        버튼이 열리지 않으면 아래 주소를 복사해 열어 주세요.<br />
                        <a href="{safe_link}" style="color: #1d4ed8; text-decoration: underline; word-break: break-all;">{safe_link}</a>
                      </div>
                    </td>
                  </tr>
                </table>

                <div style="padding: 16px 20px 0 20px; text-align: center; font-size: 12px; line-height: 1.7; color: #94a3b8;">
                  화홍고등학교 학생회 학생 건의함
                </div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
""".strip()
    reply_to = settings.SMTP_REPLY_TO_EMAIL.strip() or settings.SMTP_FROM_EMAIL
    return send_email(
        notification_email,
        "학생회에서 건의에 답변을 보냈어요",
        body,
        html_body=html_body,
        reply_to=reply_to,
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
        if s.notification_email:
            send_answer_email(s.notification_email, s.student_key, s.id, s.title, s.answer or "")
    
    return s


@router.delete("/suggestions/{suggestion_id}", status_code=204)
def admin_delete_suggestion(
    suggestion_id: int,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """건의를 DB에서 완전히 삭제합니다."""
    s = db.query(Suggestion).filter(Suggestion.id == suggestion_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    db.delete(s)
    db.commit()
