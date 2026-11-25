# 프론트엔드 API 연동 현황

작성 기준: 2026-11-25. 최신 `docs/API_CONTRACT.md`를 기준으로 실제 API와 임시 데이터를 구분한다. API 오류가 발생해도 Mock으로 조용히 대체하지 않으며 사용자에게 오류 상태를 표시한다.

## 실제 API 연동 완료

| 화면/기능 | API | 상태 |
|---|---|---|
| 로그인·회원가입·로그아웃 | 인증 API | 완료 |
| 커플 초대·연결·24시간 만료·재발급 | `POST /couples`, `POST /couples/join`, `POST /couples/invite-code`, `GET /couples/me` | 완료 |
| 공동결정·비공개 조건·추천·수동 후보·양측 승인 | `/decisions` 계열 | 완료 |
| 확정 결정 기록 및 상세 | `GET /decision-confirmations`, 필요 시 `GET /decisions/{id}` | 완료 |
| 본인 만족도 조회·작성·수정 | `GET/PUT /decisions/{id}/feedback/me` | 완료 |
| 기념일·일정·반복 캘린더 | `GET/POST /schedules`, `GET/PUT/DELETE /schedules/{id}` | 완료 |
| 본인 알림 동의·철회 및 예약 설정 | `GET/PUT /notifications/settings/me` | 완료 |
| 대시보드 | 결정·확정 기록·일정·커플·본인 알림 설정 API 조합 | 완료 |
| PET DOCK 연결 상태 | 브라우저 Web Serial/Web Bluetooth | 서버 API 불필요 |

모든 신규 요청은 기존 JWT 인증을 사용한다. 401, 403, 404, 409, 410, 422 응답은 공통 API 오류 처리와 화면별 안내 문구로 구분한다.

## 아직 임시 데이터 또는 로컬 저장을 사용하는 기능

| 기능 | 현재 소스 | 필요한 백엔드 |
|---|---|---|
| 알림 센터 목록·읽음 상태 | Mock + 이 기기 읽음 상태 | 알림 목록·개별 읽음·전체 읽음 API |
| OUR PET 레벨·경험치·성장 상태 | Mock | 펫 상태 조회 API |
| 개인 표시 이름 수정 | 이 기기 저장 | 본인 프로필 수정 API |
| 실제 이메일 알림 발송 | 미제공으로 명시 | n8n/Gmail 발송 worker 및 결과 정책 |

임시 기능은 `frontend/feature-data.js`의 `TwoPickFeatureData.sources`에서 `mock` 또는 `local`로 표시한다. 실제 API 연동 기능은 `api`로 표시한다.

## 추가로 필요한 API 제안

### 알림 센터

- `GET /notifications?cursor=<cursor>`
- `POST /notifications/{notification_id}/read`
- `POST /notifications/read-all`
- 사용자별 읽음 상태를 저장하고 비공개 조건 내용은 알림에 포함하지 않는다.

### OUR PET

- `GET /pets/me`
- 최소 응답: `name`, `level`, `experience`, `next_level_experience`, `status`, `updated_at`
- 캐릭터·공간 에셋 계약은 별도 확정이 필요하다. 하드웨어 버튼은 공동결정 승인 API와 연결하지 않는다.

### 프로필

- `PATCH /users/me` 요청: `{ "nickname": "새 이름" }`
- 계정 삭제는 재인증·복구 정책 합의 후 별도 설계한다.

## 연동 원칙

- `docs/API_CONTRACT.md`의 실제 필드명과 오류 코드를 따른다.
- 만족도는 본인 값만 조회·표시하며 상대방 값, 평균, 합계를 노출하지 않는다.
- 일정은 `Asia/Seoul` 현지 날짜·시간과 반복 규칙을 그대로 표시한다.
- 알림 설정 저장을 실제 발송 완료로 표현하지 않는다.
- 시연용 추천 가격은 확인된 실제 가격처럼 표시하지 않는다.
- 백엔드가 없는 기능은 Mock 또는 이 기기 저장임을 화면에 표시한다.
