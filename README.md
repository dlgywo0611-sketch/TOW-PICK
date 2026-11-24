# OURVERSE 3.0

**TWO-PICK** — 커플이 함께 선택하고 합의하는 공동 의사결정 서비스

## 로컬 실행

1. `.env.example`을 참고해 `.env`에 `SECRET_KEY`를 설정합니다.
2. 의존성을 설치합니다: `pip install -r requirements.txt`
3. 서버를 실행합니다: `uvicorn main:app --reload`
4. 웹 UI는 `http://127.0.0.1:8000/app`에서 엽니다.
5. API 문서는 `http://127.0.0.1:8000/docs`에서 확인합니다.

## 현재 웹 UI 범위

- 회원가입 및 JWT 로그인
- 현재 로그인 사용자 확인
- 커플 초대 코드 생성
- 상대방 초대 코드로 커플 참여
- 연결된 커플 구성원 표시
- 로그아웃 및 브라우저 세션 정리
- Arduino USB 버튼 `BTN_A` / `BTN_B` 이벤트 표시
- KEYES BLE `Meem` 연결 및 RGB LED 제어 (`R` / `G` / `B` / `X`)

## 현재 백엔드 API 범위

- 로그아웃 토큰 폐기
- 커플 단위 공동결정 생성·목록·상세 조회
- 결정 후보 버전 관리
- 최신 후보에 대한 두 사용자의 독립 승인과 확정
- 구버전·중복·확정 후 승인 차단

웹 UI에는 공동결정 생성·목록, 개인 조건 입력, 규칙형 균형 추천, 수동 후보·각 계정의 독립 승인과 결과 조회가 연결되어 있습니다.
이는 **UI 코드 구현** 상태이며 두 계정의 실제 Windows 브라우저 E2E 시험은 아직 완료되지 않았습니다.
실제 장소·가격·예약 검증, 만족도, 펫 상태·경험치, 기념일·일정은 여전히 미구현입니다.
추천은 사용자가 제시한 시연용 옵션을 기반으로 결정당 단 한 번만 평가합니다. 적합 후보가 없어도 추천 횟수는 소진되므로 수동 후보 기능을 제공합니다.
공개 후보와 비공개 개인 조건은 분리하며 PET DOCK 버튼은 승인에 연결하지 않습니다.

## PET DOCK 사용 조건

- Windows Chrome/Edge에서 `localhost` 또는 HTTPS로 접속합니다.
- Arduino USB Serial은 9600 baud이며, 연결 전 Arduino IDE 시리얼 모니터를 닫습니다.
- USB에서 `BTN_A`, `BTN_B`를 수신하며 연결 해제 후 다시 연결할 수 있습니다.
- BLE 광고명은 `Meem`, 서비스는 `FFE0`, 특성은 `FFE1`입니다.
- FFE1의 실제 write capability를 확인한 뒤 `R`, `G`, `B`, `X`로 RGB LED를 제어합니다.
- USB 버튼은 펫 반응·상태 표시 전용이며 커플 투표나 공동결정 승인 API를 호출하지 않습니다.
- KEYES RXD는 연결하지 않으며 Arduino UNO D5를 KEYES RXD에 직접 연결하지 않습니다.
- BLE 버튼 Notify는 KEYES RXD 입력 전압 검증 전이므로 아직 지원하지 않습니다.
- Arduino 배선과 firmware는 [`arduino/README.md`](arduino/README.md)를 따릅니다.

## 설계 문서

- [핵심 기능 명세](docs/FEATURE_SPEC.md)
- [시스템 구조](docs/SYSTEM_ARCHITECTURE.md)
- [DB 설계](docs/DB_DESIGN.md)
