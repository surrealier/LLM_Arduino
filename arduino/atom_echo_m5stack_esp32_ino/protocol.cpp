#include "protocol.h"
#include "led_control.h"
#include "servo_control.h"
#include <M5Unified.h>
#include <ctype.h>
#include <string.h>
#include <stdlib.h>

static constexpr size_t RX_MAX_PAYLOAD = 512;
static constexpr size_t AUDIO_BUFFER_MAX = 524288;  // 512KB (충분히 큰 버퍼)

enum RxStage { RX_TYPE, RX_LEN0, RX_LEN1, RX_PAYLOAD };
static RxStage rx_stage = RX_TYPE;
static uint8_t rx_type = 0;
static uint16_t rx_len = 0;
static uint16_t rx_pos = 0;
static uint8_t rx_buf[RX_MAX_PAYLOAD];
static uint8_t* rx_audio_buf = nullptr;
static size_t rx_audio_buf_size = 0;

// 오디오 스트림 누적 버퍼
static uint8_t* audio_stream_buf = nullptr;
static size_t audio_stream_buf_size = 0;
static size_t audio_stream_pos = 0;

static uint32_t last_ping_ms = 0;
static constexpr uint32_t PING_INTERVAL_MS = 3000;

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

static void handleAudioOut(const uint8_t* payload, uint16_t len) {
  // #region agent log
  size_t free_heap_before = ESP.getFreeHeap();
  size_t max_alloc_before = ESP.getMaxAllocHeap();
  Serial.printf("[DEBUG_H1] handleAudioOut entry: free_heap=%d, max_alloc=%d, current_buf_size=%d, current_pos=%d\n", 
                free_heap_before, max_alloc_before, audio_stream_buf_size, audio_stream_pos);
  // #endregion
  
  if (len < 2) {
    Serial.println("[AUDIO_OUT] Error: payload too short");
    return;
  }
  
  // 버퍼에 누적 (즉시 재생하지 않음)
  size_t needed = audio_stream_pos + len;
  
  // #region agent log
  Serial.printf("[DEBUG_H2] needed=%d, len=%d, AUDIO_BUFFER_MAX=%d\n", needed, len, AUDIO_BUFFER_MAX);
  // #endregion
  
  if (audio_stream_buf == nullptr || audio_stream_buf_size < needed) {
    size_t new_size = (needed > AUDIO_BUFFER_MAX) ? needed : AUDIO_BUFFER_MAX;
    
    // #region agent log
    Serial.printf("[DEBUG_H3] Before realloc: new_size=%d, old_size=%d, free_heap=%d, max_alloc=%d\n", 
                  new_size, audio_stream_buf_size, ESP.getFreeHeap(), ESP.getMaxAllocHeap());
    // #endregion
    
    uint8_t* new_buf = (uint8_t*)realloc(audio_stream_buf, new_size);
    if (new_buf == nullptr) {
      // #region agent log
      Serial.printf("[DEBUG_H4] REALLOC FAILED: requested=%d, free_heap=%d, max_alloc=%d, old_buf=%p\n", 
                    new_size, ESP.getFreeHeap(), ESP.getMaxAllocHeap(), audio_stream_buf);
      // #endregion
      
      Serial.println("[AUDIO_OUT] Error: memory allocation failed");
      return;
    }
    
    // #region agent log
    Serial.printf("[DEBUG_H3] After realloc success: new_buf=%p, free_heap=%d\n", 
                  new_buf, ESP.getFreeHeap());
    // #endregion
    
    audio_stream_buf = new_buf;
    audio_stream_buf_size = new_size;
  }
  
  memcpy(audio_stream_buf + audio_stream_pos, payload, len);
  audio_stream_pos += len;
  
  Serial.printf("[AUDIO_OUT] Buffered %d bytes (total: %d bytes)\n", len, audio_stream_pos);
}

static void handleAudioOutEnd() {
  // #region agent log
  Serial.printf("[DEBUG_H5] handleAudioOutEnd entry: audio_stream_pos=%d, buf_size=%d, free_heap=%d\n", 
                audio_stream_pos, audio_stream_buf_size, ESP.getFreeHeap());
  // #endregion
  
  if (audio_stream_pos < 2) {
    Serial.println("[AUDIO_OUT_END] No audio data to play");
    audio_stream_pos = 0;
    return;
  }
  
  size_t samples = audio_stream_pos / 2;
  const int16_t* pcm = (const int16_t*)audio_stream_buf;
  
  Serial.printf("[AUDIO_OUT_END] Playing %d samples (%d bytes) in one go\n", samples, audio_stream_pos);
  
  // 볼륨 최대로 확인
  M5.Speaker.setVolume(255);
  
  // 전체 오디오를 한 번에 재생 (블로킹 모드)
  M5.Speaker.playRaw(pcm, samples, 16000, false, 1, 0);
  
  // 재생 완료까지 대기
  while (M5.Speaker.isPlaying()) {
    delay(1);
  }
  
  Serial.println("[AUDIO_OUT_END] Playback complete");
  
  // 버퍼 초기화
  audio_stream_pos = 0;
  
  // #region agent log
  Serial.printf("[DEBUG_H5] After playback: audio_stream_pos=%d, free_heap=%d\n", 
                audio_stream_pos, ESP.getFreeHeap());
  // #endregion
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
      delay(200);
      servo_set_angle(90);
    } else if (strcmp(servo_action, "CENTER") == 0) {
      servo_set_angle(90);
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
    delay(3000);
    servo_stop();
  }
}

void protocol_init() {
  rx_stage = RX_TYPE;
  rx_len = 0;
  rx_pos = 0;
  audio_stream_pos = 0;
  
  // #region agent log
  Serial.printf("[DEBUG_H1] protocol_init: free_heap=%d, max_alloc=%d\n", 
                ESP.getFreeHeap(), ESP.getMaxAllocHeap());
  // #endregion
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
            // #region agent log
            Serial.printf("[DEBUG_H4] Large AUDIO_OUT packet: rx_len=%d, current_rx_audio_buf_size=%d, free_heap=%d\n", 
                          rx_len, rx_audio_buf_size, ESP.getFreeHeap());
            // #endregion
            
            if (rx_audio_buf == nullptr || rx_audio_buf_size < rx_len) {
              if (rx_audio_buf) free(rx_audio_buf);
              rx_audio_buf = (uint8_t*)malloc(rx_len);
              rx_audio_buf_size = rx_len;
              
              // #region agent log
              Serial.printf("[DEBUG_H4] rx_audio_buf malloc: requested=%d, result=%p, free_heap=%d\n", 
                            rx_len, rx_audio_buf, ESP.getFreeHeap());
              // #endregion
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
          } else if (rx_type == PTYPE_AUDIO_OUT_END) {
            handleAudioOutEnd();
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
