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

개인 조건, 추천, 공동 승인, BLE 화면은 다음 WBS에서 API 계약과 함께 연결합니다.
