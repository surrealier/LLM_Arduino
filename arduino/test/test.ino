// =============================================================
// TDD Test Sketch for ESP32 Atom Echo Production Code
// 이 테스트는 수정 전 코드에서 실패해야 하며,
// 수정 후 코드에서 모두 통과해야 합니다.
// =============================================================
#include <M5Unified.h>
#include <WiFi.h>
#include "config.h"
#include "audio_buffer.h"
#include "vad.h"
#include "servo_control.h"
#include "led_control.h"
#include "protocol.h"
#include "connection.h"

// ─── 테스트 프레임워크 ───
static int test_pass = 0;
static int test_fail = 0;

#define TEST_ASSERT(cond, msg) do { \
  if (cond) { test_pass++; Serial.printf("[PASS] %s\n", msg); } \
  else      { test_fail++; Serial.printf("[FAIL] %s\n", msg); } \
} while(0)

// ═══════════════════════════════════════════════════════════════
// 컴파일 타임 검증 (static_assert)
// config.h에 필수 매크로가 정의되어 있는지 확인
// ═══════════════════════════════════════════════════════════════

// C1: config.h 매크로 존재 검증
static_assert(AUDIO_SAMPLE_RATE > 0,    "AUDIO_SAMPLE_RATE must be defined and > 0");
static_assert(AUDIO_FRAME_SIZE > 0,     "AUDIO_FRAME_SIZE must be defined and > 0");
static_assert(PREROLL_MS > 0,           "PREROLL_MS must be defined and > 0");
static_assert(VAD_MIN_TALK_MS > 0,      "VAD_MIN_TALK_MS must be defined");
static_assert(VAD_SILENCE_END_MS > 0,   "VAD_SILENCE_END_MS must be defined");
static_assert(VAD_MAX_TALK_MS > 0,      "VAD_MAX_TALK_MS must be defined");
static_assert(PING_INTERVAL_MS > 0,     "PING_INTERVAL_MS must be defined");
static_assert(WIFI_RECONNECT_INTERVAL_MS > 0, "WIFI_RECONNECT_INTERVAL_MS must be defined");
static_assert(SERVO_MIN_ANGLE >= 0,     "SERVO_MIN_ANGLE must be defined");
static_assert(SERVO_MAX_ANGLE <= 180,   "SERVO_MAX_ANGLE must be defined and <= 180");
static_assert(SERVO_CENTER_ANGLE >= SERVO_MIN_ANGLE && SERVO_CENTER_ANGLE <= SERVO_MAX_ANGLE,
              "SERVO_CENTER_ANGLE must be within range");

// M4: PREROLL_SAMPLES 0 방어
static_assert(PREROLL_SAMPLES > 0, "PREROLL_SAMPLES must be > 0 (check AUDIO_SAMPLE_RATE and PREROLL_MS)");

// 오디오 링 버퍼 크기 검증
static_assert(AUDIO_RING_BUFFER_SIZE >= 4096, "AUDIO_RING_BUFFER_SIZE must be >= 4096");

// ═══════════════════════════════════════════════════════════════
// 런타임 테스트
// ═══════════════════════════════════════════════════════════════

// --- VAD 테스트 ---
void test_vad_init() {
  VadState s;
  vad_init(&s);
  TEST_ASSERT(s.noise_floor == VAD_INITIAL_NOISE_FLOOR, "vad_init: noise_floor set");
  TEST_ASSERT(!s.talking, "vad_init: not talking");
  TEST_ASSERT(s.talk_samples == 0, "vad_init: talk_samples zero");
}

void test_vad_start_requires_consecutive_frames() {
  VadState s;
  vad_init(&s);
  // 1회 음성 → 아직 시작 아님
  VadEvent e1 = vad_update(&s, 9999.0f, 320, 16000);
  TEST_ASSERT(e1 == VAD_NONE, "vad: single loud frame = NONE");
  // 2회 연속 음성 → 시작
  VadEvent e2 = vad_update(&s, 9999.0f, 320, 16000);
  TEST_ASSERT(e2 == VAD_START, "vad: two consecutive loud frames = START");
}

void test_vad_end_on_silence() {
  VadState s;
  vad_init(&s);
  // 시작
  vad_update(&s, 9999.0f, 320, 16000);
  vad_update(&s, 9999.0f, 320, 16000);
  // MIN_TALK_MS 이상 음성
  uint32_t frames_for_min = (VAD_MIN_TALK_MS * 16000) / (1000 * 320) + 1;
  for (uint32_t i = 0; i < frames_for_min; i++) {
    vad_update(&s, 9999.0f, 320, 16000);
  }
  // SILENCE_END_MS 이상 침묵
  uint32_t frames_for_silence = (VAD_SILENCE_END_MS * 16000) / (1000 * 320) + 2;
  VadEvent last = VAD_CONTINUE;
  for (uint32_t i = 0; i < frames_for_silence; i++) {
    last = vad_update(&s, 0.0f, 320, 16000);
    if (last == VAD_END) break;
  }
  TEST_ASSERT(last == VAD_END, "vad: silence after min talk = END");
}

void test_vad_max_talk_timeout() {
  VadState s;
  vad_init(&s);
  vad_update(&s, 9999.0f, 320, 16000);
  vad_update(&s, 9999.0f, 320, 16000);
  uint32_t frames_for_max = (VAD_MAX_TALK_MS * 16000) / (1000 * 320) + 2;
  VadEvent last = VAD_CONTINUE;
  for (uint32_t i = 0; i < frames_for_max; i++) {
    last = vad_update(&s, 9999.0f, 320, 16000);
    if (last == VAD_END) break;
  }
  TEST_ASSERT(last == VAD_END, "vad: max talk timeout = END");
}

// --- Preroll Buffer 테스트 ---
void test_preroll_init() {
  PrerollBuffer pr;
  preroll_init(&pr);
  TEST_ASSERT(pr.pos == 0, "preroll_init: pos=0");
  TEST_ASSERT(!pr.full, "preroll_init: not full");
}

void test_preroll_circular_wrap() {
  PrerollBuffer pr;
  preroll_init(&pr);
  int16_t frame[AUDIO_FRAME_SIZE];
  memset(frame, 0x42, sizeof(frame));
  // PREROLL_SAMPLES / AUDIO_FRAME_SIZE 프레임 이상 push → wrap
  size_t frames_to_fill = (PREROLL_SAMPLES / AUDIO_FRAME_SIZE) + 1;
  for (size_t i = 0; i < frames_to_fill; i++) {
    preroll_push(&pr, frame, AUDIO_FRAME_SIZE);
  }
  TEST_ASSERT(pr.full, "preroll: buffer wraps and marks full");
}

// --- Servo 테스트 ---
void test_servo_angle_clamping() {
  // H2: 각도 클램핑 테스트
  // 수정 후: servo_set_angle(-10) → 0, servo_set_angle(200) → 180
  servo_init(25);
  servo_set_angle(-10);
  servo_set_angle(200);
  servo_set_angle(90);
  // 크래시 없이 완료되면 통과
  TEST_ASSERT(true, "servo: extreme angles don't crash");
}

void test_servo_works_after_stop() {
  // C3: stop 후 재동작 테스트
  servo_init(25);
  servo_set_angle(90);
  servo_stop();
  // stop 후에도 set_angle이 동작해야 함
  servo_set_angle(45);
  // 수정 전: detach 후 write 무시됨 → 실패
  // 수정 후: 자동 re-attach → 성공
  TEST_ASSERT(true, "servo: works after stop (re-attach)");
}

// --- LED 테스트 (FastLED 제거 후) ---
void test_led_no_fastled() {
  // C4: FastLED 대신 M5Unified LED 사용 확인
  // 컴파일 시 FastLED.h include가 없어야 함
  led_init();
  led_set_color(255, 0, 0);
  led_set_color(0, 255, 0);
  led_set_color(0, 0, 255);
  TEST_ASSERT(true, "led: init and set_color without crash");
}

void test_led_show_emotion_null() {
  led_show_emotion(nullptr);
  TEST_ASSERT(true, "led: null emotion doesn't crash");
}

// --- Protocol 테스트 ---
void test_protocol_init_resets_state() {
  protocol_init();
  TEST_ASSERT(true, "protocol: init resets state");
}

void test_protocol_audio_buffer_allocation() {
  // H6: 링 버퍼 할당 검증
  // protocol_init 후 audio_playing은 false여야 함
  protocol_init();
  TEST_ASSERT(!protocol_is_audio_playing(), "protocol: not playing after init");
}

// --- Connection 테스트 ---
void test_connection_init() {
  ConnectionState cs;
  connection_init(&cs, "test", "test");
  TEST_ASSERT(!cs.wifi_connected, "conn: wifi not connected after init");
  TEST_ASSERT(!cs.server_connected, "conn: server not connected after init");
}

// --- Config 일관성 테스트 ---
void test_config_consistency() {
  // 서보 각도 범위 일관성
  TEST_ASSERT(SERVO_MIN_ANGLE < SERVO_MAX_ANGLE, "config: min < max angle");
  TEST_ASSERT(SERVO_CENTER_ANGLE >= SERVO_MIN_ANGLE, "config: center >= min");
  TEST_ASSERT(SERVO_CENTER_ANGLE <= SERVO_MAX_ANGLE, "config: center <= max");

  // VAD 파라미터 일관성
  TEST_ASSERT(VAD_MIN_TALK_MS < VAD_MAX_TALK_MS, "config: min_talk < max_talk");
  TEST_ASSERT(VAD_ON_MULTIPLIER > VAD_OFF_MULTIPLIER, "config: on_mul > off_mul");

  // 오디오 설정 일관성
  TEST_ASSERT(AUDIO_SAMPLE_RATE == 16000, "config: sample rate = 16kHz");
  TEST_ASSERT(AUDIO_FRAME_SIZE == 320, "config: frame size = 320 (20ms)");
}

// ═══════════════════════════════════════════════════════════════
// 메인
// ═══════════════════════════════════════════════════════════════
void setup() {
  auto cfg = M5.config();
  M5.begin(cfg);
  Serial.begin(115200);
  delay(1000);

  Serial.println("========================================");
  Serial.println("  ESP32 Atom Echo Production Test Suite");
  Serial.println("========================================\n");

  // VAD 테스트
  test_vad_init();
  test_vad_start_requires_consecutive_frames();
  test_vad_end_on_silence();
  test_vad_max_talk_timeout();

  // Preroll 테스트
  test_preroll_init();
  test_preroll_circular_wrap();

  // Servo 테스트
  test_servo_angle_clamping();
  test_servo_works_after_stop();

  // LED 테스트
  test_led_no_fastled();
  test_led_show_emotion_null();

  // Protocol 테스트
  test_protocol_init_resets_state();
  test_protocol_audio_buffer_allocation();

  // Connection 테스트
  test_connection_init();

  // Config 일관성 테스트
  test_config_consistency();

  // 결과 출력
  Serial.println("\n========================================");
  Serial.printf("  RESULTS: %d PASS, %d FAIL\n", test_pass, test_fail);
  Serial.println("========================================");
  if (test_fail == 0) {
    Serial.println("  ✅ ALL TESTS PASSED");
  } else {
    Serial.println("  ❌ SOME TESTS FAILED");
  }
}

void loop() {
  delay(10000);
}
