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
