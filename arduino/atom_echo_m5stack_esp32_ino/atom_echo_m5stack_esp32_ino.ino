// ============================================================
// atom_echo_m5stack_esp32_ino.ino — 메인 애플리케이션 엔트리포인트
// ============================================================
// 역할: M5Stack Atom Echo의 setup()/loop() 진입점.
//       모든 서브모듈(연결, 프로토콜, VAD, 오디오, LED, 서보)을
//       초기화하고, 메인 루프에서 협력적 멀티태스킹으로 구동.
//
// 동작 흐름:
//   setup() → 하드웨어 초기화 → WiFi 연결 시작
//   loop()  → 연결 관리 → 프로토콜 송수신 → TTS 재생 →
//             Half-duplex Mic 전환 → VAD 음성 감지 →
//             LED/서보 업데이트
//
// 하드웨어 핀 맵 (Atom Echo):
//   G22=SPK_DATA, G19=SPK_BCLK, G33=SPK_LRCK/MIC_CLK
//   G23=MIC_DATA, G27=SK6812_LED, G39=BUTTON
//   G25=SERVO (외부 연결), G26/G32=Grove
// ============================================================

#include <M5Unified.h>
#include <WiFi.h>
#include <math.h>
#include "config.h"
#include "audio_buffer.h"
#include "connection.h"
#include "led_control.h"
#include "protocol.h"
#include "servo_control.h"
#include "vad.h"

// ────────────────────────────────────────────
// 네트워크 자격증명 및 서버 주소 (여기서 실제 값 정의)
// config.h의 extern 선언에 대응하는 정의부
// ────────────────────────────────────────────
const char* SSID = "KT_GiGA_3926";
const char* PASS = "fbx7bef119";
const char* SERVER_IP = "172.30.1.20";
const uint16_t SERVER_PORT = 5001;

// ────────────────────────────────────────────
// 전역 상태 객체
// ────────────────────────────────────────────
WiFiClient client;           // TCP 소켓 (서버 연결용)
ConnectionState conn_state;  // WiFi/서버 연결 상태 머신
VadState vad_state;          // 음성 활동 감지 상태
PrerollBuffer preroll;       // VAD 시작 전 프리롤 오디오 버퍼

// Half-duplex 제어: TTS 재생 중 마이크 비활성화 추적
// M5.Mic.isEnabled() 대신 플래그를 사용하여 end/begin 반복 호출 방지
static bool mic_disabled = false;
static uint32_t last_play_end_ms = 0;
static bool was_playing_or_buffered = false;

// Reinitialize speaker after mic end (Atom Echo shares I2S lines).
// M5Unified Speaker task가 이미 살아있어도 I2S 드라이버는 Mic.begin/end로 바뀔 수 있으므로
// end()를 먼저 호출해 항상 스피커 I2S를 재설정한다.
static bool speaker_reinit() {
  M5.Speaker.stop();
  M5.Speaker.end();
  auto spk_cfg = M5.Speaker.config();
  spk_cfg.sample_rate = AUDIO_SAMPLE_RATE;
  M5.Speaker.config(spk_cfg);
  bool ok = M5.Speaker.begin();
  M5.Speaker.setVolume(180);
  if (!ok) {
    Serial.println("[AUDIO] Speaker begin failed");
  }
  return ok;
}

// Reinitialize microphone and release speaker I2S resources first.
static bool mic_reinit() {
  M5.Speaker.stop();
  M5.Speaker.end();
  M5.Mic.end();
  auto mic_cfg = M5.Mic.config();
  mic_cfg.sample_rate = AUDIO_SAMPLE_RATE;
  M5.Mic.config(mic_cfg);
  bool ok = M5.Mic.begin();
  if (!ok) {
    Serial.println("[AUDIO] Mic begin failed");
  }
  return ok;
}

// ────────────────────────────────────────────
// frame_rms — 오디오 프레임의 RMS(Root Mean Square) 계산
// ────────────────────────────────────────────
// 용도: VAD에서 현재 프레임의 음량 레벨을 측정
// 주의: ESP32는 double FPU가 없으므로 float 연산 사용 (성능 ~10배 차이)
static inline float frame_rms(const int16_t* x, size_t n) {
  float ss = 0.0f;
  for (size_t i = 0; i < n; i++) {
    float v = (float)x[i];
    ss += v * v;
  }
  return sqrtf(ss / (float)n);
}

// ============================================================
// setup() — 1회 실행: 모든 하드웨어 및 소프트웨어 모듈 초기화
// ============================================================
void setup() {
  // M5Unified 프레임워크 초기화 (I2S, LED, 버튼 등 자동 설정)
  auto cfg = M5.config();
  cfg.internal_mic = true;
  cfg.internal_spk = true;
  M5.begin(cfg);
  Serial.begin(115200);
  delay(500);  // 시리얼 안정화 대기

  // LED 초기화 → 연결 중 표시 (빨강)
  led_init();
  servo_init(SERVO_PIN);
  led_set_color(LED_COLOR_CONNECTING_R, LED_COLOR_CONNECTING_G, LED_COLOR_CONNECTING_B);

  // WiFi 연결 시작 (비동기, connection_manage에서 상태 추적)
  connection_init(&conn_state, SSID, PASS);

  auto spk_cfg = M5.Speaker.config();
  auto mic_cfg = M5.Mic.config();
  Serial.printf(
      "[BOOT] board=%d spk(bck=%d ws=%d dout=%d i2s=%d) mic(bck=%d ws=%d din=%d i2s=%d)\n",
      (int)M5.getBoard(),
      (int)spk_cfg.pin_bck,
      (int)spk_cfg.pin_ws,
      (int)spk_cfg.pin_data_out,
      (int)spk_cfg.i2s_port,
      (int)mic_cfg.pin_bck,
      (int)mic_cfg.pin_ws,
      (int)mic_cfg.pin_data_in,
      (int)mic_cfg.i2s_port);

  // 기본 대기 상태는 마이크 활성화(입력), 스피커는 I2S 리소스를 점유하지 않도록 종료
  mic_reinit();

  // 프로토콜 수신 상태머신, VAD, 프리롤 버퍼 초기화
  protocol_init();
  vad_init(&vad_state);
  preroll_init(&preroll);
}

// ============================================================
// loop() — 메인 루프: 협력적 멀티태스킹 (약 1ms 주기)
// ============================================================
void loop() {
  // M5Unified 내부 상태 갱신 (버튼, 터치 등)
  M5.update();

  // ── 버튼 인터럽트: TTS 재생 중 버튼 누르면 즉시 중단 ──
  #if ENABLE_BUTTON_INTERRUPT
  if (M5.BtnA.wasPressed()) {
    if (protocol_is_audio_playing()) {
      protocol_clear_audio_buffer();
      Serial.println("[BUTTON] TTS interrupted");
    }
  }
  #endif

  // ── 연결 관리: WiFi 재연결 + 서버 TCP 재연결 ──
  connection_manage(&conn_state, client);

  // 서버 미연결 시 100ms 대기 후 재시도 (CPU 절약)
  if (!connection_is_server_connected(&conn_state)) {
    delay(100);
    return;
  }

  // ── 프로토콜 송수신 ──
  protocol_send_ping_if_needed(client);  // 3초마다 keepalive PING
  protocol_poll(client);                  // 서버→ESP32 패킷 수신 및 디스패치
  // 오디오 재생은 마이크 전환 이후에 수행

  // ── Half-duplex 마이크/스피커 전환 ──
  // Atom Echo는 I2S 버스를 마이크와 스피커가 공유하므로
  // TTS 재생 중에는 마이크를 끄고, 재생 완료 후 다시 켬.
  // mic_disabled 플래그로 전환을 1회만 수행 (I2S 재설정 비용 절감)
  bool will_play = protocol_is_audio_playing() || protocol_has_audio_buffered();
  // 재생 종료 순간 기록 (버퍼까지 모두 비었을 때만 종료로 간주)
  if (was_playing_or_buffered && !will_play) {
    last_play_end_ms = millis();
  }
  was_playing_or_buffered = will_play;

  if (will_play && !mic_disabled) {
    // TTS 재생 시작 → 마이크 비활성화
    M5.Mic.end();
    if (speaker_reinit()) {
      mic_disabled = true;
      Serial.println("[AUDIO] Mic end -> Speaker reinit");
      vad_init(&vad_state);     // VAD 상태 리셋 (잔여 음성 데이터 무효화)
      preroll_init(&preroll);   // 프리롤 버퍼 리셋
    } else {
      // 스피커 초기화 실패 시 버퍼를 비우고 입력 모드로 복구
      protocol_clear_audio_buffer();
      mic_reinit();
      mic_disabled = false;
      Serial.println("[AUDIO] Speaker reinit failed -> Mic restored");
    }
  }

  protocol_audio_process();               // 링 버퍼 → 스피커 재생 처리

  bool is_playing = protocol_is_audio_playing();
  bool has_buffered_audio = protocol_has_audio_buffered();
  bool cooldown_done = (millis() - last_play_end_ms) >= 1000;
  if (!is_playing && !has_buffered_audio && cooldown_done && mic_disabled) {
    // TTS 재생 완료 → 마이크 재활성화
    mic_reinit();
    mic_disabled = false;
    Serial.println("[AUDIO] Mic begin (after TTS)");
  }

  // ── 음성 입력 처리 (마이크 활성 + TTS 미재생 시만) ──
  if (!mic_disabled && !is_playing && !has_buffered_audio && cooldown_done) {
    static int16_t frame_buf[AUDIO_FRAME_SIZE];  // 20ms 프레임 버퍼 (static: 스택 절약)

    if (M5.Mic.record(frame_buf, AUDIO_FRAME_SIZE, AUDIO_SAMPLE_RATE)) {
      // 현재 프레임의 음량(RMS) 계산
      float rms = frame_rms(frame_buf, AUDIO_FRAME_SIZE);

      // 아직 말하고 있지 않으면 프리롤 버퍼에 축적
      // (VAD_START 시 이 버퍼를 먼저 전송하여 발화 앞부분 보존)
      if (!vad_state.talking) {
        preroll_push(&preroll, frame_buf, AUDIO_FRAME_SIZE);
      }

      // VAD 상태 업데이트 → 이벤트에 따라 패킷 전송
      VadEvent event = vad_update(&vad_state, rms, AUDIO_FRAME_SIZE, AUDIO_SAMPLE_RATE);

      if (event == VAD_START) {
        // 발화 시작 감지 → LED 녹색 + START 패킷 + 프리롤 전송
        led_set_color(LED_COLOR_RECORDING_R, LED_COLOR_RECORDING_G, LED_COLOR_RECORDING_B);
        if (protocol_send_packet(client, PTYPE_START, nullptr, 0)) {
          preroll_send(&preroll, client);
        }
      } else if (event == VAD_CONTINUE) {
        // 발화 진행 중 → 현재 프레임을 AUDIO 패킷으로 전송
        protocol_send_packet(client, PTYPE_AUDIO, (uint8_t*)frame_buf, AUDIO_FRAME_SIZE * sizeof(int16_t));
      } else if (event == VAD_END) {
        // 발화 종료 → END 패킷 + LED 파랑(대기)
        protocol_send_packet(client, PTYPE_END, nullptr, 0);
        led_set_color(LED_COLOR_IDLE_R, LED_COLOR_IDLE_G, LED_COLOR_IDLE_B);
      }
    }
  }

  // ── 주변장치 업데이트 ──
  led_update_pattern();  // LED 애니메이션 패턴 (현재 placeholder)
  servo_update();        // 서보 비동기 동작 (회전/위글) 스텝 처리
  delay(1);              // Watchdog 피딩 + CPU 양보
}
