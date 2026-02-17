# School Suggestions - 학교 건의사항 웹사이트

FastAPI + MySQL 기반 학교 건의사항 웹사이트입니다. 학생들은 익명으로 건의를 작성하고, 관리자가 답변을 등록할 수 있습니다.

## 프로젝트 구조

```
suggesting-new/
├── api/
│   └── index.py          # Vercel serverless entrypoint
├── app/
│   ├── core/
│   │   ├── config.py     # 환경설정 (Settings)
│   │   └── security.py   # JWT, bcrypt 해시
│   ├── db/
│   │   ├── base.py       # SQLAlchemy Base
│   │   └── session.py    # DB 세션 관리
│   ├── models/
│   │   ├── admin.py      # 관리자 모델
│   │   └── suggestion.py # 건의사항 모델
│   ├── routers/
│   │   ├── admin.py      # 관리자 API
│   │   └── public.py     # 학생/공개 API
│   ├── schemas/
│   │   ├── admin.py      # 관리자 Pydantic 스키마
│   │   └── suggestion.py # 건의사항 Pydantic 스키마
│   ├── deps.py           # 의존성 주입 (JWT 검증)
│   └── main.py           # FastAPI 앱
├── public/
│   ├── assets/
│   │   ├── app.js        # 공통 JS 유틸
│   │   └── theme.css     # 글로벌 스타일
│   ├── admin/
│   │   ├── index.html    # 관리자 대시보드
│   │   └── login.html    # 관리자 로그인
│   ├── index.html        # 학생 건의 작성
│   └── me.html           # 내 건의 확인
├── scripts/
│   └── create_admin.py   # 관리자 계정 생성 스크립트
├── .env.example          # 환경설정 예시
├── requirements.txt      # Python 의존성
└── vercel.json           # Vercel 배포 설정
```

## DB 설계

### suggestions 테이블
| 필드 | 타입 | 설명 |
|------|------|------|
| id | INT (PK) | 자동 증가 |
| student_key | VARCHAR(64) | 학생 식별용 UUID |
| grade | INT |学年 (1-6) |
| title | VARCHAR(140) | 제목 |
| content | TEXT | 내용 |
| status | ENUM('pending','answered') | 상태 |
| answer | TEXT | 답변 내용 |
| answered_at | DATETIME | 답변 일시 |
| created_at | DATETIME | 생성 일시 |
| updated_at | DATETIME | 수정 일시 |

### admins 테이블
| 필드 | 타입 | 설명 |
|------|------|------|
| id | INT (PK) | 자동 증가 |
| username | VARCHAR(64) | 로그인 아이디 |
| password_hash | VARCHAR(255) | bcrypt 해시 |
| created_at | DATETIME | 생성 일시 |
| last_login_at | DATETIME | 마지막 로그인 |

## 로컬 실행 방법

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. MySQL 데이터베이스 생성
```bash
mysql -u root -p
CREATE DATABASE suggestions CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 3. 환경설정 (.env 생성)
```bash
cp .env.example .env
# .env 파일을 열어 DATABASE_URL, JWT_SECRET_KEY 등을 수정하세요.
```

예시 (.env):
```env
DATABASE_URL=mysql+pymysql://root:your_password@127.0.0.1:3306/suggestions?charset=utf8mb4
JWT_SECRET_KEY=super-secret-key-change-this
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=720
CORS_ORIGINS=http://localhost:3000
AUTO_CREATE_TABLES=true
```

### 4. 관리자 계정 생성
```bash
python scripts/create_admin.py --username admin --password "your_password"
```

### 5. 서버 실행 (2개 터미널 필요)

**터미널 1 - Backend (FastAPI):**
```bash
uvicorn app.main:app --reload --port 8000
```

**터미널 2 - Frontend (정적 파일 서빙):**
```bash
# Python 내장 서버 사용
cd public
python -m http.server 3000
```

### 6. 브라우저에서 확인
- 학생 화면: http://localhost:3000
- 내 건의: http://localhost:3000/me.html
- 관리자: http://localhost:3000/admin/login.html

## Vercel 배포

### 사전 준비
1. MySQL 데이터베이스 호스팅 (예: Railway, PlanetScale, Cloudflare D1)
2. Vercel 계정

### 배포 단계

1. **데이터베이스 URL 설정**
   - `.env` 파일의 `DATABASE_URL`을 배포용 DB로 변경

2. **Vercel CLI 설치 및 로그인**
   ```bash
   npm i -g vercel
   vercel login
   ```

3. **환경변수 설정**
   - Vercel 대시보드 → Project → Settings → Environment Variables
   - 아래 변수들을 추가:
     - `DATABASE_URL`: MySQL 연결 문자열
     - `JWT_SECRET_KEY`: 랜덤 문자열
     - `CORS_ORIGINS`: 배포 도메인 (예: `https://your-project.vercel.app`)

4. **배포 실행**
   ```bash
   vercel --prod
   ```

### Vercel 설정 (vercel.json)
```json
{
  "version": 2,
  "builds": [
    {"src": "api/index.py", "use": "@vercel/python"},
    {"src": "public/**", "use": "@vercel/static"}
  ],
  "routes": [
    {"src": "/api/(.*)", "dest": "api/index.py"},
    {"handle": "filesystem"},
    {"src": "/(.*)", "dest": "/public/$1"}
  ]
}
```

## 기능 설명

### 학생 기능
1. **건의 작성**: 학년 선택 후 제목/내용 입력
2. **내 건의 확인**: localStorage에 저장된 student_key로 조회
3. **수정/삭제**: 답변 전(대기중) 상태에서만 가능

### 관리자 기능
1. **JWT 로그인**: 안전한 인증
2. **건의 목록**: 학년/상태 필터, 검색
3. **답변 작성**: textarea로 답변 입력, 저장 시 자동 상태 변경

### 알림 기능
- Notification API 사용
- 15초 간격으로 polling
- 새 답변이 달리면 브라우저 알림 표시

## 보안

- 비밀번호: bcrypt 해시 저장
- JWT: HS256 서명, 720분(12시간) 만료
- CORS: 설정된 도메인만 허용
- 입력 검증: Pydantic 사용
