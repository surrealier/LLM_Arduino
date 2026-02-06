// ============================================================
// connection.cpp — WiFi/서버 연결 관리 구현
// ============================================================
// 역할: WiFi AP 연결 및 TCP 서버 연결을 관리.
//       끊김 감지 시 WIFI_RECONNECT_INTERVAL_MS 간격으로 재시도.
//
// 주요 설계 결정:
//   - WiFi.reconnect() 대신 WiFi.begin(ssid, pass) 사용
//     (일부 ESP32 Arduino 코어에서 reconnect() 불안정)
//   - server_connected를 client.connected()와 매 루프 동기화
//     (TCP 연결이 조용히 끊겨도 즉시 감지)
// ============================================================

#include "connection.h"
#include "config.h"
#include "led_control.h"
#include "protocol.h"
#include <M5Unified.h>

// WiFi 자격증명 캐시 (재연결 시 WiFi.begin()에 전달)
static const char* s_ssid = nullptr;
static const char* s_pass = nullptr;

// connection_init — WiFi STA 모드 설정 및 첫 연결 시도
void connection_init(ConnectionState* state, const char* ssid, const char* pass) {
  state->last_connect_attempt = 0;
  state->wifi_connected = false;
  state->server_connected = false;
  s_ssid = ssid;
  s_pass = pass;

  WiFi.mode(WIFI_STA);          // Station 모드 (AP가 아닌 클라이언트)
  WiFi.begin(ssid, pass);       // 비동기 연결 시작
  led_set_color(LED_COLOR_CONNECTING_R, LED_COLOR_CONNECTING_G, LED_COLOR_CONNECTING_B);
}

// connection_manage — 매 loop()에서 호출하여 연결 상태 관리
// 처리 순서: WiFi 확인 → WiFi 재연결 → 서버 확인 → 서버 재연결
void connection_manage(ConnectionState* state, WiFiClient& client) {
  unsigned long now = millis();

  // ── 1단계: WiFi AP 연결 확인 ──
  if (WiFi.status() != WL_CONNECTED) {
    if (state->wifi_connected) {
      // WiFi가 끊김 → 서버도 끊긴 것으로 처리
      state->wifi_connected = false;
      state->server_connected = false;
    }
    // 재연결 간격 체크 후 WiFi.begin() 재시도
    if (now - state->last_connect_attempt > WIFI_RECONNECT_INTERVAL_MS) {
      WiFi.disconnect(true);     // 이전 연결 정리 (auto-reconnect 비활성화)
      delay(50);                 // 안정화 대기
      WiFi.begin(s_ssid, s_pass);
      state->last_connect_attempt = now;
      led_set_color(LED_COLOR_CONNECTING_R, LED_COLOR_CONNECTING_G, LED_COLOR_CONNECTING_B);
    }
    return;  // WiFi 미연결 시 서버 연결 시도하지 않음
  }

  // WiFi 연결 성공 감지
  if (!state->wifi_connected) {
    state->wifi_connected = true;
  }

  // ── 2단계: TCP 서버 연결 상태 동기화 ──
  // server_connected 플래그와 실제 소켓 상태를 매 루프 동기화
  // (TCP RST 없이 조용히 끊긴 경우 대응)
  if (state->server_connected && !client.connected()) {
    state->server_connected = false;
  }

  // ── 3단계: TCP 서버 재연결 ──
  if (!client.connected()) {
    state->server_connected = false;
    if (now - state->last_connect_attempt > WIFI_RECONNECT_INTERVAL_MS) {
      if (client.connect(SERVER_IP, SERVER_PORT)) {
        client.setNoDelay(true);   // Nagle 알고리즘 비활성화 (저지연)
        state->server_connected = true;
        protocol_init();           // 수신 상태머신 리셋 (잔여 데이터 무효화)
        M5.Speaker.stop();         // 이전 재생 중단
        led_set_color(LED_COLOR_IDLE_R, LED_COLOR_IDLE_G, LED_COLOR_IDLE_B);
      } else {
        led_set_color(LED_COLOR_CONNECTING_R, LED_COLOR_CONNECTING_G, LED_COLOR_CONNECTING_B);
      }
      state->last_connect_attempt = now;
    }
  }
}

// connection_is_server_connected — 서버 연결 상태 조회
bool connection_is_server_connected(const ConnectionState* state) {
  return state->server_connected;
}
