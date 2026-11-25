# 신규 프론트 화면 API 연동 준비

작성 기준: 2026-11-25. 이 문서는 프론트엔드가 필요로 하는 제안 계약이며, 백엔드 합의 전에는 호출하지 않는다. 현재 구현된 인증·커플·공동결정·확정 기록은 실제 API를 사용한다. 일정, 알림, 만족도, OUR PET 성장, 프로필 수정은 화면에 **테스트 데이터/이 기기 저장**으로 표시한다.

## 데이터 소스 현황

| 화면/기능 | 현재 소스 | 연동 상태 |
|---|---|---|
| 로그인·회원가입·커플 연결 | API | 연동 완료 |
| 공동결정·조건·추천·승인 | API | 연동 완료 |
| 최근 확정 결정 | `GET /decision-confirmations` | 연동 완료 |
| 만족도 평가 | Mock/localStorage | API 필요 |
| 기념일·커플 일정 | Mock/localStorage | API 필요 |
| 알림 센터 | Mock/localStorage | API 필요 |
| OUR PET 레벨·경험치 | Mock | API 필요 |
| 개인 프로필·알림 설정 | localStorage | API 필요 |
| PET DOCK 연결 상태 | 브라우저 Web Serial/Bluetooth | 서버 API 불필요 |

## 제안 API 계약

### 만족도

- `PUT /decision-confirmations/{confirmation_id}/satisfaction`
- 요청: `{ "score": 1 }` (`1..5`)
- 응답: `{ "confirmation_id": 10, "score": 1, "updated_at": "ISO-8601" }`
- 권한: 해당 커플 구성원. 두 사람 점수를 분리 저장하며 상대방 점수 공개 여부는 백엔드/기획 합의가 필요하다.

### 일정

- `GET /schedules?from=YYYY-MM-DD&to=YYYY-MM-DD`
- `POST /schedules` 요청: `{ "title": "첫 만남 기념일", "date": "2026-11-26", "type": "anniversary" }`
- `DELETE /schedules/{schedule_id}`
- 목록 항목: `{ "id": 1, "title": "...", "date": "YYYY-MM-DD", "type": "anniversary|date|todo", "created_by": 1 }`
- 권한: 현재 커플 데이터만 조회·변경. 제목 1~100자, 날짜 유효성, type enum 검증 필요.

### 알림

- `GET /notifications?cursor=<cursor>`
- `POST /notifications/{notification_id}/read`
- `POST /notifications/read-all`
- 목록 응답: `{ "items": [{ "id": 1, "type": "condition|approval|confirmed|schedule", "title": "...", "message": "...", "created_at": "ISO-8601", "read_at": null, "route": "decision" }], "next_cursor": null }`
- 알림은 사용자별 읽음 상태를 저장하며 비공개 조건 내용 자체는 메시지에 포함하지 않는다.

### OUR PET

- `GET /pets/me`
- 응답: `{ "name": "OUR PET", "level": 3, "experience": 65, "next_level_experience": 100, "status": "happy", "updated_at": "ISO-8601" }`
- 캐릭터/공간 에셋 계약은 확정 전이며 프론트는 현재 CSS 임시 에셋만 사용한다. 하드웨어 버튼을 공동결정 승인 API와 연결하지 않는다.

### 프로필·환경 설정

- `PATCH /users/me` 요청: `{ "nickname": "새 이름" }`, 응답은 기존 `UserRead`
- `GET /users/me/preferences`
- `PUT /users/me/preferences` 요청/응답: `{ "decision_notifications": true, "schedule_notifications": true, "pet_notifications": true }`
- 계정 삭제 API는 본인 재인증·복구 정책 합의 후 별도 설계한다.

## 프론트 연동 방법

Mock 원본은 `frontend/feature-data.js` 한곳에 있고 `TwoPickFeatureData.sources`로 `api`, `mock`, `local`을 구분한다. 백엔드 계약이 확정되면 해당 기능만 API adapter로 교체하고, 화면 렌더링과 검증 로직은 유지한다. 응답 실패 시 기존 Mock으로 조용히 대체하지 말고 오류 상태를 표시해 실제 장애가 테스트 데이터에 가려지지 않도록 한다.
