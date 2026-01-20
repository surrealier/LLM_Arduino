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
  led_set_color(255, 0, 0);

  connection_init(&conn_state, SSID, PASS);

  auto spk_cfg = M5.Speaker.config();
  M5.Speaker.config(spk_cfg);
  M5.Speaker.begin();
  M5.Speaker.setVolume(255);  // 최대 볼륨으로 설정

  auto mic_cfg = M5.Mic.config();
  mic_cfg.sample_rate = SR;
  M5.Mic.config(mic_cfg);
  M5.Mic.begin();

  protocol_init();
  vad_init(&vad_state);
  preroll_init(&preroll);
}

void loop() {
  M5.update();
  connection_manage(&conn_state, client);

  if (!connection_is_server_connected(&conn_state)) {
    delay(100);
    return;
  }

  protocol_send_ping_if_needed(client);
  protocol_poll(client);

  if (M5.Mic.isEnabled()) {
    static int16_t frame_buf[FRAME];
    if (M5.Mic.record(frame_buf, FRAME, SR)) {
      float rms = frame_rms(frame_buf, FRAME);

      if (!vad_state.talking) {
        preroll_push(&preroll, frame_buf, FRAME);
      }

      VadEvent event = vad_update(&vad_state, rms, FRAME, SR);

      if (event == VAD_START) {
        led_set_color(0, 255, 0);
        if (protocol_send_packet(client, PTYPE_START, nullptr, 0)) {
          preroll_send(&preroll, client);
        }
      } else if (event == VAD_CONTINUE) {
        protocol_send_packet(client, PTYPE_AUDIO, (uint8_t*)frame_buf, FRAME * sizeof(int16_t));
      } else if (event == VAD_END) {
        protocol_send_packet(client, PTYPE_END, nullptr, 0);
        led_set_color(0, 0, 255);
      }
    }
  }

  led_update_pattern();
  delay(1);
}
