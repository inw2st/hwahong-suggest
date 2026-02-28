# School Suggestions - 학교 건의사항 웹사이트

화홍고 학생회 건의함 서비스입니다.
학생은 익명으로 건의를 등록하고, 관리자는 관리자 콘솔에서 건의를 조회/답변할 수 있습니다.

## 기술 스택

- Backend: FastAPI, SQLAlchemy 2.x, Pydantic v2
- Database: PostgreSQL (`psycopg2-binary`)
- Auth: JWT + bcrypt
- Frontend: 정적 HTML/CSS/Vanilla JS (Tailwind CDN)
- Notification: Web Push (VAPID)
- Optional email notifications: SMTP
- Infra: Nginx + systemd (배포 스크립트 제공)

## 핵심 기능

### 학생
- 건의 등록 (`학년 1~3`, 제목, 내용)
- 내 건의 목록 조회
- 답변 전 건의 수정/삭제
- 답변 도착 시 브라우저 푸시 알림 구독

### 관리자
- 관리자 로그인 (JWT 발급)
- 건의 목록 조회 (학년/상태/검색 필터)
- 건의 답변 작성/수정
- 건의 완전 삭제
- 새 건의 등록 시 관리자 푸시 알림 수신

## 프로젝트 구조

```text
.
├── app/
│   ├── core/
│   │   ├── config.py         # 환경 변수 설정
│   │   └── security.py       # 비밀번호 해시/JWT
│   ├── db/
│   │   ├── base.py           # SQLAlchemy Base
│   │   └── session.py        # DB 엔진/세션
│   ├── models/
│   │   ├── admin.py
│   │   ├── suggestion.py
│   │   └── push.py
│   ├── routers/
│   │   ├── public.py         # 학생 API
│   │   ├── admin.py          # 관리자 API
│   │   └── push.py           # 푸시 구독 API
│   ├── schemas/
│   │   ├── admin.py
│   │   ├── suggestion.py
│   │   └── push.py
│   ├── deps.py
│   └── main.py               # FastAPI 앱 + 정적 파일 라우팅
├── public/
│   ├── assets/
│   ├── admin/
│   │   ├── login.html
│   │   └── index.html
│   ├── index.html
│   ├── me.html
│   └── sw.js
├── scripts/
│   └── create_admin.py       # 관리자 생성/비밀번호 갱신
├── deploy/
│   ├── setup.sh              # Ubuntu 서버 초기 배포 스크립트
│   ├── nginx.conf
│   └── suggesting.service
├── requirements.txt
└── .env.example
```

## 환경 변수

`.env.example` 기준:

```env
DATABASE_URL=postgresql://user:password@db-host:5432/suggestions
JWT_SECRET_KEY=change-me-to-a-long-random-string
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=720
CORS_ORIGINS=https://your-domain.com
VAPID_PUBLIC_KEY=
VAPID_PRIVATE_KEY=
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
SMTP_FROM_NAME=화홍고 학생회 건의함
SMTP_USE_TLS=true
SMTP_USE_SSL=false
AUTO_CREATE_TABLES=true
```

설명:
- `DATABASE_URL`: PostgreSQL 연결 문자열
- `JWT_SECRET_KEY`: JWT 서명 키
- `CORS_ORIGINS`: 허용할 Origin(쉼표로 다중 지정)
- `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`: Web Push 전송용 키
- `SMTP_*`: 답변 이메일 알림 전송용 SMTP 설정
- `AUTO_CREATE_TABLES`: 앱 시작 시 테이블 자동 생성 여부

## 데이터 모델

### `suggestions`
- `id` (PK)
- `student_key` (익명 식별 키)
- `grade` (1~3)
- `title`, `content`
- `status` (`pending` | `answered`)
- `answer`, `answered_at`
- `notification_email` (선택 입력)
- `created_at`, `updated_at`

### `admins`
- `id` (PK)
- `username` (unique)
- `password_hash`
- `created_at`, `last_login_at`

### `push_subscriptions`
- `id` (PK)
- `student_key` 또는 `admin_id`
- `endpoint`, `p256dh`, `auth`
- `created_at`

## API 요약

### Public (`/api`)
- `GET /health`
- `POST /suggestions`
- `GET /me/suggestions`
- `PATCH /me/suggestions/{suggestion_id}`
- `PATCH /me/suggestions/{suggestion_id}/notification-email`
- `DELETE /me/suggestions/{suggestion_id}`

학생 API는 `X-Student-Key` 헤더를 사용합니다.

### Admin (`/api/admin`)
- `POST /login`
- `GET /me`
- `GET /suggestions`
- `PATCH /suggestions/{suggestion_id}/answer`
- `DELETE /suggestions/{suggestion_id}`

관리자 API는 `Authorization: Bearer <token>` 헤더를 사용합니다.

### Push (`/api/push`)
- `POST /subscribe`
- `DELETE /unsubscribe`
- `POST /admin/subscribe`

## 배포

`deploy/setup.sh`를 기준으로 Ubuntu 서버에 다음 구성을 자동화합니다.

- PostgreSQL 설치 및 DB/유저 생성
- Python 가상환경 및 의존성 설치
- Nginx 설정 적용 (`deploy/nginx.conf`)
- systemd 서비스 등록 (`deploy/suggesting.service`)

배포 후 관리자 계정은 아래 스크립트로 생성/갱신합니다.

```bash
python scripts/create_admin.py --username admin --password "strong-password"
python scripts/create_admin.py --username admin --password "new-password" --update
```

## 보안 및 운영 메모

- 비밀번호는 bcrypt 해시로 저장됩니다.
- JWT 만료 시간 기본값은 720분입니다.
- `CORS_ORIGINS`를 실제 서비스 도메인으로 제한하세요.
- VAPID 키가 없으면 푸시 전송은 자동으로 건너뜁니다.
