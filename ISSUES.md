# ESP32 Atom Echo Arduino 코드 이슈 분석

> 분석일: 2026-02-06
> 대상: arduino/atom_echo_m5stack_esp32_ino/ 전체 소스

---

## 하드웨어 참조 (M5Stack Atom Echo)

| 항목 | 사양 |
|------|------|
| SoC | ESP32-PICO-D4, 240MHz Dual Core |
| SRAM | 520KB (가용 DRAM ~320KB) |
| Flash | 4MB |
| Speaker | NS4168 I2S (G22=DATA, G19=BCLK, G33=LRCK) |
| Microphone | SPM1423 PDM (G33=CLK, G23=DATA) |
| RGB LED | SK6812 on G27 |
| Button | G39 |
| 사용 가능 GPIO | G21, G25 (헤더), G26, G32 (Grove) |
| **예약 핀 (재사용 금지)** | **G19, G22, G23, G33** (I2S 오디오) |

---

## CRITICAL — 컴파일 실패 또는 즉시 크래시

### C1. config.h에 모든 #define 매크로 누락
- **파일**: `config.h`
- **현상**: extern 선언 4개만 존재. VAD_*, AUDIO_*, LED_COLOR_*, SERVO_*, PING_*, WIFI_* 매크로 전부 없음
- **영향**: **컴파일 불가** — vad.cpp, connection.cpp, protocol.cpp, audio_buffer.h, .ino 전부 미정의 심볼 에러
- **수정**: config.h.example의 모든 #define을 config.h에 추가

### C2. config.h.example 변수 다중 정의 충돌
- **파일**: `config.h.example`
- **현상**: `const char* SSID = "..."` 형태로 변수를 직접 정의. .ino에서도 동일 변수 정의
- **영향**: config.h.example을 config.h로 복사하면 **링크 에러** (multiple definition)
- **수정**: extern 패턴으로 통일

### C3. servo_stop() 후 서보 영구 비활성화
- **파일**: `servo_control.cpp`
- **현상**: `servo_stop()`이 `s_servo.detach()` 호출. 이후 `s_servo.write()` 호출 시 아무 동작 안 함
- **영향**: STOP 명령 후 서보가 영구적으로 작동 불능
- **수정**: detach 대신 중립 위치로 이동, 또는 write 전 자동 re-attach

### C4. FastLED + M5Unified LED 충돌
- **파일**: `led_control.cpp/h`
- **현상**: FastLED 라이브러리로 G27 SK6812 제어. M5Unified도 내부적으로 LED 관리
- **영향**: GPIO 27 제어권 충돌, LED 오동작 또는 I2S 타이밍 간섭
- **수정**: FastLED 제거, M5Unified 내장 LED API 사용

---

## HIGH — 런타임 오류/크래시 가능

### H1. ESP32Servo setPeriodHertz(50) 미호출
- **파일**: `servo_control.cpp`
- **현상**: `s_servo.attach(pin)` 호출 시 PWM 주파수 미설정
- **영향**: 서보 PWM 주파수가 기본값(잘못된 값)으로 설정되어 서보 오동작
- **수정**: attach 전 `s_servo.setPeriodHertz(50)` 호출

### H2. 서보 각도 범위 미검증
- **파일**: `servo_control.cpp`
- **현상**: `servo_set_angle(angle)` 에서 0-180 범위 클램핑 없음
- **영향**: 범위 초과 각도 전달 시 서보 손상 또는 예측 불가 동작
- **수정**: `constrain(angle, SERVO_MIN_ANGLE, SERVO_MAX_ANGLE)` 추가

### H3. frame_rms() double 연산 — ESP32 성능 저하
- **파일**: `.ino`
- **현상**: `double ss`, `double v` 사용. ESP32는 double FPU 없음
- **영향**: 소프트웨어 에뮬레이션으로 ~10배 느림. 20ms 프레임마다 호출되어 CPU 과부하
- **수정**: float로 변경

### H4. Mic.end()/Mic.begin() 매 루프 반복 호출
- **파일**: `.ino`
- **현상**: TTS 재생 중 매 loop()마다 Mic 상태 체크 → end/begin 반복 가능
- **영향**: I2S 재설정 비용 높음, DMA 버퍼 누수 가능, 오디오 글리치
- **수정**: 상태 플래그로 1회만 전환

### H5. protocol_send_packet partial write 과잉 대응
- **파일**: `protocol.cpp`
- **현상**: `client.write()` 반환값이 요청 크기와 다르면 즉시 `client.stop()`
- **영향**: 네트워크 지연 시 불필요한 연결 끊김 반복
- **수정**: 재시도 로직 또는 남은 바이트 전송

### H6. audio_ring_buffer malloc 실패 시 복구 없음
- **파일**: `protocol.cpp`
- **현상**: `handleAudioOut()`에서 malloc 실패 시 return만. 이후 호출에서도 계속 실패
- **영향**: TTS 오디오 재생 영구 불가
- **수정**: 초기화 시 할당 또는 재시도 로직

### H7. rx_audio_buf 무제한 할당
- **파일**: `protocol.cpp`
- **현상**: 수신 패킷 길이(rx_len)만큼 malloc. 최대 65535바이트
- **영향**: 악의적/오류 패킷으로 메모리 고갈 → 크래시
- **수정**: 최대 크기 제한 (예: 16KB)

### H8. audio_ring_push/pop byte-by-byte 복사
- **파일**: `protocol.cpp`
- **현상**: for 루프로 1바이트씩 복사
- **영향**: 32KB 버퍼 처리 시 심각한 성능 저하
- **수정**: memcpy + wrap-around 처리

---

## MEDIUM — 안정성/신뢰성 저하

### M1. WiFi.reconnect() 불안정
- **파일**: `connection.cpp`
- **현상**: `WiFi.disconnect()` → `WiFi.reconnect()` 패턴 사용
- **영향**: 일부 ESP32 Arduino 코어 버전에서 재연결 실패
- **수정**: `WiFi.begin(ssid, pass)` 사용

### M2. server_connected 상태 미동기화
- **파일**: `connection.cpp`
- **현상**: TCP 연결이 조용히 끊겨도 server_connected가 true 유지
- **영향**: 데이터 전송 실패 시까지 끊김 감지 불가
- **수정**: client.connected() 체크 추가

### M3. protocol_poll byte-by-byte 수신
- **파일**: `protocol.cpp`
- **현상**: `client.read()` 1바이트씩 호출
- **영향**: 대량 오디오 데이터 수신 시 심각한 지연
- **수정**: available() 크기만큼 벌크 읽기

### M4. PREROLL_SAMPLES가 0일 때 방어 없음
- **파일**: `audio_buffer.h`, `vad.cpp`
- **현상**: AUDIO_SAMPLE_RATE 또는 PREROLL_MS가 0이면 PREROLL_SAMPLES=0
- **영향**: 크기 0 배열 생성, preroll_push에서 즉시 wrap → 무한 루프 가능
- **수정**: static_assert 또는 최소값 보장

### M5. 기능 가이드와 코드 불일치
- **현상**: 가이드는 서보 핀 G26, 코드는 G25 사용. 가이드의 VAD 파라미터(MIN_TALK_MS=300, SILENCE_END_MS=600, MAX_TALK_MS=12000)와 config.h.example 값(500, 350, 8000) 불일치
- **영향**: 사용자 혼란, 예상과 다른 동작

---

## LOW — 코드 품질/유지보수

### L1. .ino에 WiFi 자격증명 하드코딩
### L2. Speaker 볼륨 중복 설정 (setup + handleAudioOut)
### L3. PONG 패킷 수신 처리 없음
### L4. preroll_send uint16_t 오버플로 미방어
### L5. 기능 가이드의 LED 색상과 코드 불일치 (idle=파란색 vs 가이드=초록색)
