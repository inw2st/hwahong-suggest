"""Common dependencies (auth, headers, etc.)."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.admin import Admin


bearer_scheme = HTTPBearer(auto_error=False)


def require_student_key(x_student_key: str | None = Header(default=None, alias="X-Student-Key")) -> str:
    if not x_student_key or len(x_student_key) < 10:
        raise HTTPException(status_code=400, detail="Missing X-Student-Key")
    return x_student_key


def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Admin:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = credentials.credentials
    try:
        payload = decode_token(token)
        username = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")

    admin = db.query(Admin).filter(Admin.username == username).first()
    if not admin:
        raise HTTPException(status_code=401, detail="Invalid token")

    return admin
