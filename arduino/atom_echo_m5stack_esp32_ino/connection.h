#ifndef CONNECTION_H
#define CONNECTION_H

#include <WiFi.h>

struct ConnectionState {
  unsigned long last_connect_attempt;
  bool wifi_connected;
  bool server_connected;
};

void connection_init(ConnectionState* state, const char* ssid, const char* pass);
void connection_manage(ConnectionState* state, WiFiClient& client);
bool connection_is_server_connected(const ConnectionState* state);

#endif
