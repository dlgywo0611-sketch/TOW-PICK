# TWO-PICK 2차 백엔드 구현·검증 기록 — 2026-11-25

- 기준: `origin/main` `6eed646784564ae8a36bc0e6697f0787f76a171a`
- 브랜치: `feature/backend-phase2-20261125`
- WBS 원담당: 김해인 / 이번 실제 수행: 이효재(PM, 임시 대행)
- 프론트엔드·Notion·PET DOCK 펌웨어 변경 없음

## 과거 49개 테스트 기준선 조사

작업 시작 시 `origin/main`에서 `python -m unittest discover -s tests -q`는 **37개 PASS**였다. `git log --all -- tests`, 삭제 이력, `git log --all -S '49' -- tests docs daily-scrum`, 현재 저장소의 관련 문자열을 확인했으나 Python 49개를 실행했다는 커밋·출력·목록을 찾지 못했다. 현재 Node 공동결정 테스트는 별도 10개이며 PET DOCK USB 회귀 테스트는 별도 스크립트다. 수치를 합산해도 과거 Python 49개라는 기록의 근거가 되지 않는다. 따라서 과거 49개의 존재, 삭제 또는 통합 여부는 **확인 불가**다. 숫자를 맞추기 위한 테스트는 추가하지 않았다.

이번 변경 후 Python 52개 PASS(기준선 37개 + 의미 있는 신규 15개)이며, Node 공동결정 10/10 PASS와 PET DOCK USB 회귀 PASS는 별개로 기록한다.

## 구현 범위와 경계

| 영역 | 결과 | 남은 일 |
|---|---|---|
| 초대 코드 | 발급 시각·24시간 만료·재발급·사용 후 비활성화, 오래된 시각 미상 코드의 재발급 처리 | 배포 계층 IP/계정별 요청 제한, 실제 브라우저 확인 |
| 공동결정 경쟁 쓰기 | 조건·추천·후보·승인 경로 SQLite `BEGIN IMMEDIATE`, current 부분 unique index. 별도 파일 DB 연결의 동시 요청 검증 | 별도 FastAPI 프로세스 부하 검증; SQLite 한계 평가 |
| 추천 실패 | `no_match` 기록 뒤 조건 수정·재추천 차단. 수동 후보 또는 새 Decision만 제시 | 프론트 안내 연결 |
| 결정 이력·평가 | 기존 확정 스냅샷 보존; 확정 Decision의 개인별 1~5점 평가 GET/PUT | 과거 기록 없는 confirmed 건의 감사 후 이관 |
| 커플 일정 | 현재 커플 CRUD, 종일/시간 지정, 반복, 월말·윤년 조정, revision, soft delete | 실제 브라우저 통합, 운영 timezone 데이터 준비 |
| 알림 기반 | 사용자별 기본 미동의·철회, D-1/당일 선택, 예정 작업 unique 원장, 취소, 발송 직전 검사용 mock payload | 실제 scheduler/claim·재시도·n8n Webhook·Gmail 발송 모두 미구현 |

초대 코드는 8자리 hexadecimal이므로 공개 endpoint의 무제한 대입을 허용하는 운영 환경에는 적합하지 않다. 현재 애플리케이션 내 rate limiter는 없다. 역방향 프록시에서 IP와 계정별 제한을 적용하고 악용 로그에는 코드 원문을 기록하지 않는 후속 작업이 필요하다.

기존 confirmed Decision에 확정 이력이 없으면 시각을 추정해 backfill하지 않는다. 검증 가능한 후보·승인 원본과 백업을 대조한 별도 이관이 필요하다.

## DB 백업·추가 스키마 적용

작업 전 로컬 `tow_pick.db`(159744 bytes)를 Git 무시 경로 `.smoke-20261125/phase2-backup/tow_pick-before-phase2.db`에 복사했다. 원본과 백업 모두 `PRAGMA integrity_check=ok`이며, 백업의 User/Couple/Decision 행 수는 각각 0/0/0이었다. 새 테이블을 적용한 원본도 같은 세 테이블 행 수 0/0/0, `foreign_key_check` 위반 0건이다. 운영 데이터 보존을 이 빈 로컬 DB만으로 일반화하지 않는다. 별도 임시 SQLite에 기존 User/Decision/Candidate 행을 만든 후 구형 스키마에서 새 테이블·index를 추가해 행이 그대로 남는 테스트를 실행했다. 중복 current 후보가 있으면 index 적용이 오류로 멈추며 행을 자동 수정·삭제하지 않는 테스트도 통과했다.

기존 DB 적용 절차: (1) 쓰기 트래픽 중지, (2) SQLite online backup과 무결성·행 수 기록, (3) 중복 current 후보·외래키 위반 사전 점검, (4) 새 코드 기동으로 `create_all` 및 부분 index 적용, (5) 무결성·행 수·API smoke 재확인. 중복 current가 있으면 기동을 중단하고 백업과 원본 이력을 검토한다. 구형 초대 코드의 발급 시각을 만들어 넣지 않는다. 기존 커플 연결은 유지한다.

## 알림 Mock 경계

내부 `prepare_mock_payload`는 작업이 pending인지, 일정 revision·삭제 여부, 수신자 소속 커플, 동의 및 알림 종류를 다시 확인한다. 예정 시각부터 10분 이내의 작업만 최소 payload를 만든다. payload에는 작업·일정 ID, 종류, 발생일, UTC 예정 시각, 해당 수신자의 이메일, dedupe key, 일반 문구만 포함한다. 비밀번호, JWT, `SECRET_KEY`, 상대 이메일, 개인 조건은 없다. 실제 HTTP 발송, Gmail, n8n 및 발송 성공·실패 기록은 수행하지 않았다. 현 원장은 다음 반복 1건씩만 계획하며 후속 scheduler가 반복을 전진시켜야 한다. Windows에서 IANA tzdata가 없을 때 현대 한국 일정에 한해 UTC+09:00 대체 계산을 사용하며, 운영 환경에는 `Asia/Seoul` timezone 데이터가 필요하다.

## 검증 상태

| 항목 | 상태 | 근거/한계 |
|---|---|---|
| Python 자동 테스트 | PASS | 52/52, 임시/메모리 SQLite |
| 공동결정 Node 테스트 | PASS | 10/10 |
| PET DOCK USB 회귀 | PASS | Node 스크립트, 장치 실물 시험 아님 |
| Python 구문 및 `git diff --check` | PASS | 수정 모듈·테스트 검사 |
| 동시 후보·승인·중복·추천 경쟁 | PASS (별도 연결) | 파일 SQLite의 병렬 HTTP 요청; 별도 OS 프로세스·운영 부하 NOT TESTED |
| 실제 브라우저 두 계정 흐름 | NOT TESTED | 프론트엔드 변경·기동 없이 백엔드 테스트만 수행 |
| 실물 Arduino/BLE | NOT TESTED | 이번 범위 아님 |
| n8n/Gmail 실제 발송 | NOT TESTED | connector 및 worker 미구현 |

WBS 상태는 이번 구현만으로 전체 서비스 완료를 뜻하지 않는다. 2.1.6은 초대 만료 백엔드 구현과 테스트까지 확인했으나 rate limit/브라우저 검증이 남는다. 2.2.10 추천 실패 정책은 백엔드 구현·자동 테스트 PASS다. 2.2.14는 신규 확정 기록과 평가 API가 구현됐지만 과거 데이터 이관이 남는다. 2.6.3은 일정 백엔드 CRUD만 구현됐다. 알림 통합 및 P0 웹 시연은 진행 중이다. Notion WBS의 담당자·상태는 변경하지 않았다.
