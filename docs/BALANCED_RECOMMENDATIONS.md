# TWO-PICK — P0 규칙형 균형 추천 계약 (2026-11-24)

## 범위 및 주의

P0의 독립 사용자 두 명이 Decision별 비공개 조건을 제출한 뒤, 사용자가 제공한 *시연용 후보* 중 하나를 **규칙형**으로 선정하여 `DecisionCandidate` v1을 생성한다. AI 기반 자연어 의미 분석, 실제 장소 검색, 실가격 확인, 예약 가능 여부 판단은 제공하지 않는다.

기존 2026-11-18 `OURVERSE3_DATE_RECOMMENDATION_R3`의 **각자의 2인 총액 상한** 원칙을 따른다. 따라서 두 사람의 `DecisionCondition.max_budget`은 **각자의 2인 총액 허용 상한**이며, 후보의 `estimated_total_cost_krw`와 **각각** 비교한다. 두 예산을 더하지 않는다. `max_budget` 명칭 자체는 기존 PR #8의 API 계약을 보존하되 이 단위 해석을 명시한다. 기존 DB에 이미 저장된 조건을 새 의미로 자동 변환하지 않는다.

## 신규 API

`POST /decisions/{decision_id}/recommendations` (Bearer JWT, 201)

요청 예시:

```json
{
  "options": [
    {"title": "조용한 한식 식사", "estimated_total_cost_krw": 18000, "time_slot": "토 18:00-20:00", "tags": ["한식", "조용한 곳"]},
    {"title": "전시 관람", "estimated_total_cost_krw": 14000, "time_slot": "토 18:00-20:00", "tags": ["미술관"]}
  ]
}
```

- `options`: 2~8개, 같은 title 중복 금지
- `title`: 1~180자, 공백-only 금지
- `estimated_total_cost_krw`: 0~1,000,000,000원, **두 사람의 필수비 포함 총액이라는 사용자 입력 가정값**
- `time_slot`: 1~100자, 공백-only 금지; 개인의 `available_time`은 쉼표·세미콜론·줄바꿈으로 나눈 슬롯들과 정규화 후 **완전 일치**해야 한다. 의미상 겹치는 자유 서술은 자동으로 계산하지 않는다
- `tags`: 최대 12개, 태그당 1~60자, 공백·대소문자 정규화, 중복 금지. 개인 조건의 `preferences`, `avoidances`도 쉼표·세미콜론·줄바꿈으로 분리한 태그로 처리한다. 의미 유사어·부분문자열 매칭은 하지 않는다
- `extra="forbid"`를 적용해 클라이언트가 `user_id`/`couple_id`를 끼워 넣는 요청은 422로 거부한다

201 응답 예시(상대방 조건·개인 점수는 없음):

```json
{
  "policy_version": "balanced_rules_v1",
  "message": "두 사람이 수용 가능한 시연용 후보를 선정했습니다. 실제 가격과 예약 가능 여부를 확인하세요.",
  "candidate": {
    "id": 11,
    "decision_id": 3,
    "content": "조용한 한식 식사 / 토 18:00-20:00 / 2인 총액 18,000원(시연용·확인 필요)",
    "version": 1,
    "is_current": true
  }
}
```

## 선택 규칙

1. 요청자는 해당 커플의 인증된 사용자여야 하고, Decision이 `open`이어야 한다.
2. 커플 구성원이 정확히 두 명이고 두 사용자 모두 현재 Decision에 조건을 제출했어야 한다.
3. *첫 Candidate 이전*에만 추천을 실행한다. 기존 Candidate가 있다면 409; 수동 후보 변경은 기존 Candidate API로 처리한다.
4. 각 옵션에 대해 두 명 각각의 예산, 시간, 회피 태그를 확인한다. 한 명이라도 예산 초과 / 시간 슬롯 불일치 / 회피 태그 일치가 있으면 제외한다.
5. 통과한 옵션마다 내부 만족도 `min(100, 50 + 10 × (해당 사용자 선호 태그 일치 개수))`를 산정한다. **개인별 점수는 응답·로그·DB에 저장하지 않는다.**
6. 후보 간 우선순위는 (a) 두 점수 중 낮은 값 최대화, (b) 점수 차이 최소화, (c) 두 점수 합 최대화, (d) 가정 총비용 최소화, (e) 제목·시간·태그 순 결정적 동률 처리다. 입력 순서를 바꾸어도 결과가 같다.
7. 선택 시 기존 `DecisionCandidate(version=1, is_current=True)`를 생성한다. **승인은 자동으로 생성하지 않는다.** 사용자는 기존 `/candidates/{id}/approve`에서 각자 승인한다.
8. 응답에는 추천 후보의 사용자가 제공한 공개 옵션 속성만 설명하고, 개인 조건 원문·개인별 점수·불합격 사유는 반환하지 않는다.

## 프라이버시와 한 번만 실행하는 정책

호출자가 후보 집합을 바꿔 반복 요청하며 상대방의 개인 예산·선호를 역추정하는 것을 제한하기 위해, 유효한 추천 요청이 평가되면 **성공 또는 적합 후보 없음** 모두 `DecisionRecommendationAttempt` 한 건을 기록한다. `UNIQUE(decision_id)` 제약으로 Decision당 평가 기회는 한 번뿐이다. 결과 점수·제출 옵션 목록·원본 조건은 DB에 저장하지 않는다. 적합 후보가 없으면 **409**를 반환하며 같은 Decision의 재추천은 불가하다. 일반 수동 Candidate 등록은 가능하다. 별도 Decision을 생성해 커플 각자가 다시 조건을 제출하는 방식은 가능하다. 이것은 완전한 추론 공격 방지가 아니므로 실서비스에서는 요청 제한·감사·사용자 확인 등 추가 보호가 필요하다.

## 예외

| 조건 | HTTP | detail |
|---|---:|---|
| 로그인되지 않음 | 401 | 기존 인증 정책 |
| Decision 없음 | 404 | `Decision not found` |
| 다른 커플 Decision | 403 | `You cannot access this decision` |
| 미연결 계정 | 409 | `User does not belong to a couple` |
| 커플 2명 미만·조건 미제출 | 409 | `Both couple members must submit conditions before recommendation` |
| 결정 닫힘 | 409 | `Decision is already closed` |
| Candidate 이미 있음 | 409 | `Recommendation only available before first candidate` |
| 동일 Decision에서 재추천 | 409 | `Recommendation already attempted for this decision` |
| 적합 후보 없음 (1회 사용 처리) | 409 | `No mutually suitable option; try a manual candidate` |
| 요청 규격 오류/ID 주입 | 422 | Pydantic validation detail |

## 데이터·회귀 테스트·미검증

- 신규 `decision_recommendation_attempts` 테이블. `(decision_id)` unique; `requested_by_id`, `outcome` (`selected`/`no_match`), `candidate_id`(nullable), `created_at`. 실제 후보 상세와 개인 조건 원문은 이 테이블에 저장하지 않는다.
- 기존 SQLite 파일을 삭제/초기화하지 않고 신규 테이블만 `Base.metadata.create_all()`로 생성한다. 운영 DB 백업·정식 migration/이관은 별도 수행해야 한다.
- 예산/시간/회피 조건, 최소 만족도 우선순위, 동률, 양측 승인, 실패·재시도, 교차 커플 접근, JWT 인증에 대한 자동 테스트를 제공한다.
- 동시 추천 요청과 기존 Candidate 생성 요청 간 경쟁, 동시 조건 PUT, 동시 승인, 실시간 요금·예약 검증, 외부 시연/브라우저 E2E는 **후속 검증**이다.
- P1 실물 PET DOCK과 무관한 API다. 하드웨어 버튼은 공동 승인으로 연결하지 않는다.
