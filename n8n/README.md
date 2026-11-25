# TWO-PICK n8n 워크플로

## 01 Webhook 입력 검증 테스트

[`workflows/TWO_PICK_01_WEBHOOK_TEST.json`](workflows/TWO_PICK_01_WEBHOOK_TEST.json)은 **POST `two-pick-test`** Webhook → 입력 검증 Code → Respond to Webhook의 3개 노드로 구성된다. Header Auth를 통과한 요청의 필수 필드와 허용 필드를 검사해 정상 요청에는 HTTP 200, 입력 오류에는 HTTP 400을 반환한다. 인증 키 누락·불일치 요청은 Webhook 인증 단계에서 거부된다. 이 워크플로는 이메일을 보내거나 TWO-PICK DB·알림 동의 상태를 조회하지 않는다.

Git에 등록한 JSON은 원본 GitHub 등록용 파일과 동일하며 `active: false`, 빈 `pinData`, 자격 증명 값 없음 상태다. **실제 키, 수신 데이터, 개인 이메일, 실행 로그는 저장소에 추가하지 않는다.**

### 가져오기 및 Header Auth 재설정

1. n8n에서 새 워크플로를 열고 편집기 상단의 워크플로 메뉴에서 **Import from File**을 선택한 뒤 `workflows/TWO_PICK_01_WEBHOOK_TEST.json`을 가져온다.
2. `Webhook 요청 수신` 노드가 `POST`, 경로 `two-pick-test`, 인증 `Header Auth`, 응답 방식 `Respond to Webhook`인지 확인한다.
3. 해당 노드의 **Credential for Header Auth**에서 테스트 환경용 Header Auth credential을 새로 만들거나 선택한다. **Name**에는 호출자가 보내는 인증 헤더 이름을, **Value**에는 별도 비밀 저장소에서 관리하는 테스트 키를 넣는다. JSON에는 기존 credential이 포함되지 않으므로 가져온 환경마다 다시 연결해야 한다. 헤더 이름 자체는 이 JSON에 지정되지 않았으며, 기존 시험에서 쓴 이름을 확인하거나 팀에서 새 이름을 정해 호출자와 일치시킨다.
4. 저장 후 Webhook 노드의 **Test URL**을 확인하고 **Listen for test event**를 켠 상태에서 요청한다. 실제 서비스 URL은 별도로 게시한 워크플로의 **Production URL**을 사용한다. 이 파일은 기본적으로 비활성 상태이므로 테스트만을 위해 게시하거나 활성화할 필요는 없다.

메뉴·Test/Production URL과 인증 설정은 [n8n 가져오기 안내](https://docs.n8n.io/build/manage-workflows/export-and-import.md), [Webhook 노드 안내](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook.md), [Webhook Header Auth credential 안내](https://docs.n8n.io/integrations/builtin/credentials/webhook.md)를 따른다.

### 요청 형식

`Content-Type: application/json`으로 다음 **테스트 데이터**를 Test URL에 POST한다. 인증 헤더의 이름과 값은 위에서 설정한 credential에 맞춘다. 아래의 주소는 전송 가능한 실제 수신 주소가 아닌 예약된 테스트 도메인이다.

```json
{
  "job_id": 1,
  "schedule_id": 2,
  "notification_type": "d1",
  "occurrence_date": "2026-12-01",
  "send_at": "2026-11-30T00:00:00Z",
  "recipient_email": "demo@example.test",
  "dedupe_key": "0000000000000000000000000000000000000000000000000000000000000000",
  "message": "등록한 일정 알림입니다."
}
```

필수 필드는 위 8개뿐이다. `notification_type`은 `d1` 또는 `day_of`, ID는 양의 정수, `recipient_email`은 `example.test` 주소, `dedupe_key`는 64자리 소문자 16진수여야 한다. 필드 누락·추가 또는 값 형식 오류는 400으로 검사한다. 응답에는 `success`, `service`, `mode`, `status_code`, `message`, `errors`, `received_at`이 포함되며 요청 Body 원문은 반환하지 않는다.

### 재현 순서와 증빙

| 테스트 | 요청 변경 | 기대 HTTP |
|---|---|---:|
| 정상 데이터 | 위 Body와 올바른 Header Auth | 200 |
| 필수 항목 누락 | 예: `schedule_id` 삭제 | 400 |
| 허용되지 않은 필드 | 예: `private_condition` 추가 | 400 |
| 인증 키 누락 | 인증 헤더 제거 | 403 |
| 정상 인증 키 | 올바른 헤더와 값 | 200 |
| 잘못된 인증 키 | 값만 다른 테스트 키 | 403 |

2026-11-25 실제 n8n 시험의 **사용자 제공 결과는 6/6 PASS**다. 이 저장소에는 당시 HTTP 원본 로그나 n8n 실행 증빙을 포함하지 않는다. 새 환경에서 가져온 후에는 위 6개 요청을 다시 실행하고 상태 코드, 마스킹한 응답, n8n 실행 시각을 팀의 증빙 저장소에 기록한다. 인증 키와 개인정보가 포함된 요청 헤더·실행 데이터·스크린샷은 Git에 올리지 않는다.

### 운영 연결 전 확인

현재 워크플로는 입력 형식 테스트다. 이 결과가 백엔드의 사용자별 알림 동의 확인, 작업 원장 중복 발송 방지, 재시도, Gmail 발송 검증을 대신하지 않는다. 실제 전송 경로는 [`docs/NOTIFICATION_PRIVACY.md`](../docs/NOTIFICATION_PRIVACY.md)의 동의·최소 전송 규칙과 백엔드 발송 직전 재검증을 구현한 뒤 별도로 연결한다.

## FastAPI 알림 기반 → 로컬 n8n Test URL 연동

`python -m n8n.test_webhook`은 기존 `notification_logic.prepare_mock_payload`로 **임시 SQLite의 가상 알림 작업**을 준비하고, 명시적으로 `--live`를 붙였을 때만 n8n에 한 건 전송한다. 실제 `tow_pick.db`, 실제 사용자 이메일, Gmail, 작업 `sent` 상태는 사용하지 않는다. 이 명령은 FastAPI의 공개 발송 API가 아니다. 상세 계약과 후속 과제는 [`N8N_WEBHOOK_INTEGRATION_20261125.md`](../docs/N8N_WEBHOOK_INTEGRATION_20261125.md)에 있다.

1. 로컬 n8n 서버와 `TWO PICK - 01 Webhook Test` 워크플로의 `X-Two-Pick-Secret` Header Auth credential을 준비한다. **인증 값은 채팅·Git·명령줄 인자로 적지 않는다.** Git에서 제외되는 프로젝트 `.env`에 `TWO_PICK_N8N_WEBHOOK_SECRET=<로컬 테스트 키>`를 설정한다.
2. 같은 `.env` 또는 실행할 셸 환경에 `TWO_PICK_N8N_WEBHOOK_URL=http://localhost:5678/webhook-test/two-pick-test`를 설정한다. 클라이언트는 이 로컬 Test URL만 허용한다.
3. 네트워크 요청 없이 가상 DB·payload를 확인하려면 저장소 루트에서 `python -m n8n.test_webhook --case valid`를 실행한다.
4. n8n Webhook 노드에서 **Listen for test event**를 누른 **직후** 아래 명령을 한 개 실행한다. Test URL은 한 번의 요청 후 또는 대기 시간 종료 후 다시 대기해야 하므로 **각 live 명령 전에 다시 누른다.**

```powershell
python -m n8n.test_webhook --case valid --live
python -m n8n.test_webhook --case missing-field --live
python -m n8n.test_webhook --case unexpected-field --live
python -m n8n.test_webhook --case missing-auth --live
python -m n8n.test_webhook --case wrong-auth --live
```

Windows 가상환경에서는 `python` 대신 `.\.venv\Scripts\python.exe`를 사용할 수 있다. 기대 상태는 순서대로 200, 400, 400, 403, 403이다. 기존 6개 시나리오의 두 번째 정상 인증 키 200은 `valid`를 다시 실행하면 된다. 404는 Test URL 대기 종료나 경로 오류 가능성을 확인해야 하는 **FAIL**이며 PASS로 세지 않는다. 연결 실패·시간 초과도 FAIL로 기록하고 자동 재시도하지 않는다. 인증 키나 응답 원문을 Git 증빙에 포함하지 않는다.

## 02 Notification Scheduler 가상 테스트

[`workflows/TWO_PICK_02_NOTIFICATION_SCHEDULER.json`](workflows/TWO_PICK_02_NOTIFICATION_SCHEDULER.json)은 Schedule Trigger(1분 설정) → 가상 알림 데이터 생성 → 발송 조건 검증 → IF 분기 → 가상 발송 처리 또는 차단 기록 → Merge → 결과 집계의 **8개 노드**로 구성된다. 파일은 `active: false`이며 가져온 뒤에도 **활성화하지 않는다**. 예약 실행 설정은 구조 확인용이고, 실제 예약 실행의 지속 동작은 검증되지 않았다. DB, FastAPI, Gmail, 실제 이메일 발송 노드는 없다.

### 가져오기와 수동 실행

1. n8n 편집기의 워크플로 메뉴에서 **Import from File**로 `workflows/TWO_PICK_02_NOTIFICATION_SCHEDULER.json`을 가져온다. 기존 01 Webhook 워크플로와 별개로 보관한다.
2. 워크플로 이름과 8개 노드의 연결, `Asia/Seoul` 시간대, `active: false`를 확인한다. 자격 증명과 테스트 실행 데이터는 JSON에 포함되지 않는다.
3. 워크플로를 게시·활성화하지 않은 상태에서 **Execute workflow**로 한 번 수동 실행한다. 마지막 `최종 테스트 결과 집계` 노드의 `overall_result`, `total_tests`, `passed_tests`, `simulated_deliveries`, `blocked_notifications`, `actual_emails_sent`를 확인한다.
4. 실제 사용자의 데이터나 수신 주소를 입력하지 않는다. 이 워크플로의 수신 주소 `test@example.test`는 테스트 전용이며, `SIMULATED_SUCCESS`는 이메일 발송 성공을 뜻하지 않는다.

### 가상 데이터와 결과

생성 노드는 실행 시각을 기준으로 `send_at`과 한국 날짜 `occurrence_date`를 만들고, 검증 노드는 동의·알림 종류·작업 상태·일정 revision·발송 시각(예정 시각부터 10분 이내)을 검사한다. 테스트에 사용한 `status: sent`는 **가상 입력값**일 뿐 백엔드 알림 작업을 변경하지 않는다.

| 시나리오 | 기대 결과 |
| --- | --- |
| D-1 정상 알림 | `SIMULATED_SUCCESS` |
| 당일 정상 알림 | `SIMULATED_SUCCESS` |
| 알림 미동의 | `BLOCKED` |
| 발송 시간 미도달 | `BLOCKED` |
| 이미 발송된 알림 | `BLOCKED` |
| 발송 허용 시간 초과 | `BLOCKED` |
| 일정 수정으로 무효화 | `BLOCKED` |
| 알림 종류 비활성화 | `BLOCKED` |

2026-11-25 n8n 수동 가상 테스트의 **사용자 제공 결과는 8/8 PASS**다. 가상 발송 2건, 정상 차단 6건, 실제 이메일 0건이다. 저장소에는 당시 실행 로그와 개인 데이터를 넣지 않는다. 새 환경에서 재현할 때는 각 항목의 `test_result`와 집계값을 확인하고, 민감정보를 제거한 증빙을 별도 저장소에 보관한다.

이 시험은 **실제 예약 실행, DB 작업 조회·갱신, 발송 동의의 운영 시점 재검증, Gmail 발송, 영속적인 중복 발송 방지**를 검증하지 않는다. 이 항목들은 후속 구현·실물 검증 전까지 완료로 처리하지 않는다.
