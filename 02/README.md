# FastAPI 기반의 커뮤니티 서버 만들기

> ```과제내용: FastAPI로 커뮤니티 서비스의 백엔드를 구현해보세요```
  
```
- HTTP REST API 설계 및 구현(26.05.18) - 완료

- LLM 연동 기능 추가(26.05.19) - 완료

- 데이터 베이스 적용하기(26.05.20) - 완료

- 구조개선하기(26.05.21) - 완료

- (선택) HTML/CSS/JS나 스트림릿으로 프론트엔드 만들기(26.05.21) - 완료
```


##  프로젝트 개요
FastAPI 기반의 커뮤니티 서비스 REST API 백엔드와 html 기반의 클라이언트 프로젝트

게시글 CRUD, 댓글 CRUD,대댓글, 추천버튼 ,게시글 정렬, AI 모델 서빙을 통한 게시글 요약기능, 악플감지 기능등을 구현 하였습니다.


##  기술 스택

| 구분 | 기술 |
|------|------|
| **프레임워크** | FastAPI |
| **ORM** | SQLAlchemy  |
| **데이터베이스** | SQLite (`community.db`) community.db는 .gitignore입니다. | 
| **데이터 검증** | Pydantic v2 |
| **서버** | Uvicorn (ASGI) |
| **HTTP 클라이언트** | httpx (LLM 서버 통신) |
| **LLM 엔진** | Ollama (로컬 LLM 서빙) model은 `gemma4:e2b` |
| **프론트엔드** | Vanilla HTML/CSS/JS |

---

## 프로젝트 구조

```
02/
├── main.py                  # FastAPI 앱 진입점 (라우터 등록, DB 초기화)
├── database.py              # SQLAlchemy 엔진 및 세션 설정
├── requirements.txt         # Python 의존성 목록
├── community.db             # SQLite 데이터베이스 파일
│
├── api/                     # API 라우터 (엔드포인트 정의)
│   ├── __init__.py
│   ├── posts.py             # 게시글 API (/posts)
│   ├── comments.py          # 댓글 API (/posts/{id}/comments, /comments/{id})
│   └── llm.py               # LLM API (/llm)
│
├── models/                  # SQLAlchemy ORM 모델
│   ├── __init__.py
│   ├── post.py              # Post, PostLike 테이블 정의
│   └── comment.py           # Comment, CommentLike 테이블 정의
│
├── schemas/                 # Pydantic 스키마 (요청/응답 검증)
│   ├── __init__.py
│   ├── post.py              # PostCreate, PostUpdate, PostResponse 등
│   └── comment.py           # CommentCreate, CommentUpdate, CommentResponse 등
│
├── services/                # 비즈니스 로직 계층
│   ├── __init__.py
│   ├── post_service.py      # 게시글 CRUD 로직
│   ├── comment_service.py   # 댓글 CRUD 로직
│   └── llm_service.py       # Ollama LLM 연동 로직
│
├── core/                    # 핵심 설정 및 유틸리티
│   ├── __init__.py
│   ├── config.py            # Ollama URL, 모델명, 카테고리 목록 등 설정값
│   └── security.py          # X-Anonymous-ID 헤더 파싱 (익명 인증)
│
└── client/                  # 프론트엔드 정적 파일
    ├── index.html
    ├── styles.css
    └── app.js
```


## 설치 및 실행

### 1. 가상환경 생성 및 의존성 설치

```bash
cd 02/
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 서버 실행

```bash
# 개발 모드 (자동 리로드)
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 3. API 문서 확인

| 문서 | URL |
|------|-----|
| **Swagger UI** | http://localhost:8000/docs |
| **ReDoc** | http://localhost:8000/redoc |
| **프론트엔드** | http://localhost:8000/client |

---

##  API 설계 및 명세

### 인증 방식

모든 쓰기 요청에는 `X-Anonymous-ID` 헤더가 필요합니다.  
클라이언트에서 생성한 UUID를 전달하여 익명 사용자를 식별합니다.

```
예시) X-Anonymous-ID: 550e8400-e29b-41d4-a716-446655440000
```

---

###  게시글 API (`/posts`)

| Method | Endpoint | 설명 | 인증유무 |
|--------|----------|------|------|
| `POST` | `/posts/` | 게시글 작성 | ✅ |
| `GET` | `/posts/` | 게시글 목록 조회 | ❌ |
| `GET` | `/posts/{post_id}` | 게시글 상세 조회 | ❌ |
| `PUT` | `/posts/{post_id}` | 게시글 수정 | ✅ (본인만) |
| `DELETE` | `/posts/{post_id}` | 게시글 삭제 | ✅ (본인만) |
| `POST` | `/posts/{post_id}/like` | 추천 토글 | ✅ |

#### 게시글 작성 예시

```bash
curl -X POST http://localhost:8000/posts/ \
  -H "Content-Type: application/json" \
  -H "X-Anonymous-ID: my-uuid-1234" \
  -d '{
    "title": "안녕하세요!",
    "content": "첫 게시글입니다.",
    "category": "자유"
  }'
```

#### 응답 예시

```json
{
  "id": 1, 
  "title": "안녕하세요!",
  "content": "첫 게시글입니다.",
  "category": "자유",
  "author_id": "my-uuid-1234",
  "views": 0,
  "likes_count": 0,
  "comments_count": 0,
  "created_at": "2026-05-19T07:00:00",
  "updated_at": "2026-05-19T07:00:00"
}
```

###  댓글 API

| Method | Endpoint | 설명 | 인증유무 |
|--------|----------|------|------|
| `POST` | `/posts/{post_id}/comments` | 댓글 작성 | ✅ |
| `GET` | `/posts/{post_id}/comments` | 댓글 목록 조회 (트리 구조) | ❌ |
| `PUT` | `/comments/{comment_id}` | 댓글 수정 | ✅ (본인만) |
| `DELETE` | `/comments/{comment_id}` | 댓글 삭제 (대댓글 포함) | ✅ (본인만) |
| `POST` | `/comments/{comment_id}/like` | 좋아요 토글 | ✅ |

#### 대댓글 작성 예시

```bash
curl -X POST http://localhost:8000/posts/1/comments \
  -H "Content-Type: application/json" \
  -H "X-Anonymous-ID: my-uuid-1234" \
  -d '{
    "content": "대댓글입니다.",
    "parent_id": 1
  }'
```

#### 댓글 응답 구조 (계층형 트리)

```json
[
  {
    "id": 1,
    "post_id": 1,
    "parent_id": null,
    "content": "첫 번째 댓글",
    "author_id": "user-uuid",
    "likes_count": 3,
    "created_at": "2026-05-19T07:00:00",
    "updated_at": "2026-05-19T07:00:00",
    "replies": [
      {
        "id": 2,
        "post_id": 1,
        "parent_id": 1,
        "content": "대댓글입니다",
        "author_id": "other-uuid",
        "likes_count": 0,
        "replies": []
      }
    ]
  }
]
```

---

### LLM API

| Method | Endpoint | 설명 | 인증 |
|--------|----------|------|------|
| `POST` | `/posts/{post_id}/summarize` | 게시글 AI 요약 (스트리밍) | ❌ |
| `POST` | `/llm/check-toxic` | 악플 감지 | ❌ |

> LLM 기능을 사용하려면 로컬에서 Ollama가 실행 중이어야 합니다.  
> 설치: https://ollama.ai → `ollama serve` → `ollama pull gemma4:e2b`

#### 게시글 요약 응답 (스트리밍)

`/posts/{post_id}/summarize` 엔드포인트는 요약문을 실시간으로 생성하여 청크 단위로 스트리밍 반환(`text/event-stream`)합니다.

```
[스트리밍 텍스트 데이터가 실시간으로 수신됨]
안녕하세요. 본 게시글은 ... 에 대한 내용을 담고 있으며 ...
```

---

##  구현 상세

### 1. 레이어드 아키텍처

| 계층 | 역할 | 파일 |
|------|------|------|
| **API (Router)** | HTTP 요청 수신, 응답 반환, 의존성 주입 | `api/posts.py`, `api/comments.py`, `api/llm.py` |
| **Service** | 비즈니스 로직, 유효성 검사, 에러 처리 | `services/post_service.py`, `comment_service.py`, `llm_service.py` |
| **Model (ORM)** | 데이터베이스 테이블 매핑, 관계 설정 | `models/post.py`, `models/comment.py` |
| **Schema** | 요청/응답 데이터 검증 (Pydantic) | `schemas/post.py`, `schemas/comment.py` |
| **Core** | 설정값, 보안 유틸리티 | `core/config.py`, `core/security.py` |

### 2. 의존성 주입 (Dependency Injection)

```python
# database.py - DB 세션 의존성
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# core/security.py - 익명 사용자 인증 의존성
def get_anonymous_id(x_anonymous_id: str = Header(...)) -> str:
    return x_anonymous_id.strip()
```

FastAPI의 `Depends()`를 활용하여 DB 세션과 사용자 인증을 자동 주입합니다.

### 3. 에러 처리

| HTTP 상태 코드 | 상황 |
|----------------|------|
| `400` | 유효하지 않은 카테고리, 인증 헤더 누락 |
| `403` | 본인이 아닌 게시글/댓글 수정·삭제 시도 |
| `404` | 존재하지 않는 게시글/댓글 접근 |
| `503` | Ollama 서버 연결 불가 |

# 회고
이번 프로젝트는 Python FastAPI를 활용해 커뮤니티 백엔드 서버를 구축하는 것이었다. 본격적인 개발에 앞서 게시판과 댓글에 필요한 핵심 기능들을 정리하여 API 명세를 설계하고, 발생할 수 있는 여러 예외 상황을 시뮬레이션하는 초기 설계 단계의 중요성을 깊이 체감했다.

단순해 보일 수 있는 커뮤니티 기능임에도 총 13개의 API 엔드포인트를 정의하고, 각 엔드포인트에 대응하는 HTTP 메서드(GET, POST, PUT, DELETE)와 비즈니스 로직을 체계적으로 구조화하는 것이 무엇보다 중요함을 깨달았는데 초기 설계를 잘해야 향후 유지보수가 수월해지고, 다른 개발자에게 코드를 설명하거나 협업할 때도 가독성을 극대화할 수 있다.

또한, AI 기반 기능 요구사항을 충족하기 위해 로컬에서 구동되는 Ollama LLM(gemma4:e2b)을 연동하여 게시글 요약 및 댓글 악플 검사 기능을 추가로 구현했는데, 초기에는 요약본 전체를 한 번에 클라이언트로 전달하는 방식으로 구현했으나, 약 10초에 달하는 긴 Latency 문제를 겪었다. 이를 해결하기 위해 모델의 파라미터수를 gemma4:latest에서 gemma4:e2b로 변경하였고 FastAPI의 스트리밍(StreamingResponse) 방식으로 전환하여 청크 단위로 실시간 요약문을 전달받도록 개선했고, 체감되는 요약 완료 시간을 5초 이내로 단축했다. 
클라이언트 단에서도 실시간 로딩 UI와 버튼 비활성화 동작을 구현하여 사용자가 인지하는 대기 시간을 시각적으로도 개선하도록 했다.

댓글 악플 검사 역시 등록 응답이 지연되는 것을 막기 위해 백그라운드 태스크로 처리해 비동기로 검증하고, 검사 완료된 결과를 로컬 DB에 저장하도록 설계했다. 덕분에 서버가 재시작 하더라도 이미 검증된 댓글은 LLM을 다시 호출하지 않고 즉시 조회할 수 있게 되어 리소스 소모를 최소화 하였다. 
단순히 백엔드 API 구현에 그치지 않고 사용성 개선을 위해 UI 화면과 비동기 최적화까지 여러 문제들을 마주쳐가며 고민해보는 시간이였다.
