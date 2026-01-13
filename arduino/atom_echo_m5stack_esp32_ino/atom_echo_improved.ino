#include <M5Unified.h>
#include <WiFi.h>
#include <math.h>
#include <string.h>
#include <ctype.h>
#include <ESP32Servo.h>

// ===== Configuration =====
#define SERVO_PIN 25
Servo myServo;

const char* SSID = "KT_GiGA_3926";
const char* PASS = "fbx7bef119";
const char* SERVER_IP = "172.30.1.20";
const uint16_t SERVER_PORT = 5001;

WiFiClient client;

// ===== State Machine =====
enum State { IDLE, TALKING };
State state = IDLE;

// ===== Audio Config =====
static constexpr uint32_t SR = 16000;
static constexpr size_t FRAME = 320;
static constexpr uint32_t FRAME_MS = 20;

// Pre-roll buffer
static constexpr uint32_t PREROLL_MS = 200;
static constexpr size_t PREROLL_SAMPLES = (SR * PREROLL_MS) / 1000;
static int16_t preroll_buf[PREROLL_SAMPLES];
static size_t preroll_pos = 0;
static bool preroll_full = false;

// ===== VAD Parameters =====
static float noise_floor = 120.0f;
static constexpr float NOISE_ALPHA = 0.995f;
static constexpr float VAD_ON_MUL = 3.0f;
static constexpr float VAD_OFF_MUL = 1.8f;

static constexpr uint32_t MIN_TALK_MS = 500;
static constexpr uint32_t SILENCE_END_MS = 350;
static constexpr uint32_t MAX_TALK_MS = 8000;

static uint32_t talk_samples = 0;
static uint32_t silence_samples = 0;
static uint8_t start_hit = 0;

// ===== Packet Types =====
static constexpr uint8_t PTYPE_START = 0x01;
static constexpr uint8_t PTYPE_AUDIO = 0x02;
static constexpr uint8_t PTYPE_END = 0x03;
static constexpr uint8_t PTYPE_PING = 0x10;
static constexpr uint8_t PTYPE_PONG = 0x1F;
static constexpr uint8_t PTYPE_CMD = 0x11;
static constexpr uint8_t PTYPE_AUDIO_OUT = 0x12;

static uint32_t last_ping_ms = 0;
static constexpr uint32_t PING_INTERVAL_MS = 3000;

// ===== Connection Management =====
static unsigned long last_connect_attempt = 0;
static constexpr unsigned long CONNECT_INTERVAL_MS = 5000;
static bool wifi_connected = false;
static bool server_connected = false;

// ===== RX State Machine =====
enum RxStage { RX_TYPE, RX_LEN0, RX_LEN1, RX_PAYLOAD };
static RxStage rx_stage = RX_TYPE;
static uint8_t rx_type = 0;
static uint16_t rx_len = 0;
static uint16_t rx_pos = 0;
static constexpr size_t RX_MAX_PAYLOAD = 512;
static uint8_t rx_buf[RX_MAX_PAYLOAD];

// Audio playback buffer
static constexpr size_t AUDIO_BUFFER_MAX = 32768;
static uint8_t* rx_audio_buf = nullptr;
static size_t rx_audio_buf_size = 0;

// ===== Forward Declarations =====
static bool sendPacket(uint8_t type, const uint8_t* payload, uint16_t len);
static void sendPingIfNeeded();
static void manageConnections();
static void handleRxByte(uint8_t b);
static void handleCmdJson(const uint8_t* payload, uint16_t len);
static void handleAudioOut(const uint8_t* payload, uint16_t len);
static float frame_rms(const int16_t* x, size_t n);
static void preroll_push(const int16_t* x, size_t n);
static void send_preroll();
static bool json_get_string(const char* json, const char* key, char* out, size_t out_sz);
static bool json_get_int(const char* json, const char* key, int* out);
static bool json_get_bool(const char* json, const char* key, bool* out);

// ===== Setup =====
void setup() {
  auto cfg = M5.config();
  M5.begin(cfg);
  
  Serial.begin(115200);
  delay(500);
  Serial.println("\n=== M5Stack Atom Echo - LLM IoT ===");
  
  // Servo init
  myServo.attach(SERVO_PIN);
  myServo.write(90);
  Serial.println("Servo initialized at 90 degrees");
  
  // WiFi init
  WiFi.mode(WIFI_STA);
  WiFi.begin(SSID, PASS);
  Serial.print("Connecting to WiFi");
  
  // LED: Red while connecting
  M5.dis.drawpix(0, 0xFF0000);
  
  // Mic init
  auto spk_cfg = M5.Speaker.config();
  M5.Speaker.config(spk_cfg);
  M5.Speaker.begin();
  M5.Speaker.setVolume(200);
  
  auto mic_cfg = M5.Mic.config();
  mic_cfg.sample_rate = SR;
  M5.Mic.config(mic_cfg);
  M5.Mic.begin();
  
  Serial.println("\nMic & Speaker initialized");
  Serial.println("System ready!");
}

// ===== Main Loop =====
void loop() {
  M5.update();
  
  // Connection management
  manageConnections();
  
  if (!server_connected) {
    delay(100);
    return;
  }
  
  // Send periodic ping
  sendPingIfNeeded();
  
  // Handle incoming data
  while (client.available()) {
    uint8_t b = client.read();
    handleRxByte(b);
  }
  
  // Audio recording logic
  if (M5.Mic.isEnabled()) {
    static int16_t frame_buf[FRAME];
    
    if (M5.Mic.record(frame_buf, FRAME, SR)) {
      float rms = frame_rms(frame_buf, FRAME);
      
      // Update noise floor
      if (state == IDLE) {
        noise_floor = NOISE_ALPHA * noise_floor + (1.0f - NOISE_ALPHA) * rms;
      }
      
      float thr_on = noise_floor * VAD_ON_MUL;
      float thr_off = noise_floor * VAD_OFF_MUL;
      bool voice = (rms > thr_on);
      
      if (state == IDLE) {
        preroll_push(frame_buf, FRAME);
        
        if (voice) {
          start_hit++;
          if (start_hit >= 2) {
            // Start talking
            state = TALKING;
            talk_samples = 0;
            silence_samples = 0;
            
            M5.dis.drawpix(0, 0x00FF00); // Green LED
            Serial.println("🎙️ Recording started");
            
            if (sendPacket(PTYPE_START, nullptr, 0)) {
              send_preroll();
            }
          }
        } else {
          start_hit = 0;
        }
      } else if (state == TALKING) {
        // Send audio frame
        sendPacket(PTYPE_AUDIO, (uint8_t*)frame_buf, FRAME * sizeof(int16_t));
        
        talk_samples += FRAME;
        uint32_t talk_ms = (talk_samples * 1000) / SR;
        
        if (rms > thr_off) {
          silence_samples = 0;
        } else {
          silence_samples += FRAME;
        }
        
        uint32_t silence_ms = (silence_samples * 1000) / SR;
        
        // End conditions
        bool end_silence = (talk_ms >= MIN_TALK_MS && silence_ms >= SILENCE_END_MS);
        bool end_timeout = (talk_ms >= MAX_TALK_MS);
        
        if (end_silence || end_timeout) {
          sendPacket(PTYPE_END, nullptr, 0);
          
          state = IDLE;
          start_hit = 0;
          M5.dis.drawpix(0, 0x0000FF); // Blue LED
          
          Serial.printf("🛑 Recording ended (%.2fs)\n", talk_ms / 1000.0f);
        }
      }
    }
  }
  
  delay(1);
}

// ===== Connection Management =====
static void manageConnections() {
  unsigned long now = millis();
  
  // WiFi check
  if (WiFi.status() != WL_CONNECTED) {
    wifi_connected = false;
    server_connected = false;
    
    if (now - last_connect_attempt > CONNECT_INTERVAL_MS) {
      Serial.println("📡 Reconnecting WiFi...");
      WiFi.disconnect();
      WiFi.reconnect();
      last_connect_attempt = now;
      M5.dis.drawpix(0, 0xFF0000); // Red LED
    }
    return;
  }
  
  if (!wifi_connected) {
    wifi_connected = true;
    Serial.println("✅ WiFi Connected!");
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
  }
  
  // Server check
  if (!client.connected()) {
    server_connected = false;
    
    if (now - last_connect_attempt > CONNECT_INTERVAL_MS) {
      Serial.printf("🔌 Connecting to %s:%d...\n", SERVER_IP, SERVER_PORT);
      
      if (client.connect(SERVER_IP, SERVER_PORT)) {
        client.setNoDelay(true);
        server_connected = true;
        
        // Reset RX state
        rx_stage = RX_TYPE;
        rx_len = 0;
        rx_pos = 0;
        
        M5.Speaker.stop();
        M5.dis.drawpix(0, 0x0000FF); // Blue LED
        
        Serial.println("✅ Server Connected!");
        sendPacket(PTYPE_PING, nullptr, 0);
      } else {
        Serial.println("❌ Server connection failed");
        M5.dis.drawpix(0, 0xFF0000); // Red LED
      }
      
      last_connect_attempt = now;
    }
  }
}

// ===== Packet Sending =====
static bool sendPacket(uint8_t type, const uint8_t* payload, uint16_t len) {
  if (!client.connected()) {
    server_connected = false;
    return false;
  }
  
  size_t written = client.write(&type, 1);
  if (written != 1) {
    Serial.println("⚠️ Write failed (type)");
    client.stop();
    server_connected = false;
    return false;
  }
  
  uint8_t le[2] = { (uint8_t)(len & 0xFF), (uint8_t)((len >> 8) & 0xFF) };
  written = client.write(le, 2);
  if (written != 2) {
    Serial.println("⚠️ Write failed (len)");
    client.stop();
    server_connected = false;
    return false;
  }
  
  if (len && payload) {
    written = client.write(payload, len);
    if (written != len) {
      Serial.println("⚠️ Write failed (payload)");
      client.stop();
      server_connected = false;
      return false;
    }
  }
  
  return true;
}

static void sendPingIfNeeded() {
  uint32_t now = millis();
  if (now - last_ping_ms >= PING_INTERVAL_MS) {
    if (sendPacket(PTYPE_PING, nullptr, 0)) {
      last_ping_ms = now;
    }
  }
}

// ===== RX Handler =====
static void handleRxByte(uint8_t b) {
  switch (rx_stage) {
    case RX_TYPE:
      rx_type = b;
      rx_stage = RX_LEN0;
      break;
      
    case RX_LEN0:
      rx_len = b;
      rx_stage = RX_LEN1;
      break;
      
    case RX_LEN1:
      rx_len |= ((uint16_t)b << 8);
      rx_pos = 0;
      
      if (rx_len == 0) {
        // Empty payload
        if (rx_type == PTYPE_PONG) {
          // Pong received
        }
        rx_stage = RX_TYPE;
      } else {
        rx_stage = RX_PAYLOAD;
        
        // Allocate audio buffer if needed
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
        // Large audio buffer
        if (rx_audio_buf && rx_pos < rx_audio_buf_size) {
          rx_audio_buf[rx_pos++] = b;
        }
      } else {
        // Normal buffer
        if (rx_pos < RX_MAX_PAYLOAD) {
          rx_buf[rx_pos++] = b;
        }
      }
      
      if (rx_pos >= rx_len) {
        // Payload complete
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

// ===== Audio Playback =====
static void handleAudioOut(const uint8_t* payload, uint16_t len) {
  if (len < 2) return;
  
  Serial.printf("🔊 Playing audio: %d bytes\n", len);
  
  // Stop recording during playback
  bool was_recording = (state == TALKING);
  if (was_recording) {
    sendPacket(PTYPE_END, nullptr, 0);
    state = IDLE;
  }
  
  M5.dis.drawpix(0, 0xFFFF00); // Yellow LED during playback
  
  // Play audio
  int16_t* samples = (int16_t*)payload;
  size_t sample_count = len / 2;
  
  M5.Speaker.playRaw(samples, sample_count, SR, false, 1, 0);
  
  // Wait for playback to finish
  while (M5.Speaker.isPlaying()) {
    delay(10);
  }
  
  M5.dis.drawpix(0, 0x0000FF); // Back to blue
  Serial.println("🔊 Playback finished");
}

// ===== Command Handler =====
static void handleCmdJson(const uint8_t* payload, uint16_t len) {
  static char json[RX_MAX_PAYLOAD + 1];
  uint16_t n = (len > RX_MAX_PAYLOAD) ? RX_MAX_PAYLOAD : len;
  memcpy(json, payload, n);
  json[n] = 0;
  
  Serial.println("\n===== 📥 CMD from Server =====");
  Serial.print("JSON: ");
  Serial.println(json);
  
  char action[32] = {0};
  int sid = -1;
  int angle = -1;
  bool meaningful = false;
  bool recognized = false;
  
  bool has_action = json_get_string(json, "action", action, sizeof(action));
  json_get_int(json, "sid", &sid);
  bool has_angle = json_get_int(json, "angle", &angle);
  json_get_bool(json, "meaningful", &meaningful);
  json_get_bool(json, "recognized", &recognized);
  
  Serial.print("Action: ");
  Serial.println(has_action ? action : "(none)");
  if (has_angle) {
    Serial.print("Angle: ");
    Serial.println(angle);
  }
  
  // Execute action
  if (has_action) {
    if (strcmp(action, "SERVO_SET") == 0 && has_angle) {
      myServo.write(angle);
      Serial.printf("✅ Servo moved to %d degrees\n", angle);
      M5.dis.drawpix(0, 0x00FF00); // Green flash
      delay(100);
      M5.dis.drawpix(0, 0x0000FF);
      
    } else if (strcmp(action, "WIGGLE") == 0) {
      int current = myServo.read();
      myServo.write(current + 10);
      delay(150);
      myServo.write(current - 10);
      delay(150);
      myServo.write(current);
      Serial.println("✅ Wiggle executed");
      
    } else if (strcmp(action, "STOP") == 0) {
      Serial.println("✅ Stop command received");
      
    } else if (strcmp(action, "NOOP") == 0) {
      Serial.println("ℹ️ No operation");
    }
  }
  
  Serial.println("===========================\n");
}

// ===== Audio Processing =====
static float frame_rms(const int16_t* x, size_t n) {
  double ss = 0.0;
  for (size_t i = 0; i < n; i++) {
    double v = (double)x[i];
    ss += v * v;
  }
  return (float)sqrt(ss / (double)n);
}

static void preroll_push(const int16_t* x, size_t n) {
  for (size_t i = 0; i < n; i++) {
    preroll_buf[preroll_pos++] = x[i];
    if (preroll_pos >= PREROLL_SAMPLES) {
      preroll_pos = 0;
      preroll_full = true;
    }
  }
}

static void send_preroll() {
  size_t count = preroll_full ? PREROLL_SAMPLES : preroll_pos;
  if (count == 0) return;
  
  if (!preroll_full) {
    sendPacket(PTYPE_AUDIO, (uint8_t*)preroll_buf, (uint16_t)(count * sizeof(int16_t)));
    return;
  }
  
  size_t tail = PREROLL_SAMPLES - preroll_pos;
  if (tail > 0) {
    sendPacket(PTYPE_AUDIO, (uint8_t*)(preroll_buf + preroll_pos), (uint16_t)(tail * sizeof(int16_t)));
  }
  if (preroll_pos > 0) {
    sendPacket(PTYPE_AUDIO, (uint8_t*)preroll_buf, (uint16_t)(preroll_pos * sizeof(int16_t)));
  }
}

// ===== JSON Parsers =====
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
  if (*p == '-') { neg = true; p++; }
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
  if (!strncmp(p, "true", 4)) { *out = true; return true; }
  if (!strncmp(p, "false", 5)) { *out = false; return true; }
  return false;
}
