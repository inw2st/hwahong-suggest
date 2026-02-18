"""Create or update an admin user.

Usage:
  # 새 관리자 생성
  python scripts/create_admin.py --username admin --password "your-password"
  
  # 기존 관리자 비밀번호 변경
  python scripts/create_admin.py --username admin --password "new-password" --update

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
    parser.add_argument("--username", required=True, help="Admin username")
    parser.add_argument("--password", required=True, help="Admin password")
    parser.add_argument("--update", action="store_true", help="Update existing admin password")
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()
    try:
        admin = db.query(Admin).filter(Admin.username == args.username).first()
        
        if args.update:
            # 업데이트 모드
            if not admin:
                raise SystemExit(f"Admin '{args.username}' not found. Use without --update to create.")
            admin.password_hash = hash_password(args.password)
            db.commit()
            print(f"✓ Updated password for admin: {args.username}")
        else:
            # 생성 모드
            if admin:
                raise SystemExit(f"Admin '{args.username}' already exists. Use --update to change password.")
            admin = Admin(username=args.username, password_hash=hash_password(args.password))
            db.add(admin)
            db.commit()
            print(f"✓ Created admin: {args.username}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
