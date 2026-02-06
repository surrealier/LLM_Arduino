// ============================================================
// config.h — 프로젝트 전역 설정 헤더
// ============================================================
// 역할: 모든 모듈(.ino, .cpp)이 참조하는 단일 설정 소스.
//       WiFi/서버 변수는 extern 선언만 하고, 실제 값은 .ino에서 정의.
//       나머지 하드웨어·동작 파라미터는 #define 매크로로 제공.
//
// 사용법: config.h.example을 config.h로 복사 후 WiFi/서버 정보를
//         .ino 파일에서 수정하세요.
// ============================================================

#ifndef CONFIG_H
#define CONFIG_H

// ────────────────────────────────────────────
// WiFi 설정 (실제 값은 .ino에서 정의)
// ────────────────────────────────────────────
extern const char* SSID;     // WiFi SSID
extern const char* PASS;     // WiFi 비밀번호

// ────────────────────────────────────────────
// 서버 설정 (실제 값은 .ino에서 정의)
// ────────────────────────────────────────────
extern const char* SERVER_IP;      // PC 서버 IP 주소
extern const uint16_t SERVER_PORT; // TCP 포트 (기본 5001)

// ────────────────────────────────────────────
// 서보 모터 설정
// ────────────────────────────────────────────
// SERVO_PIN: Atom Echo에서 사용 가능한 GPIO 25 (헤더 핀)
// MIN/MAX/CENTER: 서보 물리적 회전 범위 및 기본 위치
#define SERVO_PIN 25
#define SERVO_MIN_ANGLE 0
#define SERVO_MAX_ANGLE 180
#define SERVO_CENTER_ANGLE 90

// ────────────────────────────────────────────
// VAD (Voice Activity Detection) 설정
// ────────────────────────────────────────────
// NOISE_ALPHA: 노이즈 플로어 지수이동평균 계수 (1에 가까울수록 느리게 적응)
// ON_MULTIPLIER: 음성 시작 판정 임계값 = noise_floor × 이 값
// OFF_MULTIPLIER: 침묵 판정 임계값 = noise_floor × 이 값
// MIN_TALK_MS: 이 시간 이상 말해야 유효한 발화로 인정
// SILENCE_END_MS: 이 시간 이상 침묵하면 발화 종료
// MAX_TALK_MS: 최대 발화 시간 (타임아웃)
// INITIAL_NOISE_FLOOR: 부팅 직후 초기 노이즈 추정값
#define VAD_NOISE_ALPHA 0.995f
#define VAD_ON_MULTIPLIER 3.0f
#define VAD_OFF_MULTIPLIER 1.8f
#define VAD_MIN_TALK_MS 500
#define VAD_SILENCE_END_MS 350
#define VAD_MAX_TALK_MS 8000
#define VAD_INITIAL_NOISE_FLOOR 120.0f

// ────────────────────────────────────────────
// 오디오 설정
// ────────────────────────────────────────────
// SAMPLE_RATE: SPM1423 PDM 마이크 → I2S 샘플레이트
// FRAME_SIZE: 1프레임 = 320샘플 = 20ms @16kHz
// PREROLL_MS: VAD 시작 전 미리 버퍼링하는 시간 (발화 앞부분 보존)
// RING_BUFFER_SIZE: TTS 재생용 링 버퍼 크기 (약 1초 분량)
// ENABLE_BUTTON_INTERRUPT: 1이면 버튼으로 TTS 재생 중단 가능
#define AUDIO_SAMPLE_RATE 16000
#define AUDIO_FRAME_SIZE 320
#define PREROLL_MS 200
#define AUDIO_RING_BUFFER_SIZE 32768
#define ENABLE_BUTTON_INTERRUPT 1

// ────────────────────────────────────────────
// 연결 설정
// ────────────────────────────────────────────
// WIFI_RECONNECT_INTERVAL_MS: WiFi/서버 재연결 시도 간격
// PING_INTERVAL_MS: 서버 keepalive PING 전송 간격
#define WIFI_RECONNECT_INTERVAL_MS 5000
#define PING_INTERVAL_MS 3000

// ────────────────────────────────────────────
// LED 색상 (RGB) — SK6812 on GPIO 27
// ────────────────────────────────────────────
// CONNECTING: 빨강 — WiFi/서버 연결 시도 중
// IDLE: 파랑 — 대기 상태 (서버 연결 완료)
// RECORDING: 초록 — 음성 녹음 중
// PLAYING: 노랑 — TTS 재생 중
#define LED_COLOR_CONNECTING_R 255
#define LED_COLOR_CONNECTING_G 0
#define LED_COLOR_CONNECTING_B 0

#define LED_COLOR_IDLE_R 0
#define LED_COLOR_IDLE_G 0
#define LED_COLOR_IDLE_B 255

#define LED_COLOR_RECORDING_R 0
#define LED_COLOR_RECORDING_G 255
#define LED_COLOR_RECORDING_B 0

#define LED_COLOR_PLAYING_R 255
#define LED_COLOR_PLAYING_G 255
#define LED_COLOR_PLAYING_B 0

// ────────────────────────────────────────────
// 프로토콜 수신 버퍼 제한
// ────────────────────────────────────────────
// RX_AUDIO_MAX_ALLOC: 대형 오디오 패킷 수신 시 동적 할당 상한 (16KB)
// ESP32 DRAM ~320KB 중 안전한 범위 내에서 설정
#define RX_AUDIO_MAX_ALLOC 16384

// ============================================
// Servo Settings
// ============================================
#define SERVO_PIN 25
#define SERVO_MIN_ANGLE 0
#define SERVO_MAX_ANGLE 180
#define SERVO_CENTER_ANGLE 90

// ============================================
// VAD (Voice Activity Detection) Settings
// ============================================
#define VAD_NOISE_ALPHA 0.995f
#define VAD_ON_MULTIPLIER 3.0f
#define VAD_OFF_MULTIPLIER 1.8f
#define VAD_MIN_TALK_MS 500
#define VAD_SILENCE_END_MS 350
#define VAD_MAX_TALK_MS 8000
#define VAD_INITIAL_NOISE_FLOOR 120.0f

// ============================================
// Audio Settings
// ============================================
#define AUDIO_SAMPLE_RATE 16000
#define AUDIO_FRAME_SIZE 320
#define PREROLL_MS 200
#define AUDIO_RING_BUFFER_SIZE 32768
#define ENABLE_BUTTON_INTERRUPT 1

// ============================================
// Connection Settings
// ============================================
#define WIFI_RECONNECT_INTERVAL_MS 5000
#define PING_INTERVAL_MS 3000

// ============================================
// LED Colors (RGB)
// ============================================
#define LED_COLOR_CONNECTING_R 255
#define LED_COLOR_CONNECTING_G 0
#define LED_COLOR_CONNECTING_B 0

#define LED_COLOR_IDLE_R 0
#define LED_COLOR_IDLE_G 0
#define LED_COLOR_IDLE_B 255

#define LED_COLOR_RECORDING_R 0
#define LED_COLOR_RECORDING_G 255
#define LED_COLOR_RECORDING_B 0

#define LED_COLOR_PLAYING_R 255
#define LED_COLOR_PLAYING_G 255
#define LED_COLOR_PLAYING_B 0

#endif // CONFIG_H
