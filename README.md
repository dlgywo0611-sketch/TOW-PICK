# TOW-PICK

HEART BRIDGE 서로의 마음을 연결하는 AI 커플 소통 플랫폼

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

개인 조건, 추천, 공동 승인은 다음 WBS에서 API 계약과 함께 연결합니다.

## PET DOCK 사용 조건

- Windows Chrome/Edge에서 `localhost` 또는 HTTPS로 접속합니다.
- Arduino USB 시리얼은 9600 baud이며, 연결 전 Arduino IDE 시리얼 모니터를 닫습니다.
- BLE 광고명은 `Meem`, 서비스는 `FFE0`, 특성은 `FFE1`입니다.
- USB 버튼은 펫 반응/상태 표시 전용이며 커플 투표나 공동 승인 API를 호출하지 않습니다.
- BLE 버튼 Notify는 하드웨어 RXD 전압 검증 전이므로 아직 지원하지 않습니다.
