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

#define SERVO_PIN 25

// Config variable definitions
const char* SSID = "KT_GiGA_3926";
const char* PASS = "fbx7bef119";
const char* SERVER_IP = "172.30.1.20";
const uint16_t SERVER_PORT = 5001;

static constexpr uint32_t SR = 16000;
static constexpr size_t FRAME = 320;

WiFiClient client;
ConnectionState conn_state;
VadState vad_state;
PrerollBuffer preroll;

static inline float frame_rms(const int16_t* x, size_t n) {
  double ss = 0.0;
  for (size_t i = 0; i < n; i++) {
    double v = (double)x[i];
    ss += v * v;
  }
  return (float)sqrt(ss / (double)n);
}

void setup() {
  auto cfg = M5.config();
  M5.begin(cfg);
  Serial.begin(115200);
  delay(500);

  led_init();
  servo_init(SERVO_PIN);
  led_set_color(LED_COLOR_CONNECTING_R, LED_COLOR_CONNECTING_G, LED_COLOR_CONNECTING_B);

  connection_init(&conn_state, SSID, PASS);

  auto spk_cfg = M5.Speaker.config();
  M5.Speaker.config(spk_cfg);
  M5.Speaker.begin();
  M5.Speaker.setVolume(255);  // 최대 볼륨으로 설정

  auto mic_cfg = M5.Mic.config();
  mic_cfg.sample_rate = AUDIO_SAMPLE_RATE;
  M5.Mic.config(mic_cfg);
  M5.Mic.begin();

  protocol_init();
  vad_init(&vad_state);
  preroll_init(&preroll);
}

void loop() {
  M5.update();
  
  // 버튼 누르면 TTS 재생 중단 (인터럽트 기능)
  #ifndef ENABLE_BUTTON_INTERRUPT
  #define ENABLE_BUTTON_INTERRUPT 1
  #endif
  
  #if ENABLE_BUTTON_INTERRUPT
  if (M5.BtnA.wasPressed()) {
    if (protocol_is_audio_playing()) {
      protocol_clear_audio_buffer();
      Serial.println("[BUTTON] TTS playback interrupted by user");
    }
  }
  #endif
  
  connection_manage(&conn_state, client);

  if (!connection_is_server_connected(&conn_state)) {
    delay(100);
    return;
  }

  protocol_send_ping_if_needed(client);
  protocol_poll(client);
  protocol_audio_process();  // 오디오 스트리밍 처리

  // TTS 재생 중인지 확인
  bool is_playing = protocol_is_audio_playing();
  
  // Half-duplex: TTS 재생 중에는 마이크 비활성화
  if (is_playing && M5.Mic.isEnabled()) {
    M5.Mic.end();
    Serial.println("[MIC] Disabled during TTS playback");
    // VAD 상태 초기화
    vad_init(&vad_state);
    preroll_init(&preroll);
  } else if (!is_playing && !M5.Mic.isEnabled()) {
    // TTS 재생 완료 후 마이크 재활성화
    auto mic_cfg = M5.Mic.config();
    mic_cfg.sample_rate = AUDIO_SAMPLE_RATE;
    M5.Mic.config(mic_cfg);
    M5.Mic.begin();
    Serial.println("[MIC] Re-enabled after TTS playback");
  }

  // 마이크가 활성화되어 있고 TTS가 재생 중이 아닐 때만 음성 입력 처리
  if (M5.Mic.isEnabled() && !is_playing) {
    static int16_t frame_buf[AUDIO_FRAME_SIZE];
    if (M5.Mic.record(frame_buf, AUDIO_FRAME_SIZE, AUDIO_SAMPLE_RATE)) {
      float rms = frame_rms(frame_buf, AUDIO_FRAME_SIZE);

      if (!vad_state.talking) {
        preroll_push(&preroll, frame_buf, AUDIO_FRAME_SIZE);
      }

      VadEvent event = vad_update(&vad_state, rms, AUDIO_FRAME_SIZE, AUDIO_SAMPLE_RATE);

      if (event == VAD_START) {
        led_set_color(LED_COLOR_RECORDING_R, LED_COLOR_RECORDING_G, LED_COLOR_RECORDING_B);
        if (protocol_send_packet(client, PTYPE_START, nullptr, 0)) {
          preroll_send(&preroll, client);
        }
      } else if (event == VAD_CONTINUE) {
        protocol_send_packet(client, PTYPE_AUDIO, (uint8_t*)frame_buf, AUDIO_FRAME_SIZE * sizeof(int16_t));
      } else if (event == VAD_END) {
        protocol_send_packet(client, PTYPE_END, nullptr, 0);
        led_set_color(LED_COLOR_IDLE_R, LED_COLOR_IDLE_G, LED_COLOR_IDLE_B);
      }
    }
  }

  led_update_pattern();
  servo_update();
  delay(1);
}
