"""Create an admin user.

Usage:
  python scripts/create_admin.py --username admin --password "your-password"

This script uses the same DATABASE_URL as the app (from .env).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.admin import Admin


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()
    try:
        exists = db.query(Admin).filter(Admin.username == args.username).first()
        if exists:
            raise SystemExit("Admin already exists")
        admin = Admin(username=args.username, password_hash=hash_password(args.password))
        db.add(admin)
        db.commit()
        print("Created admin:", args.username)
    finally:
        db.close()


if __name__ == "__main__":
    main()
