# TWO-PICK FastAPI·n8n 테스트 Webhook 연동 — 2026-11-25

- 기준: PR #25가 병합된 `origin/main` `a9170db4cfde9935e560093473d27f84e4adfdb2`
- WBS: 2.6.1, 2.6.2
- 범위: 로컬 n8n **테스트 Webhook**에 격리 DB의 가상 알림 1건을 전송하고 응답 검증
- 제외: FastAPI 공개 발송 endpoint, 운영 scheduler, 실제 메일, 작업 `sent` 갱신, 자동 재시도

## 이벤트 목록과 경계

| 이벤트 | 현재 처리 | 상태 |
|---|---|---|
| 커플 일정 등록·수정·삭제 | FastAPI/SQLite에 일정과 revision 보존, 미발송 예약 갱신 | 기존 구현 |
| 개인별 D-1·당일 동의·철회 | 사용자별 설정 및 pending 작업 취소 | 기존 구현 |
| `pending` 알림 작업의 테스트 payload 생성 | 격리 SQLite의 가상 사용자·일정·작업에서 `prepare_mock_payload` 호출 | 이번 통합 시험 |
| Header Auth POST와 n8n 응답 확인 | `n8n.webhook_client`와 one-shot CLI, 로컬 Test URL만 허용 | 이번 통합 시험 |
| 작업 선점·상태 `sent` 기록 | 테스트 스크립트에서 수행하지 않음 | planned |
| Gmail/실제 알림 전송, 반복 scheduler, 자동 재시도 | 수행하지 않음 | planned |

이 스크립트는 FastAPI의 새로운 HTTP endpoint가 아니다. `notification_logic.py`의 payload 생성 규칙을 재사용하되 기존 `tow_pick.db`에 접근하지 않는다. 실제 사용자 동의·수신 주소 대신 임시 SQLite의 가상 사용자 `n8n-smoke@example.test`와 동의한 테스트 설정을 사용한다. 실행 후 임시 DB는 삭제된다.

## JSON·HTTP 계약

| 항목 | 값 |
|---|---|
| Method/URL | `POST ${TWO_PICK_N8N_WEBHOOK_URL}`; 이 시험은 `http://localhost:5678/webhook-test/two-pick-test`만 허용 |
| 인증 | `X-Two-Pick-Secret: <환경변수 값>`; 값은 `TWO_PICK_N8N_WEBHOOK_SECRET`에서만 읽음 |
| Content-Type | `application/json` |
| 요청 | `job_id`, `schedule_id`, `notification_type`(`d1`/`day_of`), `occurrence_date`, `send_at`(UTC ISO 8601), `recipient_email`(`example.test`만), `dedupe_key`(SHA-256), `message` |
| 정상 | HTTP 200, JSON `success=true`, `status_code=200` |
| 입력 오류 | HTTP 400, JSON `success=false`, `status_code=400`, `errors` |
| 인증 오류 | HTTP 403; n8n 인증 단계에서 거부하므로 응답 본문 형태에 의존하지 않음 |

요청 예시는 [`n8n/README.md`](../n8n/README.md)에 있다. 키, JWT, 비밀번호, 실제 개인 이메일, 상대방 정보, 개인별 비공개 조건, 전체 User/Couple 객체는 payload에 포함하지 않는다. 테스트 클라이언트는 `example.test` 이외의 주소와 금지 필드를 로컬에서 차단한다. n8n 워크플로는 입력 형식을 다시 검사한다. 응답 검증은 HTTP 상태와 `success`/`status_code` 일치를 확인하고 원문 응답이나 인증 헤더를 로그에 남기지 않는다.

## 알림 조건표

| 조건 | 예약/테스트 payload | 실제 발송 |
|---|---|---|
| 본인 동의 `false` 또는 해당 종류 꺼짐 | 생성·준비 금지 | 없음 |
| 동의 후 일정 revision 일치, pending, 수신자 같은 커플 | 예정 시각부터 10분 이내에만 준비 가능 | 이번 단계에서는 없음 |
| 동의 철회·일정 변경·삭제 | pending 취소 또는 발송 전 재확인 거부 | 없음 |
| 주소 없음·실제 사용자 주소 | 이 테스트 스크립트에서 거부 | 없음 |
| 동일 작업 재요청 | DB dedupe key는 기존 예약 단계에서 unique | 발송 단계 멱등성은 미구현 |

## 오류와 재시도 정책

| 상황 | 현재 시험 클라이언트 처리 | 후속 운영 정책 |
|---|---|---|
| HTTP 200 | 응답 JSON 계약 확인 후 PASS | 실제 발송 성공으로 기록하지 않음 |
| HTTP 400 | 입력 오류로 분류; Body/schema 확인 | payload 계약 수정 전 재시도 금지 |
| HTTP 403 | Header Auth 오류로 분류 | credential 재설정 확인; 키/헤더 로그 금지 |
| HTTP 404 | 예상하지 않은 Webhook 응답으로 FAIL | Test URL 대기 상태·경로 확인 후 수동 재시도 |
| 연결 실패 | 별도 `WebhookConnectionError` | 로컬 서버 상태 확인 후 수동 재시도 |
| 시간 초과 | 별도 `WebhookTimeoutError` | 성공 여부 불명확하므로 자동 재전송 금지 |
| 다른 HTTP 상태·잘못된 JSON | `WebhookResponseError` | 응답 계약 확인 후 수동 재시도 |

요청 시간 제한은 기본 5초다. 이번 단계는 **자동 재시도하지 않는다**. 향후 실제 전송 경로는 한 작업을 원자적으로 선점하고, 성공·실패·불명 상태를 같은 dedupe key에 기록하며, 동의 철회와 일정 revision을 발송 직전에 다시 확인해야 한다. 타임아웃 후 결과가 불명확하면 n8n 실행 기록을 확인하기 전 재전송하지 않는다.

## 실행·검증 및 후속 인계

1. Git에 포함되지 않는 `.env`에 `TWO_PICK_N8N_WEBHOOK_SECRET`을 설정한다. URL은 `TWO_PICK_N8N_WEBHOOK_URL` 환경변수로 설정한다. 키를 명령줄·문서·Git에 넣지 않는다.
2. n8n에서 `TWO PICK - 01 Webhook Test`의 Header Auth credential을 확인하고 **Listen for test event**를 켠다. Test URL은 대기 중인 요청에만 응답하므로 각 live 실행 직전에 다시 켠다.
3. `python -m n8n.test_webhook --case valid --live`를 실행한다. 추가 오류 케이스는 README의 개별 명령을 사용한다. 출력은 케이스·HTTP 상태만 표시하며 키와 요청 원문을 출력하지 않는다.
4. Python 전체 테스트·공동결정 Node·PET DOCK USB 회귀를 실행한다. 실제 Webhook PASS는 **실제 HTTP 200 응답을 관찰했을 때만** 기록한다.

### 이번 실행 결과

| 항목 | 결과 | 범위 |
|---|---|---|
| 첫 실제 요청 | FAIL, HTTP 404 | n8n Test Webhook 대기 상태를 다시 확인하기 전의 요청. 원인은 단정하지 않음 |
| 재대기 상태 확인 후 실제 요청 | **PASS, HTTP 200, `success=true`** | 임시 SQLite의 가상 사용자·알림 작업, `example.test` 주소, 로컬 n8n Test URL |
| Webhook 클라이언트 Mock 자동 테스트 | **7/7 PASS** | 정상·400·403·연결 실패·시간 초과·응답 계약 오류·개인정보 차단 |
| Python 전체 회귀 | **59/59 PASS** | 기존 52개와 신규 7개 |
| 공동결정 Node / PET DOCK USB 회귀 | **10/10 PASS / PASS** | 실물 장치 시험 아님 |
| 실제 Gmail, 운영 발송 원장·재시도 | **NOT TESTED / 미구현** | 이 테스트에서 작업을 `sent`로 바꾸지 않음 |

이 결과는 이번 새 백엔드→n8n **정상 1건**의 실제 통합 확인이다. 기존 Webhook 자체의 6/6 시험은 사용자 제공 결과이며 이번 스크립트로 6개 전부를 다시 실행했다고 표시하지 않는다. 실제 키·요청 원문·실행 데이터는 Git에 포함하지 않는다.

후속 구현 담당자는 실제 수신 주소 확인, 사용자 동의의 발송 직전 재검증, 작업 선점/멱등성, n8n 인증 키의 운영 비밀 저장소 관리, Gmail 발송 및 결과 원장, 제한적 재시도를 별도 변경으로 구현해야 한다. 프론트엔드나 Arduino가 n8n Webhook을 직접 호출하지 않는다.
