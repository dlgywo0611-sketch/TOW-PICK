"""Generate an inactive, credential-free two-message Gmail test workflow."""

import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from n8n.build_care_workflow import code, edge, http, node, one

BASE_URL = "http://127.0.0.1:8002"


def build():
    nodes = [
        node("수동 실행 전용", "n8n-nodes-base.manualTrigger", 1, 0, 0, {}),
        http("테스트 작업 조회", 230, 0, "GET",
             BASE_URL + "/internal/notifications/due"),
        code("한 작업만 선택", 460, 0,
             "const ids = $input.first().json.job_ids;\n"
             "if (!Array.isArray(ids)) throw new Error('Invalid due response');\n"
             "return ids.length ? [{json: {job_id: ids[0]}}] : [];"),
        http("승인된 테스트 수신자 선점", 690, 0, "POST",
             "={{ '" + BASE_URL + "/internal/notifications/' + $json.job_id + '/claim' }}",
             "={{ JSON.stringify({mode: 'test_email'}) }}"),
        http("발송 직전 동의 재확인", 920, 0, "POST",
             "={{ '" + BASE_URL + "/internal/notifications/' + $json.job_id + '/verify' }}"),
        node("발송 가능 여부", "n8n-nodes-base.if", 2.4, 1150, 0, {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "",
                            "typeValidation": "strict", "version": 4},
                "conditions": [{"id": str(uuid5(NAMESPACE_URL, "two-pick-email:eligible")),
                                "leftValue": "={{ $json.eligible }}", "rightValue": "",
                                "operator": {"type": "boolean", "operation": "true",
                                             "singleValue": True}}],
                "combinator": "and",
            }, "options": {},
        }),
        node("승인된 주소에만 Gmail 발송", "n8n-nodes-base.gmail", 2.2,
             1380, -120, {
                 "resource": "message", "operation": "send",
                 "authentication": "oAuth2",
                 "sendTo": "={{ $json.recipient_email }}",
                 "subject": "TWO PICK 일정 알림 (테스트)",
                 "emailType": "text",
                 "message": "={{ $json.notification_type === 'd1' "
                            "? '내일은 함께 등록한 일정이 있습니다.' "
                            ": '오늘은 함께 등록한 일정이 있습니다.' }}",
                 "options": {},
             }),
        code("Gmail 접수 ID 추출", 1610, -120,
             "const sent = $input.first().json;\n"
             "const job = $('발송 직전 동의 재확인').first().json;\n"
             "if (!sent.id) throw new Error('Gmail receipt missing');\n"
             "return [{json: {job_id: job.job_id, attempt: job.attempt, "
             "provider_message_id: sent.id}}];"),
        http("발송 성공 원장 기록", 1840, -120, "POST",
             "={{ '" + BASE_URL + "/internal/notifications/' + $json.job_id + '/result' }}",
             "={{ JSON.stringify({attempt: $json.attempt, result: 'sent', "
             "provider_message_id: $json.provider_message_id}) }}"),
        code("차단 작업 정리", 1380, 120,
             "return $input.all().map(item => ({json: {job_id: item.json.job_id, "
             "attempt: item.json.attempt}}));"),
        http("차단 원장 기록", 1610, 120, "POST",
             "={{ '" + BASE_URL + "/internal/notifications/' + $json.job_id + '/result' }}",
             "={{ JSON.stringify({attempt: $json.attempt, result: 'canceled'}) }}"),
    ]
    connections = {
        "수동 실행 전용": one("테스트 작업 조회"),
        "테스트 작업 조회": one("한 작업만 선택"),
        "한 작업만 선택": one("승인된 테스트 수신자 선점"),
        "승인된 테스트 수신자 선점": one("발송 직전 동의 재확인"),
        "발송 직전 동의 재확인": one("발송 가능 여부"),
        "발송 가능 여부": {"main": [[edge("승인된 주소에만 Gmail 발송")],
                                     [edge("차단 작업 정리")]]},
        "승인된 주소에만 Gmail 발송": one("Gmail 접수 ID 추출"),
        "Gmail 접수 ID 추출": one("발송 성공 원장 기록"),
        "차단 작업 정리": one("차단 원장 기록"),
    }
    return {"name": "TWO PICK - 04 Approved Gmail Test",
            "nodes": nodes, "pinData": {}, "connections": connections,
            "active": False,
            "settings": {"executionOrder": "v1", "timezone": "Asia/Seoul",
                         "saveDataSuccessExecution": "all",
                         "saveDataErrorExecution": "all"},
            "tags": []}


if __name__ == "__main__":
    target = Path(__file__).parent / "workflows" / "TWO_PICK_04_APPROVED_GMAIL_TEST.json"
    target.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(target)
