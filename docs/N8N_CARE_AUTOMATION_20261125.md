# TWO-PICK CARE 알림 자동화 통합 기록 — 2026-11-25

## 범위와 검증 수준

기준은 PR #38 병합 후 `origin/main`의 일정·동의·알림 작업 원장이다. 이번 변경은 기존 01 Webhook과 02 가상 스케줄러를 보존하고, **비활성 03 가상 발송**과 **비활성 04 승인 Gmail 시험**을 추가한다. 실제 Gmail 시험은 사용자에게 승인받은 주소로 D-1·당일 각 1통만 수행했다. 03은 실제 사용자 주소를 거부한다. 운영 서비스 사용자 발송과 03 자동 스케줄러 활성화는 미검증이다.

| 이벤트 | 현재 처리 | 수준 |
|---|---|---|
| 회원가입·커플 연결·일정 등록 | 기존 FastAPI와 SQLite | 격리 DB에서 HTTP 흐름 실행 |
| 개인별 알림 동의·철회 | 기존 API; 기본 미동의, 당사자별 설정 | 자동 테스트·격리 DB HTTP 실행 |
| D-1·당일 작업 예약 | 기존 `plan_next_jobs`, `Asia/Seoul` 현지 시각을 UTC로 저장 | 자동 테스트·격리 DB 실행 |
| 만료/변경/삭제 작업 거부 | 10분 발송 창, revision·동의·주소 재검증 | 자동 테스트 |
| 작업 선점·결과 | SQLite `BEGIN IMMEDIATE`, 시도 원장, `simulated` 기록 | 동시 요청 자동 테스트·실제 n8n 수동 실행 |
| n8n 03 주기 실행 | 1분 Trigger가 JSON에 설정됨 | **NOT TESTED**; 워크플로 비활성 |
| Gmail 테스트 발송 | 04에서 승인된 수신 주소로 D-1·당일 각 1통 | n8n 성공·DB 접수 ID·Gmail 받은편지함 확인 |
| 운영 Gmail 발송 | 실제 서비스 사용자 대상 경로 없음 | **NOT IMPLEMENTED / NOT TESTED** |

## 구조와 워크플로 역할

```text
사용자별 동의 + 커플 일정 → FastAPI → SQLite NotificationJob
                                      ↑   ↓
비활성 03 n8n: 1분 Trigger → due IDs → claim → verify → mock result → 집계
```

- 01 Webhook Test: Header Auth와 요청 형식만 확인. 발송 없음.
- 02 Notification Scheduler: 8개 가상 시나리오. DB 연결·발송 없음.
- 03 CARE Notification Dispatch: 실제 로컬 FastAPI와 격리 SQLite를 호출하지만 **가상 결과만** 기록. 저장소 JSON은 `active=false`, 빈 `pinData`, 자격 증명 정보 없음.
- 04 Approved Gmail Test: 별도 격리 DB의 테스트 계정 작업을 **수동으로 한 건씩** 선점하고 승인된 한 주소에만 Gmail을 보낸다. Gmail 접수 ID를 DB에 남긴다. 저장소 JSON에는 실제 주소·자격 증명 정보가 없다. 자동 게시·운영 실행 경로는 없다.

03의 12개 노드: `1분 주기 확인`, `발송 예정 작업 조회`, `작업 ID 분리`, `발송 작업 선점`, `발송 직전 조건 확인`, `발송 가능 여부`, `테스트 알림 구성`, `차단 작업 정리`, `가상 발송 결과 기록`, `차단 결과 기록`, `처리 결과 병합`, `실행 결과 집계`. 수신 이메일과 일정 제목은 03의 조회·선점·검증 응답에 전달하지 않는다. 기본 메시지는 일정 이름을 포함하지 않는 일반 문구다. 노드별 연결은 [`03 JSON`](../n8n/workflows/TWO_PICK_03_CARE_NOTIFICATION_DISPATCH.json)에서 확인할 수 있다.

## 내부 API 계약

모든 경로는 `X-Two-Pick-Internal-Secret` 헤더가 필요하다. FastAPI는 `TWO_PICK_N8N_INTERNAL_SECRET`와 일정 시간 비교한다. 미설정 시 503, 누락·불일치 시 403이다. 이는 사용자 JWT와 별개인 **서버 간 테스트 키**다. 키는 Git 제외 `.env`와 로컬 n8n 자격 증명 저장소에만 둔다. HTTP 로그·문서·JSON에는 값을 남기지 않는다. `/internal` 경로는 인터넷에 공개하지 않고 로컬 바인딩 및 별도 네트워크 제한을 전제로 한다.

| Method | Path | Request | 200 응답 | 주요 오류 |
|---|---|---|---|---|
| GET | `/internal/notifications/due` | 없음 | `{ "job_ids": [1, 2] }` | 403, 503 |
| POST | `/internal/notifications/{job_id}/claim` | 생략 시 mock, 04는 `{ "mode": "test_email" }` | `{ "job_id": 1, "attempt": 1, "notification_type": "d1", "mode": "mock" }` | 403, 409, 422, 503 |
| POST | `/internal/notifications/{job_id}/verify` | 없음 | `{ "job_id": 1, "attempt": 1, "notification_type": "d1", "eligible": true }` | 403, 503 |
| POST | `/internal/notifications/{job_id}/result` | mock: `{ "attempt": 1, "result": "simulated" }`; Gmail: `result=sent`, `provider_message_id` | `{ "job_id": 1, "status": "simulated", "attempt": 1, "idempotent": false }` | 403, 409, 422, 503 |

`result`는 `simulated`, `sent`, `canceled`, `failed`를 받는다. `failed`에는 `error_code`가 필수이며 허용 값은 `connection_error`, `http_error`, `timeout`, `auth_error`, `delivery_failed`, `result_unknown`이다. `sent`에는 Gmail 응답의 `provider_message_id`가 필수다. 같은 시도·결과·접수 ID의 콜백은 `idempotent=true`로 응답한다. 03은 `simulated` 또는 `canceled`만, 04는 Gmail 성공 시 `sent`를 보낸다. 본 계약은 프론트엔드 공개 API가 아니다.

## 예약·선점·중복 방지

- 기존 `NotificationJob.dedupe_key` unique는 일정 ID·revision·수신자·알림 종류·발생 날짜를 묶는다. 새 `NotificationDispatchAttempt(job_id, number)` unique는 시도 중복을 막는다. 기존 DB 행은 변경하거나 삭제하지 않고 새 테이블을 `create_all`로 추가한다. 이전 시도 원장에 새 `mode`·`provider_message_id` 컬럼이 없으면 행을 보존하는 컬럼 추가를 적용한다.
- `due`는 예정 시각 도달 후 10분 이내의 `pending` 작업 ID 최대 100개만 반환한다. 매번 삭제·revision 변경·동의 철회·종류 비활성화·커플 불일치·테스트 주소 여부를 확인한다. 기한 경과는 `expired`, 부적격은 `canceled`로 남긴다.
- `claim`은 SQLite 쓰기 잠금을 얻은 트랜잭션에서 `pending → claimed`와 시도 행 추가를 함께 커밋한다. 같은 작업의 동시 선점은 하나만 성공한다. 비밀번호·JWT·개인 조건은 n8n에 제공하지 않는다.
- `verify`는 시도 유효성, 2분 claim 기한, 10분 창, 동의·revision을 다시 확인한다. `result=simulated` 저장 직전에도 재검증한다. 동의 변경·일정 수정/삭제 후 가상 성공으로 기록하지 않는다.
- 재시도 가능한 **가상 처리 실패**는 60초 × 시도 횟수의 지연 뒤 최대 3회까지 `pending`으로 돌아간다. 인증 오류는 중단한다. 타임아웃·결과 불명, 또는 claim 뒤 2분을 넘긴 실행은 `unknown`으로 남기고 자동 재처리하지 않는다. 10분 창을 넘긴 작업은 발송하지 않는다. 실제 Gmail 발송에 이 재시도 규칙을 그대로 적용할 수 없으며, 발송 수락 후 결과 저장 실패는 수동 대조가 선행돼야 한다.
- `simulated`는 `succeeded_at`을 채우지 않고 이메일 발송으로 취급하지 않는다. 반복 일정은 처리한 발생일의 dedupe key를 재사용하지 않고 다음 발생일의 작업을 계획한다.
- 04의 `test_email` 선점은 Git 제외 `TWO_PICK_N8N_ENABLE_TEST_EMAIL=1`과 `TWO_PICK_N8N_TEST_RECIPIENT`가 있어야 하며, 테스트 계정 이메일은 `example.test`여야 한다. 격리 DB에서 **최대 2회 선점**만 허용하고 실패한 선점도 한도에 포함한다. 실제 주소는 승인된 환경변수에서만 읽고 Git JSON에는 쓰지 않는다. Gmail 접수 ID를 받은 뒤에만 `sent`와 성공 시각을 기록한다. 이메일 경로에서는 자동 재시도를 하지 않는다.

## 오류 및 예외 처리

| 상황 | 현재 처리 | 남은 검증 |
|---|---|---|
| 동의 없음/철회·종류 꺼짐 | due/claim 차단, verify false, 결과 저장 직전 재확인 | 실제 전송 직전 경합 |
| 일정 수정/삭제 | revision 불일치·soft delete 차단 | 실제 전송 직전 경합 |
| 예정 전/10분 후 | 선점 금지, 만료 작업 상태 기록 | 자정·월말 실환경 연속 실행 |
| 동일 작업 동시 선점 | `BEGIN IMMEDIATE`와 상태 확인으로 한 건만 200 | 여러 FastAPI 프로세스 부하 |
| FastAPI 연결 실패/HTTP 오류 | n8n 실행 실패; claim이 남았다면 2분 뒤 `unknown` | 장애 복구·수동 대조 절차 |
| 내부 인증 실패 | 403; 무한 재시도 금지 | 운영 키 교체 |
| 결과 저장 실패 | claim이 남아 `unknown`; 임의 재발송 금지 | 실제 Gmail 연동 전 필수 설계 |
| Gmail 인증 실패 | 첫 실제 시도에서 자격 증명 만료로 노드 중단, 작업 `failed/auth_error` 기록 | 기존 실패 기록 보존; 사용자 재연결 후 별도 격리 DB로 재시험 |
| Gmail 발송 후 결과 저장 실패 | 동일 작업 자동 재선점 없음, 2분 뒤 `unknown` | Gmail 발신함·n8n·DB 수동 대조 필수 |

## 설치·실행·증빙

1. 기존 SQLite 파일을 먼저 별도 위치에 백업하고 무결성을 확인한다. 테스트에는 **별도 작업 디렉터리의 SQLite 파일**을 사용한다. `database.py`의 상대 경로 `tow_pick.db`는 실행 디렉터리에 따라 결정된다.
2. Git 제외 환경에 `SECRET_KEY`와 `TWO_PICK_N8N_INTERNAL_SECRET`을 설정하고, 격리 디렉터리에서 `PYTHONPATH`를 저장소로 지정해 `uvicorn main:app --host 127.0.0.1 --port 8001`을 실행한다. `/openapi.json`의 네 내부 경로를 확인한다.
3. `n8n/workflows/TWO_PICK_03_CARE_NOTIFICATION_DISPATCH.json`을 로컬 n8n에 가져오고 HTTP Request 노드 5개에 테스트 전용 Header Auth 자격 증명을 연결한다. JSON의 기본 URL은 `127.0.0.1:8001`이다. 운영 주소를 Git JSON에 임의 반영하지 않는다.
4. 두 `example.test` 계정을 회원가입·로그인하고 커플을 연결한다. 한 계정이 자신의 D-1·당일 알림에 동의한 뒤 테스트 일정을 등록한다. 시험 시간을 앞당길 때는 **격리 DB의 작업 예정 시각만** 조정하고 해당 사실을 증빙에 표시한다. 실제 DB와 실 사용자 주소는 사용하지 않는다.
5. **게시하지 않은** 03을 수동 실행해 n8n 마지막 집계와 SQLite 작업·시도 행을 비교한다. 재실행에서 중복 처리가 없는지 확인한다. 실행 스크린샷·로그에는 인증 키·JWT·개인정보를 넣지 않고 팀의 별도 증빙 저장소에 보관한다.
6. 실제 Gmail 시험은 별도 격리 DB와 `127.0.0.1:8002`에서 수행한다. 사용자 승인 후 로컬 `.env`에만 두 발송 문구의 수신 주소와 `TWO_PICK_N8N_ENABLE_TEST_EMAIL=1`을 설정한다. 04 JSON을 가져와 HTTP·Gmail 자격 증명을 로컬에서 연결하고 **수동 실행만** 한다. 첫 메일의 Gmail 접수 ID·DB `sent`를 확인한 뒤 둘째 메일을 실행한다. 두 번의 실행과 받은편지함을 확인한 뒤 재실행에서 작업 0건을 확인하고 발송 환경변수를 비활성화·수신 주소를 제거한다.

## 2026-11-25 실제 확인 결과

- 01: 로컬 n8n Test Webhook에 실제 HTTP 요청 6건, 예상 상태 200×2/400×2/403×2 일치. **PASS 6/6**.
- 02: 수동 8/8, 가상 2·차단 6·이메일 0. 가상 전용임을 확인해 일시 게시 후 1분 간격 자동 실행 ID 193(15:29:14 KST), 195(15:30:13 KST) 각각 8/8. 확인 후 게시 해제. **가상 실행 PASS**, 실제 발송 아님.
- 03: 로컬 n8n에서 격리 DB 작업 2건(D-1·당일)을 수동 실행하여 **2/2 simulated** 및 시도 각 1건 확인. 동일 데이터 재실행은 처리할 작업 0건. 이후 실제 FastAPI 회원가입·로그인·커플 연결·동의·일정 등록 API를 거친 두 번째 격리 DB 작업 2건도 **2/2 simulated**. 테스트를 위해 두 작업의 `send_at`을 격리 DB에서 현재 시각 10초 전으로 조정했다. 두 건 모두 `succeeded_at=NULL`; 이메일 0건. 03 자동 주기 실행은 미수행, 워크플로 비활성.
- 04 최초 시도: 기존 Gmail OAuth 자격 증명이 만료되어 Gmail 노드에서 중단. **FAIL**, Gmail 접수 ID 없음, 메일 전송 없음. 해당 격리 DB의 작업을 `failed/auth_error`로 기록해 원장을 보존했다. 자격 증명 재연결은 사용자가 직접 수행했다.
- 04 재시험: 새로운 격리 DB에서 두 테스트 계정을 FastAPI API로 가입·로그인·커플 연결하고 한 사용자의 알림 동의·일정 등록으로 만든 당일/D-1 작업 두 건의 `send_at`만 현재 시각 10초 전으로 조정했다. 04를 **수동으로 두 번** 실행해 Gmail 노드와 결과 기록 노드 각각 성공, 작업별 시도 1회·`sent`·접수 ID·성공 시각을 확인했다. Gmail 받은편지함에서 **당일 1통(16:14 KST), D-1 1통(16:15 KST)**의 도착과 승인된 본문을 확인했다. n8n이 본문 끝에 자동 발송 안내 문구를 덧붙였다. 세 번째 실행은 처리할 작업 0건, 이미 처리한 작업과 세 번째 새 작업의 `test_email` 선점은 각각 HTTP 409였다. 추가 메일은 발송하지 않았다. 04는 비활성 상태로 남겼고 테스트 발송 환경 플래그를 끄고 수신 주소를 로컬 `.env`에서 제거했다.
- 기존 `tow_pick.db`는 변경 전 저장소 외부에 SQLite backup API로 백업했다. 백업은 15개 테이블·0개 행·`integrity_check=ok`, 스키마 적용 후 원본은 16개 테이블·0개 행·`integrity_check=ok`였다. 추가된 것은 `notification_dispatch_attempts` 테이블이며 기존 행 수는 유지됐다. 실제 자격 증명·실행 데이터·원본 로그는 Git에 포함하지 않는다.

## WBS 판정과 남은 작업

| WBS | 현재 판정 | 근거/남은 항목 |
|---|---|---|
| 2.6.5 D-1·당일 예약 알림 | **PARTIAL** | 일정 계획과 02의 자동 가상 반복, 03의 수동 DB 연동 확인. 03 운영 예약 연속 실행 미검증 |
| 2.6.6 Gmail 또는 테스트 메일 실제 발송 | **PASS (승인된 테스트 2건)** | n8n Gmail 접수·DB 원장·받은편지함 D-1/당일 각 1통 확인. 운영 서비스 사용자 발송은 범위 밖 |
| 2.6.7 중복 방지·발송 기록·실패 처리 | **PARTIAL** | DB 선점·시도 기록·실메일 시험 중복 차단·인증 실패 보존 확인. 실메일 전송 후 결과 불명 장애 복구는 미검증 |

이번 두 통은 사용자가 **테스트 수신 주소와 D-1·당일 발송 문구**를 승인한 뒤에만 발송했다. 향후 추가 발송에는 별도 승인과 새 격리 시험이 필요하다. 발송 후 결과 저장 장애는 무조건 재발송하지 않고 Gmail·n8n·DB 기록을 대조해야 한다. 운영 정책으로 발송 시각 또는 허용 창을 확정한 적은 없으며, 현재 10분 창은 기존 mock 계약을 재사용한 **시험 가정**이다. 실제 발송 시각, 창, 보존 기간, 키 교체·복구 절차는 팀 결정이 필요하다.
