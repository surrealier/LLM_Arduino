#include "protocol.h"
#include "config.h"
#include "led_control.h"
#include "servo_control.h"
#include <M5Unified.h>
#include <ctype.h>
#include <string.h>
#include <stdlib.h>

static constexpr size_t RX_MAX_PAYLOAD = 2048;  // 512에서 2048로 증가

#ifndef AUDIO_RING_BUFFER_SIZE
#define AUDIO_RING_BUFFER_SIZE 32768  // 기본값: 32KB
#endif
static constexpr size_t AUDIO_PLAY_BUFFER_SIZE = AUDIO_RING_BUFFER_SIZE;

enum RxStage { RX_TYPE, RX_LEN0, RX_LEN1, RX_PAYLOAD };
static RxStage rx_stage = RX_TYPE;
static uint8_t rx_type = 0;
static uint16_t rx_len = 0;
static uint16_t rx_pos = 0;
static uint8_t rx_buf[RX_MAX_PAYLOAD];
static uint8_t* rx_audio_buf = nullptr;
static size_t rx_audio_buf_size = 0;

// 오디오 스트리밍을 위한 링 버퍼
static uint8_t* audio_ring_buffer = nullptr;
static size_t audio_ring_head = 0;
static size_t audio_ring_tail = 0;
static size_t audio_ring_size = AUDIO_PLAY_BUFFER_SIZE;
static bool audio_playing = false;

static uint32_t last_ping_ms = 0;

static bool json_get_string(const char* json, const char* key, char* out, size_t out_sz) {
  char pat[64];
  snprintf(pat, sizeof(pat), "\"%s\"", key);
  const char* p = strstr(json, pat);
  if (!p) return false;
  p = strchr(p, ':');
  if (!p) return false;
  p++;
  while (*p && isspace((unsigned char)*p)) p++;
  if (*p != '"') return false;
  p++;
  size_t i = 0;
  while (*p && *p != '"' && i + 1 < out_sz) {
    out[i++] = *p++;
  }
  out[i] = 0;
  return (*p == '"');
}

static bool json_get_int(const char* json, const char* key, int* out) {
  char pat[64];
  snprintf(pat, sizeof(pat), "\"%s\"", key);
  const char* p = strstr(json, pat);
  if (!p) return false;
  p = strchr(p, ':');
  if (!p) return false;
  p++;
  while (*p && isspace((unsigned char)*p)) p++;
  bool neg = false;
  if (*p == '-') {
    neg = true;
    p++;
  }
  if (!isdigit((unsigned char)*p)) return false;
  long v = 0;
  while (isdigit((unsigned char)*p)) {
    v = v * 10 + (*p - '0');
    p++;
  }
  if (neg) v = -v;
  *out = (int)v;
  return true;
}

static bool json_get_bool(const char* json, const char* key, bool* out) {
  char pat[64];
  snprintf(pat, sizeof(pat), "\"%s\"", key);
  const char* p = strstr(json, pat);
  if (!p) return false;
  p = strchr(p, ':');
  if (!p) return false;
  p++;
  while (*p && isspace((unsigned char)*p)) p++;
  if (!strncmp(p, "true", 4)) {
    *out = true;
    return true;
  }
  if (!strncmp(p, "false", 5)) {
    *out = false;
    return true;
  }
  return false;
}

// 링 버퍼에 사용 가능한 공간 계산
static size_t audio_ring_available() {
  if (audio_ring_head >= audio_ring_tail) {
    return audio_ring_size - (audio_ring_head - audio_ring_tail) - 1;
  } else {
    return audio_ring_tail - audio_ring_head - 1;
  }
}

// 링 버퍼에 저장된 데이터 크기 계산
static size_t audio_ring_used() {
  if (audio_ring_head >= audio_ring_tail) {
    return audio_ring_head - audio_ring_tail;
  } else {
    return audio_ring_size - (audio_ring_tail - audio_ring_head);
  }
}

// 링 버퍼에 데이터 추가
static bool audio_ring_push(const uint8_t* data, size_t len) {
  if (audio_ring_available() < len) {
    // 버퍼가 가득 찼을 때: 오래된 데이터를 버리고 새 데이터 추가
    size_t to_drop = len - audio_ring_available() + 1024; // 여유 공간 확보
    if (to_drop > audio_ring_used()) {
      to_drop = audio_ring_used();
    }
    
    Serial.printf("[AUDIO_RING] Buffer nearly full! Dropping %d bytes of old data\n", to_drop);
    
    // tail을 앞으로 이동하여 오래된 데이터 제거
    audio_ring_tail = (audio_ring_tail + to_drop) % audio_ring_size;
    
    // 여전히 공간이 부족하면 실패
    if (audio_ring_available() < len) {
      Serial.println("[AUDIO_RING] Still no space after dropping data!");
      return false;
    }
  }
  
  for (size_t i = 0; i < len; i++) {
    audio_ring_buffer[audio_ring_head] = data[i];
    audio_ring_head = (audio_ring_head + 1) % audio_ring_size;
  }
  return true;
}

// 링 버퍼에서 데이터 읽기
static size_t audio_ring_pop(uint8_t* data, size_t max_len) {
  size_t used = audio_ring_used();
  size_t to_read = (used < max_len) ? used : max_len;
  
  for (size_t i = 0; i < to_read; i++) {
    data[i] = audio_ring_buffer[audio_ring_tail];
    audio_ring_tail = (audio_ring_tail + 1) % audio_ring_size;
  }
  return to_read;
}

static void handleAudioOut(const uint8_t* payload, uint16_t len) {
  if (len < 2) {
    Serial.println("[AUDIO_OUT] Error: payload too short");
    return;
  }
  
  // 링 버퍼 초기화 (처음 실행 시)
  if (audio_ring_buffer == nullptr) {
    audio_ring_buffer = (uint8_t*)malloc(audio_ring_size);
    if (audio_ring_buffer == nullptr) {
      Serial.println("[AUDIO_OUT] Failed to allocate ring buffer!");
      return;
    }
    audio_ring_head = 0;
    audio_ring_tail = 0;
  }
  
  // 데이터를 링 버퍼에 추가
  if (!audio_ring_push(payload, len)) {
    Serial.println("[AUDIO_OUT] Warning: Buffer overflow, dropping audio data");
    return;
  }
  
  Serial.printf("[AUDIO_OUT] Buffered %d bytes (total: %d bytes)\n", len, audio_ring_used());
  
  // 재생 시작 (충분한 데이터가 모이면)
  if (!audio_playing && audio_ring_used() >= 4096) {
    audio_playing = true;
    M5.Speaker.setVolume(255);
    Serial.println("[AUDIO_OUT] Starting playback");
  }
}

static void handleCmdJson(const uint8_t* payload, uint16_t len) {
  static char json[RX_MAX_PAYLOAD + 1];
  uint16_t n = (len > RX_MAX_PAYLOAD) ? RX_MAX_PAYLOAD : len;
  memcpy(json, payload, n);
  json[n] = 0;

  char action[32] = {0};
  int sid = -1;
  int angle = -1;
  bool meaningful = false;
  bool recognized = false;
  char emotion[32] = {0};
  char servo_action[32] = {0};

  bool has_action = json_get_string(json, "action", action, sizeof(action));
  json_get_int(json, "sid", &sid);
  bool has_angle = json_get_int(json, "angle", &angle);
  json_get_bool(json, "meaningful", &meaningful);
  json_get_bool(json, "recognized", &recognized);
  json_get_string(json, "emotion", emotion, sizeof(emotion));
  json_get_string(json, "servo_action", servo_action, sizeof(servo_action));

  if (has_action && strcmp(action, "EMOTION") == 0) {
    led_show_emotion(emotion);
    if (strcmp(servo_action, "WIGGLE_FAST") == 0 || strcmp(servo_action, "WIGGLE") == 0) {
      servo_wiggle();
    } else if (strcmp(servo_action, "NOD") == 0) {
      servo_set_angle(110);
      servo_set_angle(SERVO_CENTER_ANGLE);
    } else if (strcmp(servo_action, "CENTER") == 0) {
      servo_set_angle(SERVO_CENTER_ANGLE);
    }
    return;
  }

  if (!meaningful) {
    if (strcmp(action, "WIGGLE") == 0) {
      servo_wiggle();
    }
    return;
  }

  if (strcmp(action, "ROTATE") == 0) {
    servo_rotate();
  } else if (strcmp(action, "STOP") == 0) {
    servo_stop();
  } else if (strcmp(action, "SERVO_SET") == 0 && has_angle) {
    servo_set_angle(angle);
  }
}

void protocol_init() {
  rx_stage = RX_TYPE;
  rx_len = 0;
  rx_pos = 0;
}

bool protocol_send_packet(WiFiClient& client, uint8_t type, const uint8_t* payload, uint16_t len) {
  if (!client.connected()) return false;

  size_t written = client.write(&type, 1);
  if (written != 1) {
    client.stop();
    return false;
  }

  uint8_t le[2] = {(uint8_t)(len & 0xFF), (uint8_t)((len >> 8) & 0xFF)};
  written = client.write(le, 2);
  if (written != 2) {
    client.stop();
    return false;
  }

  if (len && payload) {
    written = client.write(payload, len);
    if (written != len) {
      client.stop();
      return false;
    }
  }
  return true;
}

void protocol_poll(WiFiClient& client) {
  if (!client.connected()) return;
  while (client.available() > 0) {
    int b = client.read();
    if (b < 0) {
      client.stop();
      break;
    }

    uint8_t byte = (uint8_t)b;
    switch (rx_stage) {
      case RX_TYPE:
        rx_type = byte;
        rx_len = 0;
        rx_pos = 0;
        rx_stage = RX_LEN0;
        break;

      case RX_LEN0:
        rx_len = (uint16_t)byte;
        rx_stage = RX_LEN1;
        break;

      case RX_LEN1:
        rx_len |= ((uint16_t)byte << 8);
        rx_pos = 0;
        if (rx_len == 0) {
          rx_stage = RX_TYPE;
        } else {
          rx_stage = RX_PAYLOAD;
          if (rx_type == PTYPE_AUDIO_OUT && rx_len > RX_MAX_PAYLOAD) {
            if (rx_audio_buf == nullptr || rx_audio_buf_size < rx_len) {
              if (rx_audio_buf) free(rx_audio_buf);
              rx_audio_buf = (uint8_t*)malloc(rx_len);
              rx_audio_buf_size = rx_len;
            }
          }
        }
        break;

      case RX_PAYLOAD:
        if (rx_type == PTYPE_AUDIO_OUT && rx_len > RX_MAX_PAYLOAD) {
          if (rx_audio_buf && rx_pos < rx_audio_buf_size) {
            rx_audio_buf[rx_pos++] = byte;
          }
        } else {
          if (rx_pos < RX_MAX_PAYLOAD) {
            rx_buf[rx_pos++] = byte;
          }
        }

        if (rx_pos >= rx_len) {
          if (rx_type == PTYPE_CMD) {
            handleCmdJson(rx_buf, rx_len);
          } else if (rx_type == PTYPE_AUDIO_OUT) {
            if (rx_len > RX_MAX_PAYLOAD) {
              handleAudioOut(rx_audio_buf, rx_len);
            } else {
              handleAudioOut(rx_buf, rx_len);
            }
          }
          rx_stage = RX_TYPE;
        }
        break;
    }
  }
}

void protocol_send_ping_if_needed(WiFiClient& client) {
  uint32_t now = millis();
  if (now - last_ping_ms >= PING_INTERVAL_MS) {
    if (protocol_send_packet(client, PTYPE_PING, nullptr, 0)) {
      last_ping_ms = now;
    }
  }
}

void protocol_audio_process() {
  if (!audio_playing) {
    return;
  }
  
  // 스피커가 재생 중이 아니고 버퍼에 데이터가 있으면 재생
  if (!M5.Speaker.isPlaying() && audio_ring_used() > 0) {
    // 링 버퍼에서 데이터 읽기 (최대 8KB씩)
    static uint8_t play_buffer[8192];
    size_t chunk_size = audio_ring_pop(play_buffer, sizeof(play_buffer));
    
    if (chunk_size >= 2) {
      // 샘플 단위로 정렬 (2바이트씩)
      chunk_size = (chunk_size / 2) * 2;
      size_t samples = chunk_size / 2;
      
      Serial.printf("[AUDIO_PROC] Playing %d samples (%d bytes), buffer remaining: %d\n", 
                    samples, chunk_size, audio_ring_used());
      
      // 비블로킹 모드로 재생
      M5.Speaker.playRaw((const int16_t*)play_buffer, samples, 16000, false, 1, 0);
    }
  }
  
  // 버퍼가 비고 재생도 완료되면 재생 중단
  if (audio_ring_used() == 0 && !M5.Speaker.isPlaying()) {
    audio_playing = false;
    Serial.println("[AUDIO_PROC] Playback complete");
  }
}

bool protocol_is_audio_playing() {
  return audio_playing || M5.Speaker.isPlaying();
}

void protocol_clear_audio_buffer() {
  if (audio_ring_buffer != nullptr) {
    audio_ring_head = 0;
    audio_ring_tail = 0;
    audio_playing = false;
    M5.Speaker.stop();
    Serial.println("[AUDIO] Buffer cleared");
  }
}
