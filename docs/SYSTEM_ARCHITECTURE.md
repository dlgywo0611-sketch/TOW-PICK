# TWO-PICK 시스템 구조

- WBS: 1.2.1
- 확정일: 2026-11-24
- 기준: `origin/main` `eddb574` 및 2026-11-23 PET DOCK 실기기 검증 결과

## 확정 구조

```text
사용자 A 웹 ─┐
             ├─ HTTPS/JSON + 로그인 JWT ─ FastAPI ─ SQLAlchemy ─ SQLite
사용자 B 웹 ─┘                         │
                                      └─ 공동결정 생성·조회·계정별 승인·확정

Arduino UNO 버튼 A/B
  └─ USB Serial (9600 baud, BTN_A/BTN_B)
       └─ Browser Web Serial
            └─ PET 이벤트 처리/표시

Browser
  └─ Web Bluetooth WRITE (R/G/B/X)
       └─ KEYES Bluetooth 4.0, 광고명 Meem
            └─ Service FFE0 / Characteristic FFE1
                 └─ RGB LED
```

Arduino 버튼 입력과 KEYES LED 제어는 현재 서로 다른 두 경로다. 따라서 과거의 단일 `Arduino → BLE → Browser → FastAPI` 구조는 실제 구성과 맞지 않으며 사용하지 않는다.

## 구성요소별 책임

| 구성요소 | 현재 책임 | 하지 않는 일 |
|---|---|---|
| 사용자 A/B 웹 | 로그인, 커플 연결, API 호출 | 다른 사용자의 승인을 대행하지 않음 |
| FastAPI | 인증, 커플 스코프 검사, 결정·후보·승인 상태 전이 | 하드웨어 버튼을 승인으로 해석하지 않음 |
| SQLite | 계정, 커플, 메시지, 폐기 토큰, 결정·후보·승인 저장 | PET 상태·경험치·일정은 아직 저장하지 않음 |
| Arduino UNO | 버튼 A/B 입력을 USB Serial 텍스트로 전송 | 현재 BLE Notify 송신 장치가 아님 |
| Browser Web Serial | 9600 baud로 `BTN_A`/`BTN_B`를 수신하고 PET 이벤트로 변환 | `/candidates/{id}/approve`를 호출하지 않음 |
| Browser Web Bluetooth | Meem에 연결하고 FFE1로 `R/G/B/X` WRITE | 버튼 승인 수신 경로가 아님 |
| KEYES Meem | BLE 명령을 받아 RGB LED 제어 | 사용자 신원 또는 공동결정 권한을 보유하지 않음 |

## 공동결정 승인 경계

공동결정 승인은 반드시 다음 경로만 사용한다.

```text
로그인된 사용자 계정
  → Authorization: Bearer <JWT>
  → POST /candidates/{candidate_id}/approve
  → FastAPI가 사용자·커플·최신 후보·중복·결정 상태 검증
  → DecisionApproval(user_id, candidate_id) 저장
```

버튼 A/B, BLE 연결 여부, LED 명령, PET 이벤트는 위 요청의 인증 근거가 아니며 승인 행을 생성해서는 안 된다. 두 사람은 각자 로그인된 웹 세션에서 동일한 최신 후보를 승인해야 한다.

## 하드웨어 검증 상태

### 2026-11-23 확인됨

- Arduino UNO 버튼 A/B → USB Serial → Browser Web Serial
- USB Serial 속도 9600 baud
- KEYES Bluetooth 4.0 광고명 `Meem`
- BLE Service `FFE0`, Characteristic `FFE1`
- Browser Web Bluetooth WRITE `R`, `G`, `B`, `X`로 RGB LED 제어

### 미완료 또는 안전 대기

- 버튼 A/B를 KEYES BLE Notify로 전달하는 기능
- KEYES RXD 입력 허용 전압 검증
- 전압 검증 전 UNO TX와 KEYES RXD 직접 연결
- PET 이벤트의 FastAPI 전송 및 DB 영속화

## 저장소 구현 상태

| 영역 | `main` 상태 | 비고 |
|---|---|---|
| FastAPI ↔ SQLite | implemented | SQLAlchemy 동기 세션 사용 |
| 인증·커플·공동결정 API | implemented | 웹 사용자의 JWT 승인 경계 포함 |
| `main` 웹 UI | auth/couple only | 공동결정 및 PET DOCK UI 미연결 |
| Web Serial/Web Bluetooth bridge | not merged | `origin/feat/seongbin-web-ble` `a60d01e`에 검증 코드 존재 |
| BLE Notify 버튼 경로 | planned | 아직 완료되지 않음 |
| PET 상태·경험치 API/DB | planned | 모델 및 API 없음 |

미병합 bridge 구현은 Web Serial에서 `BTN_A`/`BTN_B`만 PET UI 이벤트로 내보내고, Web Bluetooth에서는 FFE1에 LED 명령만 쓴다. 공동결정 승인 API 호출은 포함하지 않는다.

## 운영 및 보안 원칙

- Web Serial/Web Bluetooth는 지원 브라우저의 secure context(`localhost` 또는 HTTPS)와 명시적 사용자 장치 선택이 필요하다.
- Arduino IDE 시리얼 모니터처럼 포트를 점유하는 프로그램과 Web Serial을 동시에 사용하지 않는다.
- 모든 공동결정 API는 JWT와 서버측 `current_user.couple_id`를 기준으로 권한을 검사한다.
- 클라이언트가 보낸 `user_id`나 `couple_id`를 승인 주체 또는 소유권의 근거로 신뢰하지 않는다.
- 하드웨어 이벤트를 서버에 추가할 때도 이벤트 출처와 사용자 승인을 별도 도메인으로 유지한다.
- KEYES RXD 전압 검증 전에는 UNO TX를 직접 연결하지 않는다.
