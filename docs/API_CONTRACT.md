# OURVERSE 3.0 프론트엔드·백엔드 API 계약

- WBS: 1.2.2
- 작성일: 2026-11-24
- 담당: 이효재(김해인 대행)
- 기능 갱신: WBS 2.2.5 개인별 비공개 조건 API
- WBS 원담당: 김해인 / 실제 구현: 이효재(대행)
- 코드 기준: `main`의 `01eb9e2`에서 분기한 `feature/p0-private-conditions-20261124`
- 확인 파일: `main.py`, `schemas.py`, `auth.py`, `models.py`, `frontend/app.js`, `frontend/index.html`

이 문서는 현재 FastAPI 코드에 실제 구현된 계약을 기준으로 한다. `planned` 항목은 아직 endpoint, request schema, response schema가 없으며 프론트엔드에서 호출하면 안 된다.

## 1. 공통 인증 방식

### 기본 호출 방식

- 현재 API에는 `/api` prefix가 없다. 예: `/users`, `/decisions`.
- 현재 웹은 FastAPI가 `/app`과 `/static`을 같은 origin에서 제공하며 상대 경로로 API를 호출한다.
- JSON 요청은 `Content-Type: application/json`을 사용한다.
- 로그인만 `Content-Type: application/x-www-form-urlencoded`를 사용한다.
- 별도 CORS middleware가 없으므로 다른 origin의 프론트 개발 서버에서 직접 호출하는 계약은 현재 지원하지 않는다. 같은 origin 또는 개발 proxy를 사용해야 한다.

### Bearer 인증

로그인 성공 후 받은 JWT를 인증이 필요한 모든 요청에 다음과 같이 보낸다.

```http
Authorization: Bearer <access_token>
```

- 토큰 subject는 사용자 ID 문자열이다.
- 토큰 만료 시간은 발급 후 60분이다.
- 로그아웃된 토큰의 SHA-256 해시가 서버에 저장되며 이후 요청은 거부된다.
- 인증 헤더 없음, 잘못된 토큰, 만료 토큰, 존재하지 않는 사용자 토큰은 401이다.
- 폐기된 토큰은 401과 `Token has been revoked`를 반환한다.

### 공통 오류 형식

애플리케이션에서 명시적으로 발생시키는 오류는 다음 형태다.

```json
{
  "detail": "User does not belong to a couple"
}
```

요청 Body 누락, 필드 누락, 잘못된 path parameter 타입 등 FastAPI validation 오류는 422이며 `detail`이 문자열이 아니라 배열이다.

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "title"],
      "msg": "Field required",
      "input": {}
    }
  ]
}
```

## 2. 인증 API

| Method | Path | Auth | Request | Success | 주요 Error |
|---|---|---|---|---|---|
| POST | `/users` | No | JSON `UserCreate` | 201 `UserRead` | 409 이메일 중복, 422 validation |
| POST | `/token` | No | Form `username`, `password` | 200 `Token` | 401 인증 실패, 422 validation |
| GET | `/users/me` | Bearer | 없음 | 200 `UserRead` | 401 인증 실패·폐기 토큰 |
| POST | `/logout` | Bearer | 없음 | 200 message | 401 인증 실패·이미 폐기된 토큰 |

### 2.1 회원가입 — `POST /users`

요청:

```json
{
  "email": "user-a@example.com",
  "nickname": "사용자A",
  "password": "password123"
}
```

201 응답:

```json
{
  "id": 1,
  "email": "user-a@example.com",
  "nickname": "사용자A",
  "couple_id": null
}
```

주요 오류:

- 409 `Email already registered`
- 422 필수 필드 누락 또는 타입 오류

현재 백엔드 `UserCreate`는 세 필드를 모두 단순 문자열로 받으며 이메일 형식, 비밀번호 최소 길이, 빈 문자열을 검증하지 않는다. 프론트 HTML의 `type="email"`, `minlength="8"`, `required`는 브라우저 검증일 뿐 백엔드 계약 제약은 아니다.

### 2.2 로그인 — `POST /token`

요청 형식은 JSON이 아니라 form-urlencoded다. 이메일을 `username` 필드에 넣는다.

```http
Content-Type: application/x-www-form-urlencoded

username=user-a%40example.com&password=password123
```

필수 필드:

- `username`: 가입 이메일
- `password`: 비밀번호

OAuth2 form의 `grant_type`, `scope`, `client_id`, `client_secret`도 schema에 존재하지만 현재 프론트는 보내지 않으며 로그인 처리에 사용하지 않는다.

200 응답:

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

주요 오류:

- 401 `Incorrect email or password`
- 422 `username` 또는 `password` 누락

### 2.3 현재 사용자 — `GET /users/me`

200 응답:

```json
{
  "id": 1,
  "email": "user-a@example.com",
  "nickname": "사용자A",
  "couple_id": 10
}
```

커플에 가입하지 않은 사용자는 정상 사용자이므로 200이며 `couple_id`가 `null`이다.

### 2.4 로그아웃 — `POST /logout`

200 응답:

```json
{
  "message": "Successfully logged out"
}
```

성공 시 현재 JWT가 폐기된다. 같은 토큰을 다시 사용하면 인증 단계에서 401 `Token has been revoked`가 발생한다. 현재 프론트는 서버 로그아웃 성공 여부와 관계없이 `sessionStorage`의 토큰을 제거한다.

## 3. 커플 API

| Method | Path | Auth | Request | Success | 주요 Error |
|---|---|---|---|---|---|
| POST | `/couples` | Bearer | 없음 | 201 `CoupleRead` | 401 인증 실패, 409 이미 커플 가입 |
| POST | `/couples/join` | Bearer | JSON `CoupleJoin` | 200 `CoupleRead` | 401, 404 코드 없음, 409 이미 가입·정원 초과, 422 |
| GET | `/couples/me` | Bearer | 없음 | 200 `CoupleRead` | 401, 404 커플 미가입·커플 없음 |

### 3.1 초대 코드 생성 — `POST /couples`

Body 없이 호출한다. 로그인 사용자가 속할 새 Couple을 만들고 해당 사용자를 첫 구성원으로 연결한다.

201 응답:

```json
{
  "id": 10,
  "invite_code": "A1B2C3D4",
  "members": [
    {
      "id": 1,
      "email": "user-a@example.com",
      "nickname": "사용자A",
      "couple_id": 10
    }
  ]
}
```

- 초대 코드는 서버가 생성하는 대문자 8자리 hexadecimal 문자열이다.
- 이미 `couple_id`가 있는 사용자는 409 `User already belongs to a couple`이다.

### 3.2 초대 코드 참여 — `POST /couples/join`

요청:

```json
{
  "invite_code": "A1B2C3D4"
}
```

200 응답:

```json
{
  "id": 10,
  "invite_code": "A1B2C3D4",
  "members": [
    {
      "id": 1,
      "email": "user-a@example.com",
      "nickname": "사용자A",
      "couple_id": 10
    },
    {
      "id": 2,
      "email": "user-b@example.com",
      "nickname": "사용자B",
      "couple_id": 10
    }
  ]
}
```

주요 오류:

- 404 `Invite code not found`
- 409 `User already belongs to a couple`
- 409 `Couple already has two members`
- 422 `invite_code` 누락

서버는 입력 코드를 대문자로 바꾸지만 공백을 제거하지 않는다. 현재 프론트는 호출 전에 `trim().toUpperCase()`를 적용한다.

### 3.3 현재 커플 조회 — `GET /couples/me`

응답 schema는 `CoupleRead`이며 구성원별 `id`, `email`, `nickname`, `couple_id`를 포함한다.

주요 오류:

- 404 `User does not belong to a couple`: 로그인 사용자의 `couple_id`가 null
- 404 `Couple not found`: 사용자의 `couple_id`가 가리키는 Couple 행이 없음

커플 미가입은 인증 실패가 아니므로 401이 아니라 404다. 현재 프론트는 이 404를 정상적인 “연결 전” 상태로 처리한다.

## 4. 공동결정 API

| Method | Path | Auth | Request | Success | 주요 Error |
|---|---|---|---|---|---|
| POST | `/decisions` | Bearer | JSON `DecisionCreate` | 201 `DecisionRead` | 401, 409 커플 미가입, 422 |
| GET | `/decisions` | Bearer | 없음 | 200 `DecisionRead[]` | 401, 409 커플 미가입 |
| GET | `/decisions/{decision_id}` | Bearer | path integer | 200 `DecisionDetailRead` | 401, 403 타 커플, 404 없음, 409 커플 미가입, 422 |
| PUT | `/decisions/{decision_id}/conditions/me` | Bearer | JSON `DecisionConditionUpsert` | 200 `DecisionConditionRead` | 401, 403, 404, 409, 422 |
| GET | `/decisions/{decision_id}/conditions/me` | Bearer | 없음 | 200 `DecisionConditionRead` | 401, 403, 404, 409, 422 |
| GET | `/decisions/{decision_id}/conditions/status` | Bearer | 없음 | 200 `DecisionConditionStatusRead` | 401, 403, 404, 409, 422 |

### 4.1 Decision 생성 — `POST /decisions`

요청:

```json
{
  "title": "오늘 저녁 메뉴"
}
```

201 응답:

```json
{
  "id": 100,
  "couple_id": 10,
  "created_by_id": 1,
  "title": "오늘 저녁 메뉴",
  "status": "open"
}
```

- `couple_id`와 `created_by_id`는 클라이언트가 보내지 않는다.
- 서버가 인증 사용자에서 두 값을 결정한다.
- 커플 미가입 사용자는 409 `User does not belong to a couple`이다.
- 현재 schema는 빈 `title`을 별도로 차단하지 않는다.

### 4.2 Decision 목록 — `GET /decisions`

200 응답:

```json
[
  {
    "id": 101,
    "couple_id": 10,
    "created_by_id": 2,
    "title": "주말 데이트",
    "status": "confirmed"
  },
  {
    "id": 100,
    "couple_id": 10,
    "created_by_id": 1,
    "title": "오늘 저녁 메뉴",
    "status": "open"
  }
]
```

- 현재 로그인 사용자의 `couple_id`에 속한 Decision만 반환한다.
- `id` 내림차순으로 반환한다.
- 목록에는 `current_candidate`, 승인 수, 구성원별 승인 상태가 포함되지 않는다.
- 커플 미가입 사용자는 409다.

### 4.3 Decision 상세 — `GET /decisions/{decision_id}`

current 후보가 없을 때:

```json
{
  "id": 100,
  "couple_id": 10,
  "created_by_id": 1,
  "title": "오늘 저녁 메뉴",
  "status": "open",
  "current_candidate": null,
  "confirmed": false
}
```

current 후보와 한 명의 승인이 있을 때:

```json
{
  "id": 100,
  "couple_id": 10,
  "created_by_id": 1,
  "title": "오늘 저녁 메뉴",
  "status": "open",
  "current_candidate": {
    "id": 501,
    "decision_id": 100,
    "content": "초밥",
    "version": 2,
    "is_current": true,
    "approval_count": 1,
    "member_approvals": [
      {
        "user_id": 1,
        "approved": true
      },
      {
        "user_id": 2,
        "approved": false
      }
    ]
  },
  "confirmed": false
}
```

양측 승인 후에는 `status`가 `confirmed`, `confirmed`가 `true`, `approval_count`가 2가 된다.

주요 오류:

- 404 `Decision not found`
- 403 `You cannot access this decision`
- 409 `User does not belong to a couple`
- 422 `decision_id`가 integer가 아님

상세 API는 current 후보만 반환하며 과거 후보 목록을 반환하지 않는다.

### 4.4 개인별 비공개 조건

#### 내 조건 저장·수정 — `PUT /decisions/{decision_id}/conditions/me`

요청:

```json
{
  "max_budget": 50000,
  "available_time": "토요일 18:00~21:00",
  "preferences": "조용한 좌석, 한식 선호",
  "avoidances": "대기 30분 이상, 매운 음식"
}
```

200 응답:

```json
{
  "max_budget": 50000,
  "available_time": "토요일 18:00~21:00",
  "preferences": "조용한 좌석, 한식 선호",
  "avoidances": "대기 30분 이상, 매운 음식",
  "id": 1,
  "decision_id": 100,
  "user_id": 1,
  "created_at": "2026-11-24T12:00:00Z",
  "updated_at": "2026-11-24T12:00:00Z"
}
```

- `max_budget`는 0 이상 1,000,000,000 이하의 정수다.
- `available_time`은 공백 제거 후 1~200자다.
- `preferences`, `avoidances`는 각각 최대 1,000자이며 빈 문자열을 허용한다.
- 같은 사용자가 같은 Decision에 다시 PUT하면 기존 행을 수정한다.
- `user_id`, `couple_id`, `decision_id`는 Body로 받지 않는다. 추가 필드는 422로 거부하며 소유권은 JWT에서 결정한다.
- Candidate가 하나라도 생성된 뒤에는 조건의 최초 저장과 수정을 모두 409 `Conditions cannot be changed after candidate creation`으로 차단한다.
- Candidate 생성 API도 커플 구성원 두 명의 조건 제출을 서버에서 검증한다. 따라서 정상 흐름에서는 두 사용자가 모두 조건을 저장하기 전에 Candidate가 생겨 한쪽의 최초 입력이 잠기는 상태가 발생하지 않는다.
- confirmed Decision은 409 `Decision is already closed`다.

#### 내 조건 조회 — `GET /decisions/{decision_id}/conditions/me`

응답은 위 `DecisionConditionRead`와 같다. JWT 사용자의 `(decision_id, user_id)` 행만 조회하며 상대방 조건을 선택할 path/query/body 인자가 없다. 본인 조건이 없으면 404 `Conditions not found`다.

#### 제출 여부 조회 — `GET /decisions/{decision_id}/conditions/status`

200 응답:

```json
{
  "decision_id": 100,
  "submitted_count": 1,
  "member_conditions": [
    {
      "user_id": 1,
      "submitted": true
    },
    {
      "user_id": 2,
      "submitted": false
    }
  ]
}
```

이 응답은 커플 구성원별 `user_id`와 제출 여부만 제공한다. 예산, 시간, 선호, 회피 조건 및 조건 행 ID는 포함하지 않는다. 추천 backend는 향후 서버 내부에서 두 개인 행을 조회할 수 있지만 공유 API가 상세 값을 반환해서는 안 된다.

공통 주요 오류:

- 401 Bearer 인증 없음·실패
- 403 `You cannot access this decision`: 타 커플 Decision
- 404 `Decision not found`
- 404 `Conditions not found`: 내 조건 조회에만 해당
- 409 `User does not belong to a couple`
- 409 `Decision is already closed`: PUT에만 해당
- 409 `Conditions cannot be changed after candidate creation`: PUT에만 해당
- 422 path 또는 Body 검증 실패

## 5. Candidate 및 승인 API

| Method | Path | Auth | Request | Success | 주요 Error |
|---|---|---|---|---|---|
| POST | `/decisions/{decision_id}/candidates` | Bearer | JSON `DecisionCandidateCreate` | 201 `DecisionCandidateRead` | 401, 403 타 커플, 404 Decision 없음, 409 조건 미제출·닫힘, 422 |
| POST | `/candidates/{candidate_id}/approve` | Bearer | 없음 | 201 `DecisionApprovalRead` | 401, 403 타 커플, 404 Candidate·Decision 없음, 409 닫힘·구버전·중복, 422 |

### 5.1 Candidate 생성 — `POST /decisions/{decision_id}/candidates`

요청:

```json
{
  "content": "초밥"
}
```

201 응답:

```json
{
  "id": 501,
  "decision_id": 100,
  "content": "초밥",
  "version": 2,
  "is_current": true
}
```

주요 오류:

- 404 `Decision not found`
- 403 `You cannot access this decision`
- 409 `Both couple members must submit conditions before candidate creation`: 커플이 두 명으로 연결되지 않았거나 두 구성원 중 한 명 이상이 해당 Decision의 조건을 제출하지 않음
- 409 `Decision is already closed`
- 422 Body 누락, `content` 누락 또는 잘못된 path parameter

서버는 Candidate를 만들기 전에 현재 Decision 소유 Couple의 구성원이 정확히 두 명인지 확인하고, 두 구성원 ID 모두에 해당하는 `DecisionCondition` 행이 있는지 검증한다. 두 조건이 모두 있으면 기존과 같이 첫 후보는 `version=1`, 이후 후보는 version을 증가시키며 이전 후보를 non-current로 바꾼다. Candidate가 생성된 뒤에는 두 사용자의 조건 PUT이 모두 잠긴다.

기존 데이터에 조건 없이 생성된 Candidate가 있는 경우 기존 Candidate와 승인 이력은 삭제하거나 변경하지 않으며 조회와 현재 후보 승인은 계속 허용한다. 다만 새 Candidate version 생성은 409로 차단한다. 조건 PUT도 기존 Candidate 잠금 정책에 따라 409이므로, 해당 레거시 Decision을 계속 사용하려면 운영자가 백업 후 두 구성원의 조건 행을 검증·보완하는 별도 데이터 이관 절차가 필요하다. API가 기존 이력을 자동 초기화하거나 임의 조건을 생성하지 않는다.

커플 미가입 사용자가 존재하는 다른 커플 Decision에 후보 생성을 시도하면 별도 미가입 검사 없이 커플 불일치로 403을 받는다.

### 5.2 Candidate 승인 — `POST /candidates/{candidate_id}/approve`

Body 없이 호출한다. 승인 사용자 ID는 JWT에서 결정되며 클라이언트가 `user_id` 또는 `approved`를 보내지 않는다.

201 응답:

```json
{
  "id": 900,
  "candidate_id": 501,
  "user_id": 1,
  "approved": true
}
```

주요 오류:

- 404 `Candidate not found`
- 404 `Decision not found`
- 403 `You cannot access this decision`
- 409 `Decision is already closed`
- 409 `Only the current candidate can be approved`
- 409 `User already approved this candidate`
- 422 `candidate_id`가 integer가 아님

승인 응답은 `DecisionApprovalRead` 한 건이며 갱신된 Decision 또는 `confirmed`를 포함하지 않는다. 승인 후 화면에서 전체 상태를 갱신하려면 `GET /decisions/{decision_id}`를 다시 호출해야 한다.

## 6. 주요 응답 상태 코드

| Status | 의미 | 대표 상황 |
|---|---|---|
| 200 | 조회·일반 처리 성공 | 로그인, 현재 사용자, 커플 참여·조회, Decision 조회, 로그아웃 |
| 201 | 리소스 생성 성공 | 회원가입, 커플 생성, Decision 생성, Candidate 생성, 승인 생성 |
| 401 | 인증 실패 | Bearer 없음·오류·만료, 폐기 토큰, 잘못된 로그인 정보 |
| 403 | 인증됐지만 커플 권한 없음 | 다른 커플 Decision의 상세·후보·승인 접근 |
| 404 | 리소스 또는 연결 상태 없음 | 초대 코드, Couple, Decision, Candidate 없음 |
| 409 | 현재 상태와 충돌 | 이미 커플 가입, 커플 정원 초과, 커플 미가입 Decision 요청, 조건 미제출 상태의 Candidate 생성, 닫힌 결정, 구버전·중복 승인 |
| 422 | 요청 형식 검증 실패 | 필수 JSON/form 필드 누락, path integer 오류 |

HTTP 오류의 `detail` 문자열은 현재 프론트의 사용자 메시지 매핑 키이기도 하므로 백엔드 변경 시 프론트와 함께 갱신해야 한다.

## 7. 최신 후보/version 규칙

1. 각 Decision의 첫 Candidate `version`은 1이다.
2. 새 Candidate 생성 시 현재 current 후보 한 건을 `is_current=false`로 바꾼다.
3. 새 Candidate의 version은 이전 current 후보의 version에 1을 더한다.
4. `(decision_id, version)`은 DB unique constraint다.
5. 승인 API는 `is_current=true`인 Candidate만 허용한다.
6. 이전 Candidate의 승인 레코드는 남아 있어도 새 Candidate 승인으로 승계되지 않는다.
7. 같은 사용자는 `(candidate_id, user_id)` unique 규칙에 따라 같은 Candidate를 한 번만 승인할 수 있다.
8. 커플 구성원이 정확히 두 명이고 동일한 current Candidate의 서로 다른 승인 사용자 수가 2이면 Decision이 `confirmed`가 된다.
9. `confirmed` 이후 Candidate 생성과 추가 승인은 409 `Decision is already closed`로 차단된다.
10. 과거 Candidate 목록을 조회하는 endpoint는 현재 없다. 상세 응답은 최신 current Candidate만 제공한다.

현재 코드는 정상적인 순차 요청 흐름을 구현한다. 동시 Candidate 생성과 동시 승인·확정의 원자성 보강은 별도 백엔드 과제이며 프론트가 중복 클릭을 막더라도 서버 보강을 대체하지 않는다.

## 8. 커플 데이터 접근 규칙

- 모든 보호 API의 사용자 신원은 Bearer JWT에서 결정한다.
- 클라이언트가 `user_id`, `created_by_id`, `couple_id`를 소유권 근거로 보내지 않는다.
- Decision 목록은 `current_user.couple_id`로 필터링한다.
- Decision 상세, Candidate 생성, Candidate 승인은 연결된 Decision의 `couple_id`와 현재 사용자의 `couple_id`를 비교한다.
- 타 커플 Decision 접근은 403 `You cannot access this decision`이다.
- Decision 생성, 목록, 상세는 커플 미가입 사용자에게 409를 반환한다.
- Candidate 생성과 승인은 별도 커플 미가입 분기가 없어 존재하는 Decision에 접근하면 403을 반환한다.
- Couple과 Decision 응답의 ID를 클라이언트에서 변경해도 서버 권한 검사를 우회할 수 없어야 한다.
- PET DOCK 버튼, Web Serial 이벤트, BLE 이벤트는 사용자 신원 또는 승인 권한이 아니다.
- 하드웨어 이벤트 처리 코드에서 `/candidates/{candidate_id}/approve`를 호출하지 않는다.

## 9. 프론트엔드 구현 시 주의사항

### 현재 프론트에서 실제 호출하는 API

| 화면 동작 | 현재 호출 |
|---|---|
| 세션 복원 | `GET /users/me`, `GET /couples/me` |
| 로그인 | `POST /token` |
| 회원가입 | `POST /users` |
| 커플 생성 | `POST /couples` |
| 초대 코드 참여 | `POST /couples/join` |
| 커플 연결 새로고침 | `GET /couples/me` |
| 로그아웃 | `POST /logout` |

`frontend/app.js`는 인증·커플·PET DOCK 화면을 담당하고, 신규 `frontend/decision-flow.js`가 Decision·조건·추천·Candidate·승인 API를 호출한다. 실제 두 계정 브라우저 시연은 별도 검증이 필요하다.

### 구현 주의사항

- 프론트는 토큰을 `sessionStorage`의 `tow_pick_token`에 저장한다.
- 인증 요청마다 `Authorization: Bearer ${token}`을 보낸다.
- 로그인 Body는 `URLSearchParams`로 보내고 JSON으로 보내지 않는다.
- JSON Body가 있는 요청만 `Content-Type: application/json`을 지정한다.
- `GET /couples/me`의 404 `User does not belong to a couple`은 세션 실패가 아니라 커플 연결 전 상태다.
- 목록 응답만으로 승인 상태를 표시할 수 없다. 각 Decision의 상세 조회가 필요하다.
- Candidate 승인 후 응답에 `confirmed`가 없으므로 상세를 다시 조회한다.
- Candidate 이력 조회, 승인 취소, Decision 삭제·수정 endpoint는 없다.
- HTML의 이메일·비밀번호 검증과 백엔드 검증 수준이 다르다. UI 검증을 서버 검증으로 간주하지 않는다.
- 현재 오류 처리기는 문자열 `detail`을 전제로 한다. 422의 배열 `detail`을 사용자 메시지로 변환하는 처리가 필요하다.
- 현재 API에는 CORS 설정이 없다. 별도 프론트 dev server를 사용하면 same-origin proxy가 필요하다.
- 하드웨어 버튼 이벤트를 승인 버튼 handler와 연결하지 않는다.

## 10. planned API 목록

다음 영역은 현재 모델 또는 endpoint가 없으며 구체적인 Method, Path, 요청·응답 schema도 확정되지 않았다. 프론트에서 임의 endpoint를 가정하지 않는다.

| 영역 | 상태 | 현재 계약 |
|---|---|---|
| 두 사용자 조건 기반 규칙형 추천 | implemented (P0 rules) | `POST /decisions/{decision_id}/recommendations` — 신규 후보 v1 생성, 가격·시간은 시연용 |
| Candidate 자동 생성·추천 | partial | 사용자 입력 시연용 옵션의 규칙형 추천 v1 생성 가능. 자동 실매장 검색/가격 확인/AI 추천은 미구현 |
| 별도 최종 결정 기록 | planned | 현재는 `Decision.status`와 current Candidate만 사용 |
| 만족도·간단 피드백 | planned | endpoint/schema 없음 |
| OUR PET 상태·성장 | planned | endpoint/schema 없음 |
| 생일 월·일 기반 OUR PET 배정 | planned | 곰·토끼 배정 규칙만 확정, endpoint/schema 없음 |
| 경험치 및 중복 지급 방지 | planned | endpoint/schema 없음 |
| 기념일·일정 | planned | endpoint/schema 없음 |
| n8n 알림 연동 | planned | endpoint/schema 없음 |
| PET 이벤트 영속화 | planned | Web Serial/BLE 이벤트 저장 API 없음 |

## 11. 기타 현재 구현된 endpoint

핵심 WBS 계약 외에도 현재 코드에는 다음 endpoint가 존재한다.

| Method | Path | Auth | Request | Success | 주요 Error |
|---|---|---|---|---|---|
| GET | `/` | No | 없음 | 200 실행 메시지 | 없음 |
| GET | `/health` | No | 없음 | 200 상태·DB 종류 | 없음 |
| GET | `/app` | No | 없음 | 200 `index.html` | 파일 제공 오류 가능 |
| POST | `/messages` | Bearer | JSON `{ "content": string }` | 200 `MessageRead` | 401, 409 커플 미가입, 422 |
| GET | `/messages` | Bearer | 없음 | 200 `MessageRead[]` | 401, 409 커플 미가입 |

`/messages`는 현재 프론트에서 호출하지 않는다. Message는 로그인 사용자의 `sender_id`와 `couple_id`를 서버에서 채우고 현재 커플 데이터만 조회한다.

## 12. 코드 대조 결과

- `main.py`의 모든 인증·커플·공동결정·Candidate·승인 route와 status code를 대조했다.
- `schemas.py`의 실제 필드명과 nullable 여부를 응답 예시에 반영했다.
- `auth.py`의 Bearer JWT, 60분 만료, 토큰 폐기 동작을 반영했다.
- `frontend/app.js`의 실제 7개 API 경로, Body 형식, 토큰 저장·헤더 처리를 대조했다.
- 현재 프론트가 호출하는 인증·커플 endpoint의 Method, Path, Body는 백엔드와 일치한다.
- 공동결정 backend endpoint는 구현되어 있지만 현재 프론트에는 연결되지 않았다.
- 개인 조건·규칙형 추천 API는 구현되어 있으며 프론트 연결 코드는 신규로 추가되었다. OUR PET, 경험치, 일정, PET 이벤트 영속화는 `planned`다. 브라우저 E2E 및 실가격 확인은 미검증이다.


## P0 규칙형 균형 추천 API

- `POST /decisions/{decision_id}/recommendations` (JWT, JSON `RecommendationCreate`, 성공 201 `RecommendationRead`).
- 최대 8개 시연용 후보의 `title`, `estimated_total_cost_krw`, `time_slot`, `tags`를 받는다(최소 2개).
- **예산은 각 사용자별 2인 총액 상한**으로 해석하며, 제안 총액은 양쪽 상한 각각을 통과해야 한다. 상한을 합산하지 않는다.
- 후보의 시각·태그는 문자열 정규화 후 완전 일치만 지원하고 자연어 추론은 하지 않는다.
- 두 사람의 조건 제출 완료 + 첫 Candidate 생성 전 + Decision open 상태에서 **1회** 실행한다.
- 적합 후보가 있으면 Candidate v1을 생성하지만, 양측 승인 API는 기존대로 따로 호출한다.
- 적합 후보 없음도 시도 원장에 저장되어 동일 Decision에서 재추천 불가하다. 수동 후보 생성은 가능하다.
- 응답은 추천 후보와 버전만 포함하며 상대방 조건·개인 점수·탈락 이유는 노출하지 않는다.
- 상세 계약, 오류 코드, 가격 미검증 주의는 [`BALANCED_RECOMMENDATIONS.md`](BALANCED_RECOMMENDATIONS.md) 참조.
- 실제 브라우저 UI, 실가격 검증, 동시 요청 원자성은 미구현/미검증 상태다.
