# OURVERSE 3.0 테스트 시나리오 및 증빙 규칙

- WBS: 1.2.7
- 작성일: 2026-11-24
- 담당: 이효재
- 기능 갱신: WBS 2.2.5 원담당 김해인, 실제 구현 이효재(대행)
- 기준 문서: `MVP_SCOPE.md`, `API_CONTRACT.md`, `USER_JOURNEY.md`, `FEATURE_SPEC.md`, `SYSTEM_ARCHITECTURE.md`, `DB_DESIGN.md`
- 완료 기준: 성공·실패·미검증 구분과 증빙 경로 정의

## 기본 원칙

- 코드, 문서, PR 또는 화면이 존재한다는 사실만으로 테스트 성공으로 판정하지 않는다.
- 기능 구현 상태(`implemented`, `partial`, `planned`)와 테스트 상태(`PASS`, `FAIL`, `PARTIAL`, `NOT TESTED`)를 별도로 기록한다.
- 모든 PASS에는 실행 조건, 예상 결과, 실제 결과와 재현 가능한 증빙 경로가 있어야 한다.
- 실제로 실행하지 않은 시나리오의 결과를 추정하거나 만들어내지 않는다.
- 자동 테스트, 브라우저, 실물 장비, n8n, 사용자 테스트는 서로 다른 증빙으로 관리한다.
- 실패 및 미검증 상태를 숨기지 않으며 재실행 시 기존 기록을 덮어쓰지 않는다.

## 1. 테스트 상태 정의

### PASS

- 완료 조건을 실제로 처음부터 끝까지 수행했다.
- 예상 결과와 실제 결과가 일치했다.
- 동일 조건에서 다시 확인할 수 있는 증빙이 존재한다.
- 실행한 commit, 환경, 데이터, 실행자와 시각을 식별할 수 있다.

### FAIL

- 시나리오를 실제로 실행했지만 완료 조건을 충족하지 못했다.
- 오류, 잘못된 상태 전이 또는 예상과 다른 결과가 발생했다.
- 실패 단계, 실제 결과, 로그와 재현 방법을 기록한다.
- 원인 분석 전이라도 FAIL을 NOT TESTED나 PASS로 바꾸지 않는다.

### PARTIAL

- 전체 시나리오 중 일부 단계만 실제로 성공했다.
- 기능은 있으나 UI 연결, 예외 처리, 데이터 영속화, 동시성 또는 다른 완료 조건이 남았다.
- 성공한 범위와 남은 범위를 각각 명시한다.
- 일부 구성요소의 PASS를 전체 사용자 흐름의 PASS로 확대하지 않는다.

### NOT TESTED

- 구현 또는 문서만 존재하고 실제 실행 검증을 하지 않았다.
- 기능이 아직 구현되지 않아 실행할 수 없는 경우도 테스트 상태는 NOT TESTED로 기록하고, 구현 상태를 `not implemented` 또는 `planned`로 별도 표시한다.
- 실행 증빙이 없거나 증빙 경로를 확인할 수 없는 경우 PASS로 올리지 않는다.

### 상태 선택 규칙

| 상황 | 구현 상태 | 테스트 상태 |
|---|---|---|
| 코드만 작성됨 | implemented 또는 partial | NOT TESTED |
| 일부 단계만 실행 성공 | partial | PARTIAL |
| 전체 실행 결과가 기대와 일치하고 증빙 존재 | implemented | PASS |
| 실제 실행 중 오류 발생 | implemented 또는 partial | FAIL |
| 아직 기능 없음 | planned 또는 not implemented | NOT TESTED |

`NOT TESTED`는 실패가 아니다. 반대로 실행하지 않은 기능을 “문제없음”으로 간주하는 상태도 아니다.

## 2. 기능별 최소 증빙 기준

### 2.1 백엔드/API

다음 중 최소 하나 이상의 실행 증빙을 남긴다. 가능하면 자동 테스트를 우선한다.

- 자동 테스트 명령과 전체 결과
- Swagger UI에서 실제 실행한 요청·응답
- HTTP client의 request/response 로그
- 테스트 전후 DB 행 또는 상태 확인

필수 메타데이터:

- branch와 commit SHA
- 테스트 명령 또는 Method/Path
- 테스트 데이터 식별자(가상 데이터)
- HTTP status와 response body
- DB를 확인했다면 쿼리 또는 확인 방법
- 실행 환경과 실행 시각

인증, 권한, 중복 방지, 버전 및 확정 상태 전이는 자동 테스트로 고정하는 것을 우선한다. Swagger 화면 한 장만으로 여러 상태 전이를 모두 PASS 처리하지 않는다.

### 2.2 프론트엔드

최소 다음을 조합해 남긴다.

- 실제 브라우저 화면 캡처 또는 화면 녹화
- 사용자 시작 지점부터 완료 지점까지의 수행 결과
- 실패 시 오류 메시지 화면
- 브라우저 Network에서 API 연동 성공 확인

소스 코드, 정적 HTML, PR 병합 사실만으로 완료 처리하지 않는다. 화면 증빙에는 테스트 계정, 시작 상태, 클릭 순서와 최종 상태를 식별할 수 있어야 한다.

### 2.3 Arduino / PET DOCK

최소 다음 정보를 남긴다.

- 실제 장치가 보이는 사진 또는 영상
- 사용 보드: Arduino UNO
- 사용 모듈: KEYES Bluetooth 4.0, 광고명 `Meem`
- 통신 설정: USB Serial 9600 baud, BLE Service `FFE0`, Characteristic `FFE1`
- firmware 또는 browser bridge 버전/commit
- 테스트 명령 또는 버튼·LED 동작 순서
- 반복 테스트 횟수, 성공 횟수, 실패 횟수
- 포트 또는 통신 결과 로그
- 테스트 날짜, 실행자, 연결 배선 정보

실물 사진 없이 소스만 존재하는 경우 하드웨어 PASS로 판정하지 않는다. RXD 입력 전압 검증 전 UNO TX와 KEYES RXD를 직접 연결하지 않는다.

### 2.4 n8n

최소 다음 증빙을 남긴다.

- 실제 workflow 실행 성공 이력
- Webhook 요청 수신 결과
- D-1 또는 당일 조건의 분기 결과
- Gmail 등 테스트 계정에 실제 알림이 도착한 화면
- 동일 일정 재처리 시 중복 발송 여부 확인
- workflow ID/버전과 실행 시각

workflow 캔버스가 존재하는 것만으로 PASS 처리하지 않는다. 실제 trigger부터 알림 도착까지 확인해야 한다.

### 2.5 사용자 테스트

최소 다음 정보를 남긴다.

- 참여자 수와 익명 참여자 ID
- 모집 조건과 테스트 환경
- 수행한 시나리오
- 단계별 성공 여부와 소요 시간
- 도움 요청, 이탈 지점, 관찰된 문제
- 실제 참여자 피드백과 진행자의 해석 구분

사용자 테스트를 하지 않았다면 참여자, 피드백 또는 결과를 임의로 만들지 않고 NOT TESTED로 기록한다.

## 3. P0 핵심 테스트 시나리오

### 3.1 인증

| ID | 시나리오 | 실행 절차 | 예상 결과 | 최소 증빙 | 현재 테스트 상태 |
|---|---|---|---|---|---|
| P0-AUTH-01 | 회원가입 성공 | 새로운 이메일·닉네임·비밀번호로 `POST /users` | 201, `UserRead`, `couple_id=null` | 자동 테스트 또는 HTTP 요청/응답 | NOT TESTED — 구현·UI 존재, 전용 테스트 없음 |
| P0-AUTH-02 | 중복 이메일 | 같은 이메일로 회원가입 2회 | 두 번째 요청 409 `Email already registered` | 자동 테스트와 DB unique 확인 | NOT TESTED |
| P0-AUTH-03 | 로그인 성공 | 올바른 계정으로 `POST /token` | 200, bearer JWT 발급 | 토큰을 마스킹한 HTTP 로그 | PASS — 개인 조건 API 테스트가 A/B·타 커플·미가입 사용자 토큰을 실제 로그인 endpoint로 발급하고 보호 API에 사용 |
| P0-AUTH-04 | 로그인 실패 | 잘못된 비밀번호 사용 | 401 `Incorrect email or password` | 자동 테스트 또는 오류 화면 | NOT TESTED |
| P0-AUTH-05 | 로그아웃 후 토큰 차단 | 로그인→`POST /logout`→같은 토큰으로 보호 API 호출 | 로그아웃 200, 이후 401 `Token has been revoked` | 자동 테스트와 폐기 토큰 DB 확인 | NOT TESTED |

### 3.2 커플 연결

| ID | 시나리오 | 실행 절차 | 예상 결과 | 최소 증빙 | 현재 테스트 상태 |
|---|---|---|---|---|---|
| P0-COUPLE-01 | A가 초대 코드 생성 | A 로그인 후 `POST /couples` | 201, A가 첫 구성원인 Couple과 8자리 코드 | API 로그와 브라우저 화면 | NOT TESTED — 구현·UI 존재 |
| P0-COUPLE-02 | B가 정상 참여 | B 로그인 후 A의 코드로 `POST /couples/join` | 200, 동일 Couple에 A/B 두 명 | 두 계정 화면과 응답 | NOT TESTED — 구현·UI 존재 |
| P0-COUPLE-03 | 잘못된 코드 | 존재하지 않는 코드 입력 | 404 `Invite code not found` | 오류 응답과 UI 오류 화면 | NOT TESTED |
| P0-COUPLE-04 | 이미 커플인 사용자 | 연결된 사용자가 새 Couple 생성 또는 참여 | 409 `User already belongs to a couple` | API 로그와 UI 오류 화면 | NOT TESTED |
| P0-COUPLE-05 | 정원 초과 | 두 명이 연결된 코드에 제3 사용자가 참여 | 409 `Couple already has two members` | 자동 테스트 또는 HTTP 로그 | NOT TESTED |

커플 UI가 `main`에 병합됐다는 사실은 구현 근거다. 실제 브라우저 통합 수행 증빙이 없으므로 위 시나리오를 PASS로 판정하지 않는다.

### 3.3 공동결정

| ID | 시나리오 | 실행 절차 | 예상 결과 | 최소 증빙 | 현재 테스트 상태 |
|---|---|---|---|---|---|
| P0-DEC-01 | Decision 생성 | 커플 사용자가 `POST /decisions` | 201, `status=open`, 서버가 couple/user 지정 | 자동 테스트 또는 HTTP 로그 | NOT TESTED — endpoint 구현 |
| P0-DEC-02 | Candidate v1 생성 | 두 커플 구성원이 조건을 제출한 열린 Decision에 첫 Candidate 생성 | 201, `version=1`, `is_current=true` | 자동 테스트와 DB 상태 | PASS — JWT 기반 조건 선행 흐름에서 세 값을 직접 검증 |
| P0-DEC-03 | Candidate v2 및 v1 비활성화 | 두 조건이 제출된 같은 Decision에 두 번째 Candidate 생성 | v2 `version=2`·current, v1 `is_current=false` | 자동 테스트와 두 Candidate 상태 | PASS — 기존 상세 테스트와 JWT 기반 회귀 테스트가 검증 |
| P0-DEC-04 | 최신 Candidate 승인 | current Candidate를 A가 승인 | 201, A의 승인 행 생성 | 자동 테스트와 상세 조회 | PASS — 기존 테스트 흐름에서 실행 |
| P0-DEC-05 | A만 승인 시 미확정 | A 승인 후 상세 조회 | `approval_count=1`, `confirmed=false` | 자동 테스트 결과 | PASS — 기존 테스트가 직접 검증 |
| P0-DEC-06 | A/B 승인 시 confirmed | B가 같은 current Candidate 승인 후 상세 조회 | 승인 2, `status=confirmed`, `confirmed=true` | 자동 테스트 결과 | PASS — 기존 테스트가 직접 검증 |
| P0-DEC-07 | 구버전 승인 차단 | v2 생성 후 v1 승인 | 409 `Only the current candidate can be approved` | 부정 자동 테스트와 응답 | NOT TESTED — 코드만 존재 |
| P0-DEC-08 | 중복 승인 차단 | 같은 사용자가 같은 Candidate를 2회 승인 | 두 번째 요청 409 | 부정 자동 테스트와 DB 승인 1건 확인 | NOT TESTED — 코드·unique 존재 |
| P0-DEC-09 | confirmed 후 재승인 차단 | 확정된 Decision의 Candidate 재승인 | 409 `Decision is already closed` | 부정 자동 테스트와 상태 유지 확인 | NOT TESTED — 코드만 존재 |
| P0-DEC-10 | 타 커플 접근 차단 | 다른 커플이 목록·상세·후보 생성·승인 시도 | 데이터 미노출, 단건 접근 403 | endpoint별 권한 자동 테스트 | PARTIAL — 목록·상세와 JWT 기반 후보 생성 차단은 테스트됨, 타 커플 승인 시도는 미검증 |
| P0-DEC-11 | 후보 없는 Decision 상세 | Candidate 없는 Decision 조회 | 200, `current_candidate=null`, `confirmed=false` | 자동 테스트 결과 | PASS |
| P0-DEC-12 | 동시 승인 원자성 | A/B가 거의 동시에 같은 Candidate 승인 | 승인 2건이면 최종 상태가 반드시 confirmed | 동시 요청 테스트와 DB 상태 | NOT TESTED — backend 보강 필요 |
| P0-DEC-13 | 동시 Candidate 버전 생성 | 같은 Decision에 동시에 후보 생성 | version 중복·복수 current 없이 한 요청씩 일관 처리 | 동시 요청 테스트와 DB constraint 확인 | NOT TESTED — backend 보강 필요 |

2026-11-24 현재 `python -m unittest discover -s tests -v`의 기존 6개 테스트는 통과했다. PASS 범위는 해당 테스트가 직접 실행·검증한 주장으로 제한한다.

### 3.4 개인별 비공개 조건

| ID | 시나리오 | 예상 결과 | 최소 증빙 | 현재 테스트 상태 |
|---|---|---|---|---|
| P0-COND-01 | A/B 각각 조건 저장·본인 조회 | 사용자별 서로 다른 행을 저장하고 `/me`는 본인 행만 반환 | `tests/test_private_conditions.py` | PASS |
| P0-COND-02 | 상대방 상세 조건 보호 | 상대 계정의 `/me`는 상대 행이 아니라 본인 행만 조회하며 미제출 시 404 | 자동 테스트와 응답 필드 확인 | PASS |
| P0-COND-03 | 제출 상태 공유 | status 응답은 구성원별 `user_id`, `submitted`만 반환 | 민감 문자열 비노출 assertion | PASS |
| P0-COND-04 | 타 커플 접근 차단 | PUT/GET/status 모두 403 | endpoint별 부정 자동 테스트 | PASS |
| P0-COND-05 | 인증·입력·ID 조작 차단 | 무인증 401, 잘못된 값과 `user_id`/`couple_id` 추가 422 | 자동 테스트 | PASS |
| P0-COND-06 | 반복 PUT 수정 | 동일 `(decision_id, user_id)` 행 1건을 갱신 | DB row count assertion | PASS |
| P0-COND-07 | 한 명만 조건 제출 후 Candidate 생성 차단 | A만 제출한 상태의 Candidate POST는 409 | JWT 기반 자동 테스트와 오류 응답 | PASS |
| P0-COND-08 | 양측 제출 후 생성·조건 잠금 | A/B 제출 뒤 Candidate는 201이고 이후 A/B 조건 PUT은 모두 409 | JWT 기반 자동 테스트 | PASS |
| P0-COND-09 | 조건 기반 추천 | 두 사용자 조건으로 후보 자동 생성 | 추천 API/알고리즘 증빙 | NOT TESTED — 이번 WBS 제외, 미구현 |

2026-11-24 `feature/p0-private-conditions-20261124`에서 개인 조건·Candidate 선행 조건 테스트 9개와 기존 Decision 조회·승인 테스트 6개, 총 15개 Python 자동 테스트를 실행해 모두 통과했다. A/B와 타 커플 접근 테스트는 `POST /token`으로 발급한 실제 JWT를 사용한다. 브라우저 UI 통합, 동시 조건 PUT, 동시 Candidate 생성 경쟁 테스트는 수행하지 않았으므로 NOT TESTED로 유지한다.

### 3.5 프론트엔드·백엔드 통합

| ID | 시나리오 | 실행 절차 | 예상 결과 | 최소 증빙 | 현재 테스트 상태 |
|---|---|---|---|---|---|
| P0-E2E-01 | 서로 다른 두 계정의 실제 웹 흐름 | 별도 세션의 A/B로 가입·로그인·연결 | 두 독립 계정이 같은 Couple로 연결 | 전체 화면 녹화와 Network 로그 | NOT TESTED — UI 구현은 인증·커플까지 존재 |
| P0-E2E-02 | 연결→결정→후보→승인→확정 | 웹 UI에서 P0 전체 흐름 수행 | 동일한 최신 후보 양측 승인 후 결과 조회 | A/B 세션 화면 녹화와 API 로그 | PARTIAL — backend 존재, Decision UI와 조건·추천 미구현 |

P0-E2E-02는 현재 전체 수행이 불가능하므로 PASS로 표시하지 않는다. 하드웨어 연결 여부는 이 시나리오의 전제 조건이 아니다.

## 4. P1 테스트 시나리오

### 4.1 OUR PET

| ID | 시나리오 | 예상 결과 | 최소 증빙 | 구현 상태 | 테스트 상태 |
|---|---|---|---|---|---|
| P1-PET-01 | 결정 1건 확정 시 경험치 지급 | 해당 커플 펫 경험치 1회 증가 | API/DB 전후 상태 | planned | NOT TESTED |
| P1-PET-02 | 동일 결정 중복 지급 차단 | 재처리해도 경험치 추가 증가 없음 | 중복 요청 자동 테스트와 경험치 원장 | planned | NOT TESTED |
| P1-PET-03 | 상태/레벨 표시 | 경험치 구간에 따라 최소 2~3단계 표시 | 브라우저 화면과 API 응답 | planned | NOT TESTED |
| P1-PET-04 | 결정 기록과 성장 연결 | 경험치 원인 Decision을 추적 가능 | DB 원장과 UI 상세 | planned | NOT TESTED |
| P1-PET-05 | 곰·토끼 결정적 배정 | 합계 짝수는 곰, 홀수는 토끼 | 자동 테스트와 PetState | planned | NOT TESTED |
| P1-PET-06 | 입력 순서 독립성 | A/B 입력 순서를 바꿔도 species 동일 | 순서 교환 자동 테스트 | planned | NOT TESTED |
| P1-PET-07 | 커플당 펫 1마리 | 같은 Couple에 PetState 1건만 존재 | DB unique와 동시 요청 테스트 | planned | NOT TESTED |
| P1-PET-08 | 생일 최소 수집 | 생년과 생일 원문 없이 species·규칙 버전만 영속 저장 | request·DB·로그 검수 | planned | NOT TESTED |

### 4.2 PET DOCK

| ID | 시나리오 | 예상 결과 | 현재 근거 | 구현/통합 상태 | 테스트 상태 |
|---|---|---|---|---|---|
| P1-DOCK-01 | Arduino 버튼 A/B → USB Serial | 9600 baud로 `BTN_A`/`BTN_B` 수신 | 성주연의 2026-11-23 실기기 반복 시험 성공 기록 | bridge 미병합 | PARTIAL — 실물 시험 성공, 정식 증빙 경로 미등록 |
| P1-DOCK-02 | Browser Web Serial 수신 | 브라우저가 버튼 이벤트를 구분 | 성주연의 2026-11-23 실기기 반복 시험 성공 기록 | bridge 미병합 | PARTIAL — 실물 시험 성공, 정식 증빙 경로 미등록 |
| P1-DOCK-03 | BLE Meem 연결 | 광고명 Meem, FFE0/FFE1 연결 성공 | 성주연의 2026-11-23 실기기 반복 시험 성공 기록 | bridge 미병합 | PARTIAL — 실물 시험 성공, 정식 증빙 경로 미등록 |
| P1-DOCK-04 | R/G/B/X LED 제어 | 명령별 RGB/꺼짐 상태 일치 | 성주연의 2026-11-23 실기기 반복 시험 성공 기록 | bridge 미병합 | PARTIAL — 실물 시험 성공, 정식 증빙 경로 미등록 |
| P1-DOCK-05 | BLE Notify 버튼 경로 | 버튼 Notify를 브라우저가 수신 | 미완료로 문서화됨 | not implemented | NOT TESTED |
| P1-DOCK-06 | 하드웨어가 승인을 대신하지 않음 | 버튼 이벤트가 승인 API·DB 승인을 만들지 않음 | 아키텍처 경계와 미병합 bridge 코드 | main 미통합 | NOT TESTED — 통합 부정 테스트 필요 |
| P1-DOCK-07 | 장치 미연결 상태 | TWO-PICK P0 흐름이 장치 없이 계속됨 | 구조 원칙만 확정 | P0 웹 전체 미완료 | NOT TESTED |

P1-DOCK-01~04는 성주연이 실제 장치로 반복 시험해 USB 버튼과 BLE LED 동작에 성공했다. 다만 저장소의 전용 `evidence/` 파일 또는 팀이 접근할 수 있는 정식 외부 링크가 아직 등록되지 않았으므로, 이 문서의 PASS 정의에 따라 현재 최종 테스트 상태는 PARTIAL이다. 원본 사진·영상, 반복 횟수, 성공/실패 횟수와 공유 경로를 manifest에 등록한 뒤 PASS로 전환한다. 실물 시험 성공을 `main` 통합 완료로 해석하지 않는다.

### 4.3 SMART COUPLE CARE / n8n

| ID | 시나리오 | 예상 결과 | 최소 증빙 | 구현 상태 | 테스트 상태 |
|---|---|---|---|---|---|
| P1-CARE-01 | 일정 등록·조회 | 현재 커플의 일정만 저장·조회 | API 로그와 DB 상태 | planned | NOT TESTED |
| P1-CARE-02 | D-1 또는 당일 trigger | 지정 조건에서 workflow 실행 | n8n 실행 이력 | planned | NOT TESTED |
| P1-CARE-03 | 테스트 메일 실제 발송 | 테스트 계정 inbox에 알림 도착 | workflow 결과와 redacted 메일 화면 | planned | NOT TESTED |
| P1-CARE-04 | 중복 발송 방지 | 같은 일정·조건으로 알림 1회만 발송 | 반복 trigger 로그와 발송 원장 | planned | NOT TESTED |

## 5. 증빙 파일 규칙

### 권장 디렉터리 구조

```text
evidence/
  YYYY-MM-DD/
    WBS_ID/
      README.md
      backend/
      frontend/
      hardware/
      n8n/
      user-test/
```

예:

```text
evidence/2026-11-24/1.2.7/
```

각 WBS 폴더의 `README.md`는 증빙 manifest로 사용하며 다음을 기록한다.

- 테스트 ID와 WBS ID
- 구현 상태와 테스트 상태
- branch, commit SHA, 관련 PR
- 실행 날짜·시각·timezone과 실행자
- 담당자 대행 여부와 사유
- 환경, 장치, 브라우저, 서버 버전
- 사전 조건과 테스트 데이터
- 실행 절차, 예상 결과, 실제 결과
- 증빙 파일 상대 경로 또는 외부 링크
- FAIL/PARTIAL/NOT TESTED 사유와 후속 작업

### 파일명 규칙

권장 형식:

```text
{WBS_ID}_{component}_{scenario}_{run}.{ext}
```

예:

- `3.1.1_backend_tests.txt`
- `3.1.2_ble_button_10x.png`
- `2.1.7_couple_ui.mp4`
- `2.6.6_n8n_email.png`
- `1.2.7_P0-DEC-06_backend_confirmed_run01.txt`

규칙:

- WBS와 시나리오를 파일명에서 식별할 수 있어야 한다.
- 반복 횟수가 중요한 장비 테스트는 `10x`, `run01`처럼 횟수나 실행 순서를 표시한다.
- 재실행 파일을 기존 파일에 덮어쓰지 않고 run 번호를 증가시킨다.
- 텍스트 로그는 가능하면 명령, 시작·종료 시각과 exit code를 포함한다.
- 화면 캡처는 어떤 단계와 상태를 보여주는지 manifest에 설명한다.

### Git과 외부 저장소 구분

Git 저장소에 적합한 자료:

- redacted 텍스트 로그
- 작은 JSON 응답 예시
- 테스트 결과 요약
- 개인정보가 없는 소형 화면 캡처
- 외부 증빙 링크를 정리한 manifest

Git 저장소에 직접 올리지 않는 자료:

- 대용량 원본 영상
- 개인정보나 실제 계정 정보가 포함된 파일
- 접근 제한이 필요한 사용자 테스트 원본
- 장기간 보관이 필요한 대용량 하드웨어 촬영본

대용량 또는 민감 자료는 팀 공유 저장소나 Notion 등 접근 제어가 가능한 위치에 저장하고 manifest에 링크, 접근 권한, 보관 책임자와 확인 날짜를 기록한다. 팀원이 열 수 없는 개인 로컬 경로는 유효한 공동 증빙 경로로 사용하지 않는다.

## 6. 개인정보·보안 규칙

증빙에 다음 값을 원문 그대로 포함하지 않는다.

- 실제 비밀번호
- JWT 전체 값
- `SECRET_KEY`
- 실제 개인 이메일 주소
- 이름, 연락처, 위치 등 개인정보
- 사용자별 민감한 개인 조건
- n8n credential, Gmail 인증 정보, API key

적용 규칙:

- `user-a@example.test` 같은 테스트 계정과 가상 데이터를 우선 사용한다.
- JWT는 앞·뒤 일부만 남기거나 `<redacted-jwt>`로 치환한다.
- 스크린샷과 영상은 업로드 전 이메일, 알림 내용, 브라우저 자동완성, OS 알림을 가린다.
- DB dump 전체 대신 필요한 행과 컬럼만 최소화해 추출한다.
- 원본 개인정보가 필요한 사용자 테스트 자료는 동의와 접근 제어를 적용하고 공개 Git에 올리지 않는다.
- redaction 후에도 테스트 ID와 결과를 추적할 수 있는 식별자는 유지한다.

## 7. WBS 완료 판정 규칙

1. **산출물만 작성:** 기능 WBS 완료가 아니다. 문서 작성 WBS는 문서 자체 완료 기준으로 별도 판정한다.
2. **구현 + 검증:** 모든 필수 완료 조건을 실제 실행하고 PASS 증빙이 있으면 완료 판정할 수 있다.
3. **일부 구현/검증:** 진행 중 또는 PARTIAL로 기록한다.
4. **필수 시나리오 FAIL:** 원인을 해결하고 재검증하기 전 완료 금지다.
5. **필수 시나리오 NOT TESTED:** 실행 전 완료 금지다.
6. **실제 장비 기능:** 실물 장비 검증과 장치 정보·반복 결과 증빙 전 완료 금지다.
7. **실제 사용자 검증 항목:** 사용자 테스트 수행과 익명화된 결과 증빙 전 완료 금지다.
8. **PR 병합:** 구현 반영의 증거이지 기능 검증 PASS를 자동으로 의미하지 않는다.
9. **자동 테스트 일부 통과:** 테스트가 직접 검증한 범위만 PASS다.
10. **대행 작업:** 담당자, 대행자, 대행 사유, 검수자를 manifest와 WBS 기록에 남긴다.
11. **재검증:** 코드·배선·workflow·환경이 의미 있게 변경되면 기존 PASS의 적용 가능성을 확인하고 필요하면 새 run을 만든다.
12. **최종 승인:** 필수 시나리오별 상태와 증빙 경로를 검토한 사람이 확인한 뒤 완료 처리한다.

WBS 1.2.7의 담당자는 이효재다.

## 8. 현재 프로젝트 기준 예시 판정

다음은 2026-11-24 현재 문서, 코드, 자동 테스트 및 제공된 실기기 테스트 기록을 기준으로 한 예시다.

| 항목 | 구현 상태 | 테스트 상태 | 현재 근거 | 완료 전 남은 사항 |
|---|---|---|---|---|
| backend Decision 양측 승인 순차 흐름 | partial | PASS | `tests/test_decision_reads.py`, 6개 테스트 통과 | 동시성·부정 테스트는 별도 |
| 동시 승인 원자성 | partial | NOT TESTED | 검증 테스트 없음 | 트랜잭션 보강 및 동시 요청 테스트 |
| 동시 Candidate version 생성 | partial | NOT TESTED | 검증 테스트 없음 | current 1건 보장 및 동시 요청 테스트 |
| 커플 초대·연결 웹 UI | implemented | NOT TESTED | 코드 및 PR 병합, 브라우저 실행 증빙 없음 | A/B 실제 브라우저 E2E 캡처 |
| P0 전체 웹 흐름 | partial | PARTIAL | 인증·커플 UI와 공동결정 backend 존재 | 조건·추천·Decision UI 구현 및 A/B E2E |
| 구버전 승인 차단 | implemented | NOT TESTED | backend 분기 존재, 직접 테스트 없음 | 부정 자동 테스트 |
| 중복 승인 차단 | partial | NOT TESTED | 조회·unique 존재, 동시성 미검증 | 순차·동시 중복 테스트 |
| confirmed 후 재승인 차단 | implemented | NOT TESTED | backend 분기 존재, 직접 테스트 없음 | 부정 자동 테스트 |
| 타 커플 Decision 목록·상세·후보 생성 | implemented | PASS | 기존 자동 테스트와 실제 JWT 기반 Candidate 생성 차단 테스트 | 타 커플 승인 권한은 별도 미검증 |
| PET DOCK USB 버튼 반복 테스트 | prototype / main 미통합 | PARTIAL | 성주연의 2026-11-23 실제 반복 시험 성공 기록 | 증빙 파일·외부 링크 manifest 등록 후 PASS 전환 |
| PET DOCK Web Serial 수신 | prototype / main 미통합 | PARTIAL | 성주연의 2026-11-23 실제 반복 시험 성공 기록 | 반복 횟수·성공/실패 횟수와 공유 경로 등록 |
| BLE Meem FFE0/FFE1 연결·LED 반복 테스트 | prototype / main 미통합 | PARTIAL | 성주연의 2026-11-23 실제 반복 시험 성공 기록 | 사진·영상·통신 결과 경로 등록 후 PASS 전환 |
| BLE Notify 버튼 | not implemented | NOT TESTED | 미완료로 문서화 | 구현 후 실물 반복 테스트 |
| PET DOCK이 승인을 만들지 않음 | architecture boundary | NOT TESTED | 설계와 prototype 코드에는 승인 호출 없음 | main 통합 후 부정 통합 테스트 |
| 개인 비공개 조건 API | implemented | PASS | `tests/test_private_conditions.py`, 개인 조건·Candidate 선행 조건 9개 테스트 | 브라우저 UI·동시 PUT은 별도 검증 |
| 두 사용자 조건 기반 추천 | planned | NOT TESTED | 추천 모델/API 없음 | 다음 P0 단계에서 구현·검증 |
| OUR PET·경험치 | planned | NOT TESTED | 모델/API 없음 | 중복 지급 포함 구현·테스트 |
| CARE 일정·n8n 알림 | planned | NOT TESTED | 구현·실행 증빙 없음 | 일정 등록, trigger, 실제 알림, 중복 테스트 |
| 실제 커플 사용자 테스트 | planned | NOT TESTED | 참여자·결과 없음 | 모집·동의·시나리오 수행·익명 결과 기록 |

## 9. WBS 1.2.7 완료 판정

다음을 정의했다.

- PASS, FAIL, PARTIAL, NOT TESTED의 구분
- backend, frontend, hardware, n8n, 사용자 테스트별 최소 증빙
- P0/P1 필수 테스트 시나리오와 현재 보수적 판정
- 증빙 디렉터리, 파일명, manifest 및 외부 저장소 규칙
- 개인정보·비밀정보 redaction 규칙
- 구현, 검증, 실물·사용자 테스트와 WBS 완료의 관계
- 담당자 부재 시 대행 기록 원칙

따라서 WBS 1.2.7 완료 기준인 **“성공·실패·미검증 구분과 증빙 경로 정의”를 충족**한다. 이는 증빙 규칙 문서의 완료 판정이며, 표에 포함된 개별 기능이 모두 구현·검증됐다는 뜻은 아니다.
