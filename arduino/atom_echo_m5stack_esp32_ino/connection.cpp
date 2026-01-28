#include "connection.h"
#include "config.h"
#include "led_control.h"
#include "protocol.h"
#include <M5Unified.h>

void connection_init(ConnectionState* state, const char* ssid, const char* pass) {
  state->last_connect_attempt = 0;
  state->wifi_connected = false;
  state->server_connected = false;

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, pass);
  led_set_color(LED_COLOR_CONNECTING_R, LED_COLOR_CONNECTING_G, LED_COLOR_CONNECTING_B);
}

void connection_manage(ConnectionState* state, WiFiClient& client) {
  unsigned long now = millis();

  if (WiFi.status() != WL_CONNECTED) {
    state->wifi_connected = false;
    state->server_connected = false;
    if (now - state->last_connect_attempt > WIFI_RECONNECT_INTERVAL_MS) {
      WiFi.disconnect();
      delay(100);
      WiFi.reconnect();
      state->last_connect_attempt = now;
      led_set_color(LED_COLOR_CONNECTING_R, LED_COLOR_CONNECTING_G, LED_COLOR_CONNECTING_B);
    }
    return;
  }

  if (!state->wifi_connected) {
    state->wifi_connected = true;
  }

  if (!client.connected()) {
    state->server_connected = false;

    if (now - state->last_connect_attempt > WIFI_RECONNECT_INTERVAL_MS) {
      if (client.connect(SERVER_IP, SERVER_PORT)) {
        client.setNoDelay(true);
        state->server_connected = true;
        protocol_init();
        M5.Speaker.stop();
        led_set_color(LED_COLOR_IDLE_R, LED_COLOR_IDLE_G, LED_COLOR_IDLE_B);
      } else {
        led_set_color(LED_COLOR_CONNECTING_R, LED_COLOR_CONNECTING_G, LED_COLOR_CONNECTING_B);
      }
      state->last_connect_attempt = now;
    }
  }
}

bool connection_is_server_connected(const ConnectionState* state) {
  return state->server_connected;
}
