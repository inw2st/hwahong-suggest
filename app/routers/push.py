from __future__ import annotations

import base64
import json
import logging
from typing import Any

import requests
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.deps import get_current_admin, require_student_key
from app.models.admin import Admin
from app.models.push import PushSubscription
from app.schemas.push import PushSubscriptionIn, PushSubscriptionOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/push", tags=["push"])


@router.post("/subscribe", response_model=PushSubscriptionOut)
async def subscribe(
    request: Request,
    body: PushSubscriptionIn,
    student_key: str = Depends(require_student_key),
    db: Session = Depends(get_db),
):
    """Save push subscription for a student."""
    logger.info(f"收到订阅请求: {body}")
    logger.info(f"student_key: {student_key}")
    
    try:
        # Remove old subscriptions for this student
        deleted = db.query(PushSubscription).filter(
            PushSubscription.student_key == student_key
        ).delete()
        logger.info(f"删除了 {deleted} 个旧订阅")
        
        # Add new subscription
        sub = PushSubscription(
            student_key=student_key,
            endpoint=body.endpoint,
            p256dh=body.p256dh,
            auth=body.auth,
        )
        db.add(sub)
        db.commit()
        db.refresh(sub)
        logger.info(f"订阅保存成功: id={sub.id}")
        return sub
    except Exception as e:
        logger.error(f"订阅保存失败: {e}")
        db.rollback()
        raise


@router.delete("/unsubscribe")
def unsubscribe(
    student_key: str = Depends(require_student_key),
    db: Session = Depends(get_db),
):
    """Remove push subscription for a student."""
    db.query(PushSubscription).filter(
        PushSubscription.student_key == student_key
    ).delete()
    db.commit()
    return {"ok": True}


@router.post("/admin/subscribe")
def admin_subscribe(
    body: PushSubscriptionIn,
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    """Save push subscription for an admin."""
    logger.info(f"Admin subscription request: {admin.username}")
    
    try:
        # Remove old subscriptions for this admin
        db.query(PushSubscription).filter(
            PushSubscription.admin_id == admin.id
        ).delete()
        
        # Add new subscription
        sub = PushSubscription(
            admin_id=admin.id,
            student_key=None,
            endpoint=body.endpoint,
            p256dh=body.p256dh,
            auth=body.auth,
        )
        db.add(sub)
        db.commit()
        db.refresh(sub)
        logger.info(f"Admin subscription saved: id={sub.id}")
        return {"ok": True, "id": sub.id}
    except Exception as e:
        logger.error(f"Admin subscription failed: {e}")
        db.rollback()
        raise
