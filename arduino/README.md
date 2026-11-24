# PET DOCK Arduino

PET DOCK은 반려동물의 반응과 장치 상태를 확인하기 위한 Arduino 기반 하드웨어입니다. 버튼 입력은 USB Serial로 전송하고, RGB LED는 BLE 명령으로 제어합니다.

하드웨어 버튼은 펫 반응과 상태 확인 용도로만 사용하며 공동 승인 기능에는 연결하지 않습니다.

## 사용 부품

- Arduino UNO
- KEYES Bluetooth 4.0 V2
- 버튼 2개
- RGB LED 1개
- RGB LED 각 채널용 저항

## 배선

| 부품 | Arduino UNO | 비고 |
| --- | --- | --- |
| 버튼 A | D2 | `INPUT_PULLUP` 사용, 버튼 입력 시 GND 연결 |
| 버튼 B | D3 | `INPUT_PULLUP` 사용, 버튼 입력 시 GND 연결 |
| RGB LED Red | D9 | 채널 저항 사용 |
| RGB LED Green | D10 | 채널 저항 사용 |
| RGB LED Blue | D11 | 채널 저항 사용 |
| KEYES TXD | D4 | KEYES에서 Arduino로 수신 |
| KEYES VCC | 5V | 전원 |
| KEYES GND | GND | 공통 접지 |
| KEYES RXD | 연결하지 않음 | 현재 구성에서는 사용하지 않음 |

> **주의:** Arduino UNO D5와 KEYES RXD를 직접 연결하지 않습니다. 코드에서는 `SoftwareSerial bluetooth(4, 5)`로 D5가 송신 핀에 할당되어 있지만, 현재 실물 구성의 KEYES RXD는 연결하지 않은 상태입니다.

## 통신 및 신호

- USB Serial 통신 속도: 9600 baud
- BLE Serial 통신 속도: 9600 baud
- 버튼 A 신호: `BTN_A`
- 버튼 B 신호: `BTN_B`
- BLE 이름: `Meem`
- BLE 서비스 UUID: `FFE0`
- BLE 특성 UUID: `FFE1`

버튼을 누르면 디바운싱 처리 후 USB Serial로 해당 버튼 신호를 출력합니다. 버튼 입력은 BLE Notify가 아닌 USB 통신 방식입니다.

## RGB LED 명령

BLE 특성 `FFE1`로 아래 단일 문자 명령을 전송합니다.

| 명령 | 동작 |
| --- | --- |
| `R` | 빨간색 켜기 |
| `G` | 초록색 켜기 |
| `B` | 파란색 켜기 |
| `X` | LED 끄기 |

## 실물 테스트 결과

- 버튼 A 입력 10회 성공
- 버튼 B 입력 10회 성공
- BLE RGB LED 제어 10회 성공

## 현재 제한 사항

- 완전 무선 버튼 Notify 기능은 아직 구현되지 않았습니다.
- USB 분리 후 재연결 동작은 별도 검증이 필요합니다.

## 소스 코드

- [`PET_DOCK/PET_DOCK.ino`](PET_DOCK/PET_DOCK.ino)
