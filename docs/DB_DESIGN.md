# TWO-PICK DB 설계 검수

- WBS: 1.2.5
- 검수일: 2026-11-24
- 기능 갱신: WBS 2.2.5 개인별 비공개 조건 API
- WBS 원담당: 김해인 / 실제 구현: 이효재(대행)
- 기준: `main`의 `01eb9e2`에서 분기한 `feature/p0-private-conditions-20261124`의 `models.py`와 실제 API
- DB: SQLite (`sqlite:///./tow_pick.db`)

## 관계 개요

```text
Couple 1 ── N User
Couple 1 ── N Message N ── 1 User(sender)
Couple 1 ── N Decision N ── 1 User(created_by)
Decision 1 ── N DecisionCondition N ── 1 User
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

### DecisionCondition

| 항목 | 내용 |
|---|---|
| 소유자 | `user_id`의 개인 비공개 조건. 상위 Decision의 커플 스코프에 속함 |
| 주요 컬럼 | `id`, `decision_id`, `user_id`, `max_budget`, `available_time`, `preferences`, `avoidances`, `created_at`, `updated_at` |
| user_id 관계 | `user_id → users.id`; 요청 Body가 아니라 JWT 사용자로 지정 |
| couple_id 관계 | 직접 컬럼 없음. `decision_id → decisions.couple_id`로 권한 확인 |
| version | 없음. Candidate 생성 전까지 동일 행을 수정하며 Candidate 생성 뒤에는 변경 차단 |
| unique | `(decision_id, user_id)` |
| 중복 규칙 | 같은 사용자의 반복 PUT은 새 행을 만들지 않고 기존 행을 수정 |

`max_budget`은 정수이며 API에서 0~1,000,000,000 범위를 검증한다. `available_time`은 최대 200자, `preferences`와 `avoidances`는 각각 최대 1,000자다. 상대방 상세 조건을 반환하는 API는 없고 제출 상태 응답에는 커플 구성원의 `user_id`와 boolean만 포함한다.

현재 스키마 초기화 방식인 `Base.metadata.create_all()`은 기존 테이블이나 행을 삭제하지 않고 `decision_conditions`가 없을 때 새 테이블만 생성한다. 별도 migration 도구와 schema version 이력은 아직 없으므로 배포 전 DB 백업 및 신규 테이블 생성 확인은 운영 절차로 남는다.

후보가 생성된 뒤 조건이 바뀌어 추천 근거와 Candidate가 불일치하는 일을 막기 위해 Candidate 1건 이상 존재 시 조건의 최초 저장과 수정 모두 거부한다. 추천 시도 원장이 존재하면 결과가 `no_match`여서 후보가 없어도 조건 변경을 거부한다. 향후 조건 version과 Candidate 입력 snapshot을 도입하기 전까지 이 정책을 유지한다.

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
3. 개인 조건은 `(decision_id, user_id)` unique로 사용자별 결정당 1행을 유지한다.
4. 현재 후보에 대한 서로 다른 승인 사용자 수가 2이고 커플 구성원이 정확히 2명이면 결정 상태를 `confirmed`로 바꾼다.
5. 확정 이후 후보 생성과 승인은 `status != open` 검사로 막는다.
6. 2차 백엔드에서는 관련 SQLite 쓰기를 `BEGIN IMMEDIATE`로 직렬화하고 별도 연결의 경쟁 테스트를 추가했다. 다중 프로세스 부하 검증은 남아 있다.

## 타 커플 접근 차단 원칙

- 소유권의 기준은 요청 본문의 ID가 아니라 인증된 `current_user.couple_id`다.
- 커플 공유 데이터 목록은 항상 `WHERE couple_id = current_user.couple_id`로 조회한다.
- 단건 결정, 후보, 승인 접근은 최종적으로 연결된 `Decision.couple_id`를 현재 사용자와 비교한다.
- 개인 조건 저장·조회는 `Decision.couple_id` 검증 후 JWT 사용자 ID로만 행을 선택한다. 상대방 상세 행을 선택하는 API는 제공하지 않는다.
- 신규 하위 테이블도 직접 `couple_id`를 갖거나 상위 FK 경로로 커플을 검증해야 한다.
- 생성 시 `user_id`, `created_by_id`, `sender_id`, `couple_id`는 가능한 한 서버가 인증 컨텍스트에서 채운다.
- 타 커플 단건 접근은 현재 결정 API 정책대로 403, 존재하지 않는 리소스는 404로 처리한다.

## SQLite 제약 관련 주의

`database.py`의 기본 engine 연결은 `PRAGMA foreign_keys=ON` 및 `busy_timeout=5000`을 설정한다. 테스트에서 별도 생성한 SQLite engine은 해당 연결 이벤트를 별도로 설정해야 같은 FK 강제를 받는다. unique constraint는 DB에서 강제된다.

## 확장 모델 현황

아래 각 항목의 `implemented`/`planned` 표시를 기준으로 읽는다. PET 영역은 여전히 설계 제안이며 테이블·API가 없다.

### DecisionConfirmation — 최종 결정 기록 (`implemented`, 2026-11-25)

| 제안 필드 | 목적 |
|---|---|
| `id` | PK |
| `decision_id` | 결정 FK, unique로 결정당 최종 기록 1건 |
| `candidate_id` | 확정된 정확한 후보 버전 FK |
| `content_snapshot`, `version` | 이후 후보 데이터 변화와 무관한 최종 기록 |
| `confirmed_at` | 확정 시각 |

양측 승인으로 `Decision.status`를 `confirmed`로 바꾸는 트랜잭션에서 후보 ID, version, content snapshot과 확정 시각을 한 건 저장한다. `decision_id` unique로 중복 기록을 막는다. 신규 테이블 생성은 기존 행을 삭제하지 않는다. 이 변경 전에 이미 확정된 Decision에는 기록 행이 자동 생성되지 않으며, 기존 상세 조회는 계속 동작한다. 이력 이관은 백업과 원본 후보 확인 후 별도 수행해야 한다. 별도 SQLite 연결의 병렬 승인 자동 테스트는 통과했으며 다중 프로세스 부하 검증은 남아 있다.

### DecisionFeedback — 만족도/간단 피드백 (`implemented`, 2026-11-25 2차)

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
| `species` | `bear` 또는 `rabbit` 중 배정된 한 종 |
| `assignment_rule_version` | 생일 조합 규칙 변경 시 배정 근거 추적 |
| `assigned_at` | 최초 배정 시각 |
| `experience`, `level` | 누적 경험치와 표시 레벨 |
| `mood` 또는 상태 필드 | 현재 펫 상태 |
| `updated_at` | 마지막 상태 변경 |

소유자는 개인이 아니라 커플이다. 초기 규칙은 두 사용자의 생일 월·일 합계가 짝수이면 `bear`, 홀수이면 `rabbit`이며 입력 순서와 무관하다. 생년은 수집하지 않는다. 가능한 경우 backend는 월·일 요청을 검증한 뒤 parity 기여값만 임시 저장하고, 두 입력이 모여 배정되면 임시값을 삭제해 정확한 생일 원문 대신 `species`와 규칙 버전만 영속 저장한다. 하드웨어 연결 상태는 일시적 브라우저 상태이므로 영속 PET 상태와 분리한다.

### PetExperienceEvent — 경험치 원장

| 제안 필드 | 목적 |
|---|---|
| `id`, `couple_id` | 원장 PK와 소유 커플 |
| `event_type` | 예: `decision_confirmed` |
| `source_id` | 원인이 된 `decision_id` 등 |
| `amount`, `created_at` | 지급량과 시각 |

공동결정 경험치는 `UNIQUE(couple_id, event_type, source_id)`로 중복 지급을 막는다. 확정 트랜잭션에서 원장 행 삽입이 성공한 경우에만 `PetState.experience`를 증가시키거나, 원장 합계를 경험치의 기준값으로 사용한다. API의 사전 조회만으로 중복을 막지 않고 DB unique를 최종 방어선으로 둔다.

### CoupleSchedule — 기념일/일정 (`implemented`, 2026-11-25 2차)

| 제안 필드 | 목적 |
|---|---|
| `id`, `couple_id` | 일정 PK와 소유 커플 |
| `created_by_id` | 작성 사용자 |
| `title`, `local_date`, `local_time` | 일정 이름·한국 현지 날짜와 선택 시간(null이면 종일) |
| `kind`, `repeat_rule` | 기념일/일정 구분과 반복 규칙 |
| `revision`, `deleted_at` | 수정 버전, soft delete 시각 |

조회·수정·삭제는 모두 현재 커플로 제한하고, `created_by_id`는 감사 정보로 유지하되 공유 데이터의 접근 권한은 `couple_id`로 판정한다.

`CoupleInvite`는 `couple_id` PK/FK, 현재 `code` unique, `issued_at`, `used_at`을 저장한다. 발급 시각이 없는 기존 초대 코드에는 임의 날짜를 채우지 않고 재발급 전까지 만료로 취급한다. 기존 연결 관계와 다른 테이블 행은 유지한다.

후보별 current 제약은 `decision_candidates(decision_id) WHERE is_current=1` 부분 unique index로 보강했다. `decision_id, version`, 후보별 사용자 승인, Decision별 확정 기록의 기존 unique 제약을 유지한다. 조건·추천·후보·승인 수정은 SQLite `BEGIN IMMEDIATE`로 읽기 전 쓰기 잠금을 얻어 다른 연결과 직렬화한다. 기존 DB에 중복 current 후보가 있으면 index 생성이 실패하며 백업 후 수동 정합성 복구가 필요하다. 자동으로 후보 기록을 삭제하거나 고치지 않는다.

`DecisionFeedback`은 `(decision_id, user_id)` unique, `score` 1~5, 선택 `comment` 최대 500자와 생성·수정 시각을 저장한다. 서버가 JWT 사용자와 결정의 `couple_id`를 검증하고 개인 GET/PUT만 제공한다. 점수 범위와 글자 길이는 API schema에서 검증하며 기존 SQLite 테이블에 DB CHECK를 추가하지 않는다.

`NotificationSetting`은 `user_id` PK/FK, 기본 미동의, D-1/당일 선택, 한국 현지 발송 시각, 정책 버전, 동의·철회 시각을 가진다. 설정 행이 없어도 GET은 미동의 기본값을 반환한다. `NotificationJob`은 일정 ID/FK, revision, 수신 사용자 ID/FK, 알림 종류, 발생 날짜, UTC 예정 시각, SHA-256 dedupe key unique, 상태·시도 횟수·성공·실패 시각을 저장한다. 동일 key는 중복 삽입하지 않는다. 일정 삭제는 원장을 보존하기 위해 soft delete하고 미발송 작업을 취소한다. 현재는 `pending`/`canceled` 예약 기반만 사용하며 발송·실패 재시도 worker는 없다.

## 우선 보강 순서

1. SQLite FK 강제와 스키마 마이그레이션 도입
2. 승인·확정 전이의 단일 트랜잭션 및 동시성 보장
3. current 후보 1건 보장과 버전 생성 경쟁 처리
4. 최종 결정 기록 및 경험치 원장의 unique 기반 멱등 지급
5. 피드백, PET 상태, 기념일·일정 모델과 커플 스코프 API


## P0 규칙형 추천 시도 원장

`DecisionRecommendationAttempt`: `id`, `decision_id`(unique), `requested_by_id`, `outcome`(`selected`/`no_match`), `candidate_id`(nullable), `created_at`. 같은 Decision에서 추천 평가를 성공/실패와 관계없이 한 번만 허용하여 조건 역추정 반복을 제한한다. 점수·비공개 조건·제출 후보 목록은 저장하지 않는다.

기존 `DecisionCondition.max_budget`는 **각자가 허용하는 2인 총액 상한**이고 후보의 `estimated_total_cost_krw`와 각각 비교한다. 기존 저장값의 의미·단위는 자동 마이그레이션하지 않으므로 별도 확인이 필요하다. `Base.metadata.create_all`은 신규 테이블만 만들며 기존 DB를 삭제하지 않는다. 운영 백업·마이그레이션·병렬 요청 원자성은 후속 과제다.
