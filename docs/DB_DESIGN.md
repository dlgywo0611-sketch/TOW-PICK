# TWO-PICK DB 설계 검수

- WBS: 1.2.5
- 검수일: 2026-11-24
- 기준: `origin/main` `eddb574`의 `models.py`와 실제 API
- DB: SQLite (`sqlite:///./tow_pick.db`)

## 관계 개요

```text
Couple 1 ── N User
Couple 1 ── N Message N ── 1 User(sender)
Couple 1 ── N Decision N ── 1 User(created_by)
Decision 1 ── N DecisionCandidate
DecisionCandidate 1 ── N DecisionApproval N ── 1 User

RevokedToken: 해시된 JWT 단위 독립 테이블
```

현재 ORM relationship은 `Couple.members`와 `User.couple`에만 선언되어 있다. 나머지는 FK 컬럼과 API 쿼리로 연결한다.

## 현재 구현된 모델

### User

| 항목 | 내용 |
|---|---|
| 소유자 | 개인 사용자 |
| 주요 컬럼 | `id`, `email`, `nickname`, `hashed_password`, `couple_id nullable` |
| user_id 관계 | 자체 PK가 다른 모델의 사용자 FK가 됨 |
| couple_id 관계 | `couples.id` FK, 미가입 시 null |
| unique | `email` |
| 중복 규칙 | 같은 이메일 회원가입은 API에서 409, DB unique로도 차단 |

주의: 현재 DB 구조는 커플당 사용자 수를 최대 2명으로 강제하지 않는다. API의 참여 전 구성원 수 확인만 존재하므로 동시 참여에 대한 트랜잭션 보강이 필요하다.

### Couple

| 항목 | 내용 |
|---|---|
| 소유자 | 연결된 두 사용자의 공유 영역 |
| 주요 컬럼 | `id`, `invite_code` |
| user_id 관계 | 직접 컬럼 없음. `users.couple_id`의 역관계로 구성원 확인 |
| couple_id 관계 | 자체 PK가 커플 소유 데이터의 FK가 됨 |
| unique | `invite_code` |
| 중복 규칙 | 초대 코드 충돌 시 생성 루프가 재시도 |

### Message

| 항목 | 내용 |
|---|---|
| 소유자 | 커플 공유 데이터 |
| 주요 컬럼 | `id`, `content`, `sender_id`, `couple_id` |
| user_id 관계 | `sender_id → users.id` |
| couple_id 관계 | `couple_id → couples.id` |
| unique | 없음 |
| 중복 규칙 | 동일 내용의 반복 전송 허용 |

API는 로그인 사용자의 ID와 `couple_id`를 서버에서 채우며, 조회도 현재 커플로 제한한다. DB는 `sender_id` 사용자가 같은 `couple_id` 소속인지 복합 제약으로 보장하지 않는다.

### RevokedToken

| 항목 | 내용 |
|---|---|
| 소유자 | 인증 시스템. 현재 사용자 FK는 없음 |
| 주요 컬럼 | `id`, `token_hash`, `expires_at` |
| user_id / couple_id | 없음 |
| unique | `token_hash` |
| 중복 규칙 | 같은 토큰의 반복 로그아웃은 기존 행을 재사용 |

원문 JWT 대신 SHA-256 해시만 저장한다. 만료 행 자동 정리는 아직 없다.

### Decision

| 항목 | 내용 |
|---|---|
| 소유자 | `couple_id`의 공유 결정 |
| 주요 컬럼 | `id`, `couple_id`, `created_by_id`, `title`, `status` |
| user_id 관계 | `created_by_id → users.id` |
| couple_id 관계 | `couple_id → couples.id` |
| version | 없음. 버전은 후보에 존재 |
| unique | 없음 |
| 중복 규칙 | 같은 제목의 여러 결정 허용 |

현재 `status`는 문자열 `open`/`confirmed`를 사용하지만 DB CHECK 또는 enum은 없다. `created_by_id`의 사용자가 같은 커플인지 DB 복합 제약으로는 보장하지 않는다.

### DecisionCandidate

| 항목 | 내용 |
|---|---|
| 소유자 | 상위 Decision의 커플 |
| 주요 컬럼 | `id`, `decision_id`, `content`, `version`, `is_current` |
| user_id / couple_id | 직접 컬럼 없음. `decision_id`를 통해 상속 |
| version | 결정별 1부터 증가 |
| unique | `(decision_id, version)` |
| 중복 규칙 | 같은 결정에서 같은 버전은 금지. 같은 내용의 새 버전은 허용 |

새 버전 생성 시 이전 current를 false로 바꾼다. 다만 결정당 `is_current=true` 1건을 DB가 강제하지 않아 동시 생성 보강이 필요하다.

### DecisionApproval

| 항목 | 내용 |
|---|---|
| 소유자 | 승인한 개인 사용자이며, 후보의 결정을 통해 커플 스코프에 속함 |
| 주요 컬럼 | `id`, `candidate_id`, `user_id`, `approved` |
| user_id 관계 | `user_id → users.id` |
| couple_id 관계 | 직접 컬럼 없음. 후보 → 결정 → 커플로 확인 |
| version | 직접 컬럼 없음. `candidate_id`가 특정 버전을 고정 |
| unique | `(candidate_id, user_id)` |
| 중복 규칙 | 한 사용자는 한 후보를 한 번만 승인 |

승인 API는 로그인 사용자와 결정 커플의 일치를 확인한다. 이전 버전의 승인 행은 보존되지만 새 후보의 승인 수에는 포함되지 않는다.

## 현재 중복 및 확정 처리 규칙

1. 후보 버전은 `(decision_id, version)` unique로 중복을 막는다.
2. 사용자의 후보 승인은 `(candidate_id, user_id)` unique로 중복을 막는다.
3. 현재 후보에 대한 서로 다른 승인 사용자 수가 2이고 커플 구성원이 정확히 2명이면 결정 상태를 `confirmed`로 바꾼다.
4. 확정 이후 후보 생성과 승인은 `status != open` 검사로 막는다.
5. 현재 구현은 정상적인 순차 요청을 처리하지만 동시 버전 생성·동시 승인의 원자성은 보장하지 않는다.

## 타 커플 접근 차단 원칙

- 소유권의 기준은 요청 본문의 ID가 아니라 인증된 `current_user.couple_id`다.
- 커플 공유 데이터 목록은 항상 `WHERE couple_id = current_user.couple_id`로 조회한다.
- 단건 결정, 후보, 승인 접근은 최종적으로 연결된 `Decision.couple_id`를 현재 사용자와 비교한다.
- 신규 하위 테이블도 직접 `couple_id`를 갖거나 상위 FK 경로로 커플을 검증해야 한다.
- 생성 시 `user_id`, `created_by_id`, `sender_id`, `couple_id`는 가능한 한 서버가 인증 컨텍스트에서 채운다.
- 타 커플 단건 접근은 현재 결정 API 정책대로 403, 존재하지 않는 리소스는 404로 처리한다.

## SQLite 제약 관련 주의

모델에는 `ForeignKey`가 선언되어 있지만 현재 `database.py`는 연결 시 `PRAGMA foreign_keys=ON`을 설정하지 않는다. SQLite 기본 설정에서는 FK가 실제로 강제되지 않을 수 있으므로 고아 행 방지를 위해 연결 이벤트 설정과 마이그레이션 검증이 필요하다. unique constraint는 현재도 DB에서 강제된다.

## 계획 모델 (`planned`, 미구현)

아래는 설계 방향이며 이번 WBS에서 테이블이나 API를 생성하지 않는다.

### DecisionConfirmation — 최종 결정 기록

| 제안 필드 | 목적 |
|---|---|
| `id` | PK |
| `decision_id` | 결정 FK, unique로 결정당 최종 기록 1건 |
| `candidate_id` | 확정된 정확한 후보 버전 FK |
| `content_snapshot`, `version` | 이후 후보 데이터 변화와 무관한 최종 기록 |
| `confirmed_at` | 확정 시각 |

`Decision.status`만 바꾸는 현재 방식에서 최종 후보와 확정 시점을 명시적으로 보존하는 방향이다.

### DecisionFeedback — 만족도/간단 피드백

| 제안 필드 | 목적 |
|---|---|
| `decision_id`, `user_id` | 대상 결정과 작성자 |
| `score`, `comment` | 간단 점수와 선택 메모 |
| `created_at`, `updated_at` | 작성·수정 이력 |

`UNIQUE(decision_id, user_id)`로 사용자별 결정당 피드백 1건을 유지하고, 해당 사용자가 결정의 커플 구성원인지 API에서 검증한다.

### PetState — OUR PET 상태

| 제안 필드 | 목적 |
|---|---|
| `couple_id` | 커플당 펫 1개, PK 또는 unique |
| `experience`, `level` | 누적 경험치와 표시 레벨 |
| `mood` 또는 상태 필드 | 현재 펫 상태 |
| `updated_at` | 마지막 상태 변경 |

소유자는 개인이 아니라 커플이다. 하드웨어 연결 상태는 일시적 브라우저 상태이므로 영속 PET 상태와 분리한다.

### PetExperienceEvent — 경험치 원장

| 제안 필드 | 목적 |
|---|---|
| `id`, `couple_id` | 원장 PK와 소유 커플 |
| `event_type` | 예: `decision_confirmed` |
| `source_id` | 원인이 된 `decision_id` 등 |
| `amount`, `created_at` | 지급량과 시각 |

공동결정 경험치는 `UNIQUE(couple_id, event_type, source_id)`로 중복 지급을 막는다. 확정 트랜잭션에서 원장 행 삽입이 성공한 경우에만 `PetState.experience`를 증가시키거나, 원장 합계를 경험치의 기준값으로 사용한다. API의 사전 조회만으로 중복을 막지 않고 DB unique를 최종 방어선으로 둔다.

### CoupleSchedule — 기념일/일정

| 제안 필드 | 목적 |
|---|---|
| `id`, `couple_id` | 일정 PK와 소유 커플 |
| `created_by_id` | 작성 사용자 |
| `title`, `scheduled_at` | 일정 내용과 시각 |
| `kind`, `repeat_rule` | 기념일/일정 구분과 반복 규칙 |

조회·수정·삭제는 모두 현재 커플로 제한하고, `created_by_id`는 감사 정보로 유지하되 공유 데이터의 접근 권한은 `couple_id`로 판정한다.

## 우선 보강 순서

1. SQLite FK 강제와 스키마 마이그레이션 도입
2. 승인·확정 전이의 단일 트랜잭션 및 동시성 보장
3. current 후보 1건 보장과 버전 생성 경쟁 처리
4. 최종 결정 기록 및 경험치 원장의 unique 기반 멱등 지급
5. 피드백, PET 상태, 기념일·일정 모델과 커플 스코프 API
