# TWO-PICK 백엔드 검증 및 연동 메모 — 2026-11-25

- 기준: `origin/main` `31ea448`에서 분기한 `feature/backend-validation-20261125`
- WBS 원담당: 김해인 / 당일 실제 수행: 이효재(PM, 임시 대행)
- 검증 범위: 2.1.2, 3.1.1, 2.1.4, 2.1.6, 2.2.10; 부분 구현: 2.2.14

## 실행 기준선

격리된 SQLite 메모리 DB에서 기존 Python 테스트 32개를 실행해 모두 통과했다. 별도 임시 디렉터리의 SQLite DB로 FastAPI를 실행해 `/health`, `/docs`, `/app`에서 HTTP 200을 확인했다. 이 확인은 실제 브라우저 조작이나 운영 DB 검증을 의미하지 않는다. 기존 `tow_pick.db`는 삭제하지 않았고 신규 테이블 추가 전에 작업공간 내 백업본을 만들었다. 백업본은 Git에 포함하지 않는다.

## 프론트엔드 연결

모든 보호 API는 `Authorization: Bearer <JWT>`가 필요하다. `POST /token`은 JSON이 아닌 form의 `username`(이메일), `password`를 받는다. JWT 원문을 화면·로그·증빙에 기록하지 않는다.

| 기능 | 호출 | 화면 처리 |
|---|---|---|
| 내 조건 | `PUT/GET /decisions/{decision_id}/conditions/me` | 사용자 본인의 조건만 표시. 후보 생성 후 PUT은 409 |
| 제출 여부 | `GET /decisions/{decision_id}/conditions/status` | 상대의 제출 boolean만 표시, 예산·시간·취향은 표시하지 않음 |
| 추천 | `POST /decisions/{decision_id}/recommendations` | 양측 조건 선행, 결정당 평가 1회. 상세 body는 `API_CONTRACT.md`의 P0 추천 계약 참조 |
| 추천 실패 | 같은 POST의 409 `No mutually suitable option; try a manual candidate` | 적합 후보가 없음을 안내하고 수동 Candidate 등록 경로 제공. 재호출하면 409 `Recommendation already attempted for this decision` |
| 수동 후보 | `POST /decisions/{decision_id}/candidates` | 양측 조건 제출 후 허용. 추천 실패 후에도 가능 |
| 확정 이력 | `GET /decision-confirmations` | 현재 커플의 기록만 표시. 과거 데이터의 기록 없는 confirmed Decision은 기존 `/decisions` 조회로 표시 |

추천 실패 응답에는 개인 조건 원문, 개인별 점수, 탈락 이유가 없다. 실패 후 조건 수정과 재추천은 반복 역추정 가능성 때문에 현재 허용하지 않는다. WBS의 재입력 안내와 충돌하는 UX는 팀장 정책 결정 후 별도 구현한다. 시연용 후보의 가격·시간은 실제 예약 가능성 검증값이 아니다.

## API 예시

```http
GET /decision-confirmations
Authorization: Bearer <redacted-jwt>
```

```json
[{"id": 1, "decision_id": 100, "candidate_id": 501,
  "candidate_version": 2, "content_snapshot": "초밥",
  "confirmed_at": "2026-11-25T09:00:00"}]
```

인증이 없거나 무효면 401, 커플 미가입이면 409다. 상대 커플의 기록은 목록에 포함되지 않는다. 현재 API 계약의 요청·응답 필드와 상태 코드는 `API_CONTRACT.md`를 기준으로 한다.

## 1차 작업 당시 미완료·팀장 확인 기록

아래는 `31ea448` 분기 시점의 이력이며, 2차 백엔드 변경의 최신 상태가 아니다. 최신 계약은 `API_CONTRACT.md`의 2차 백엔드 계약을 확인한다.

- 초대 코드 만료 시간이 확정되지 않아 만료 처리는 구현하지 않았다.
- 피드백 점수 범위와 상대방 공개 범위가 미확정이므로 만족도 API를 생성하지 않았다.
- 기념일·일정의 반복 규칙과 알림 동의 연동 계약이 확정되지 않아 일정 API 및 n8n 호출을 이번 변경에 포함하지 않았다. n8n에는 동의가 확인된 수신자에게 필요한 일정 식별자·유형·예정 시각·최소 수신 정보만 전달하고, JWT·비밀번호·비공개 조건은 전달하지 않는 `NOTIFICATION_PRIVACY.md` 원칙을 유지한다.
- 기존 확정 Decision의 불변 기록 backfill은 별도 백업·감사 후 수행해야 한다.
- 승인·추천·후보 동시 요청의 원자성, 다중 프로세스의 동시 커플 참여, 실제 브라우저 통합은 추가 검증 대상이다. 이번 동시 참여 테스트는 파일 SQLite와 단일 FastAPI 프로세스의 두 요청 범위다.
- 최종 WBS 상태와 Notion 업데이트는 팀장 검수 후 결정한다. 이 문서는 Notion을 수정하지 않는다.

## 2차 백엔드 연동 참고

- 초대 코드는 신규 발급 후 24시간 유효하며, 한 명만 연결된 구성원은 `POST /couples/invite-code`로 재발급한다. 만료·비활성 코드는 410이다.
- 추천 실패 후 조건 수정·재추천은 409다. 수동 후보 등록 또는 새 Decision 생성 경로를 제공한다.
- `GET/PUT /decisions/{decision_id}/feedback/me`는 확정 결정에 대한 본인 평가만 처리한다. 상대의 점수와 의견은 노출되지 않는다.
- `POST/GET /schedules`, `GET/PUT/DELETE /schedules/{schedule_id}`는 현재 커플의 한국 현지 일정 CRUD다. `kind`, `local_date`, `local_time`, `repeat_rule`을 사용한다.
- `GET/PUT /notifications/settings/me`는 본인 알림 동의·철회를 처리한다. 기본값은 미동의다. 일정/동의 변경 시 내부 미발송 작업을 갱신한다.
- 실제 n8n 전송 및 Gmail 발송, 재시도 worker는 아직 없다. 프론트엔드는 알림 예약을 실제 발송 완료로 표시하면 안 된다.
