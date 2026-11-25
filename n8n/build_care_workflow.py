"""Generate the credential-free, inactive local CARE mock dispatch workflow."""

import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

BASE_URL = "http://127.0.0.1:8001"


def node(name, kind, version, x, y, parameters):
    return {"parameters": parameters, "type": kind, "typeVersion": version,
            "position": [x, y], "id": str(uuid5(NAMESPACE_URL, "two-pick-care:" + name)),
            "name": name}


def http(name, x, y, method, path, body=None):
    parameters = {
        "method": method,
        "url": path,
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "options": {"timeout": 5000, "response": {"response": {"responseFormat": "json"}}},
    }
    if body is not None:
        parameters.update({"sendBody": True, "contentType": "json",
                           "specifyBody": "json", "jsonBody": body})
    return node(name, "n8n-nodes-base.httpRequest", 4.2, x, y, parameters)


def code(name, x, y, source):
    return node(name, "n8n-nodes-base.code", 2, x, y,
                {"jsCode": source})


def edge(target, index=0):
    return {"node": target, "type": "main", "index": index}


def one(target):
    return {"main": [[edge(target)]]}


def build():
    nodes = [
        node("1분 주기 확인", "n8n-nodes-base.scheduleTrigger", 1.4, 0, 0,
             {"rule": {"interval": [{"field": "minutes", "minutesInterval": 1}]}}),
        http("발송 예정 작업 조회", 230, 0, "GET",
             BASE_URL + "/internal/notifications/due"),
        code("작업 ID 분리", 460, 0,
             "const ids = $input.first().json.job_ids;\n"
             "if (!Array.isArray(ids)) throw new Error('Invalid due response');\n"
             "return ids.map(id => ({json: {job_id: id}}));"),
        http("발송 작업 선점", 690, 0, "POST",
             "={{ '" + BASE_URL + "/internal/notifications/' + $json.job_id + '/claim' }}"),
        http("발송 직전 조건 확인", 920, 0, "POST",
             "={{ '" + BASE_URL + "/internal/notifications/' + $json.job_id + '/verify' }}"),
        node("발송 가능 여부", "n8n-nodes-base.if", 2.4, 1150, 0, {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "",
                            "typeValidation": "strict", "version": 4},
                "conditions": [{"id": str(uuid5(NAMESPACE_URL, "two-pick-care:eligible")),
                                "leftValue": "={{ $json.eligible }}", "rightValue": "",
                                "operator": {"type": "boolean", "operation": "true",
                                             "singleValue": True}}],
                "combinator": "and",
            }, "options": {},
        }),
        code("테스트 알림 구성", 1380, -120,
             "return $input.all().map(item => ({json: {\n"
             "  job_id: item.json.job_id, attempt: item.json.attempt,\n"
             "  notification_type: item.json.notification_type,\n"
             "  message: item.json.notification_type === 'd1'\n"
             "    ? '내일은 함께 등록한 일정이 있습니다.'\n"
             "    : '오늘은 함께 등록한 일정이 있습니다.',\n"
             "  result: 'simulated', actual_email_sent: false\n"
             "}}));"),
        code("차단 작업 정리", 1380, 120,
             "return $input.all().map(item => ({json: {\n"
             "  job_id: item.json.job_id, attempt: item.json.attempt,\n"
             "  result: 'canceled', actual_email_sent: false\n"
             "}}));"),
        http("가상 발송 결과 기록", 1610, -120, "POST",
             "={{ '" + BASE_URL + "/internal/notifications/' + $json.job_id + '/result' }}",
             "={{ JSON.stringify({attempt: $json.attempt, result: $json.result}) }}"),
        http("차단 결과 기록", 1610, 120, "POST",
             "={{ '" + BASE_URL + "/internal/notifications/' + $json.job_id + '/result' }}",
             "={{ JSON.stringify({attempt: $json.attempt, result: $json.result}) }}"),
        node("처리 결과 병합", "n8n-nodes-base.merge", 3.2, 1840, 0,
             {"mode": "append"}),
        code("실행 결과 집계", 2070, 0,
             "const rows = $input.all().map(item => item.json);\n"
             "return [{json: {mode: 'mock', total: rows.length,\n"
             "  simulated: rows.filter(r => r.status === 'simulated').length,\n"
             "  blocked: rows.filter(r => r.status === 'canceled').length,\n"
             "  actual_emails_sent: 0,\n"
             "  job_ids: rows.map(r => r.job_id),\n"
             "  completed_at: new Date().toISOString()\n"
             "}}];"),
    ]
    connections = {
        "1분 주기 확인": one("발송 예정 작업 조회"),
        "발송 예정 작업 조회": one("작업 ID 분리"),
        "작업 ID 분리": one("발송 작업 선점"),
        "발송 작업 선점": one("발송 직전 조건 확인"),
        "발송 직전 조건 확인": one("발송 가능 여부"),
        "발송 가능 여부": {"main": [[edge("테스트 알림 구성")],
                                     [edge("차단 작업 정리")]]},
        "테스트 알림 구성": one("가상 발송 결과 기록"),
        "차단 작업 정리": one("차단 결과 기록"),
        "가상 발송 결과 기록": {"main": [[edge("처리 결과 병합", 0)]]},
        "차단 결과 기록": {"main": [[edge("처리 결과 병합", 1)]]},
        "처리 결과 병합": one("실행 결과 집계"),
    }
    return {"name": "TWO PICK - 03 CARE Notification Dispatch",
            "nodes": nodes, "pinData": {}, "connections": connections,
            "active": False,
            "settings": {"executionOrder": "v1", "timezone": "Asia/Seoul",
                         "saveDataSuccessExecution": "all",
                         "saveDataErrorExecution": "all"},
            "tags": []}


if __name__ == "__main__":
    target = Path(__file__).parent / "workflows" / "TWO_PICK_03_CARE_NOTIFICATION_DISPATCH.json"
    target.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(target)
