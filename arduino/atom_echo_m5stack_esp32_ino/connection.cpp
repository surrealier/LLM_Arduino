#include "connection.h"
#include "config.h"
#include "led_control.h"
#include "protocol.h"
#include <M5Unified.h>

static constexpr unsigned long CONNECT_INTERVAL_MS = 5000;

void connection_init(ConnectionState* state, const char* ssid, const char* pass) {
  state->last_connect_attempt = 0;
  state->wifi_connected = false;
  state->server_connected = false;

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, pass);
  led_set_color(255, 0, 0);
}

void connection_manage(ConnectionState* state, WiFiClient& client) {
  unsigned long now = millis();

  if (WiFi.status() != WL_CONNECTED) {
    state->wifi_connected = false;
    state->server_connected = false;
    if (now - state->last_connect_attempt > CONNECT_INTERVAL_MS) {
      WiFi.disconnect();
      WiFi.reconnect();
      state->last_connect_attempt = now;
      led_set_color(255, 0, 0);
    }
    return;
  }

  if (!state->wifi_connected) {
    state->wifi_connected = true;
  }

  if (!client.connected()) {
    state->server_connected = false;

    if (now - state->last_connect_attempt > CONNECT_INTERVAL_MS) {
      if (client.connect(SERVER_IP, SERVER_PORT)) {
        client.setNoDelay(true);
        state->server_connected = true;
        protocol_init();
        M5.Speaker.stop();
        led_set_color(0, 0, 255);
      } else {
        led_set_color(255, 0, 0);
      }
      state->last_connect_attempt = now;
    }
  }
}

bool connection_is_server_connected(const ConnectionState* state) {
  return state->server_connected;
}
