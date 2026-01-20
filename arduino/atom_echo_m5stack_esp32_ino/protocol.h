#ifndef PROTOCOL_H
#define PROTOCOL_H

#include <WiFi.h>
#include <stdint.h>

static constexpr uint8_t PTYPE_START = 0x01;
static constexpr uint8_t PTYPE_AUDIO = 0x02;
static constexpr uint8_t PTYPE_END = 0x03;
static constexpr uint8_t PTYPE_PING = 0x10;
static constexpr uint8_t PTYPE_PONG = 0x1F;
static constexpr uint8_t PTYPE_CMD = 0x11;
static constexpr uint8_t PTYPE_AUDIO_OUT = 0x12;
static constexpr uint8_t PTYPE_AUDIO_OUT_END = 0x13;

void protocol_init();
bool protocol_send_packet(WiFiClient& client, uint8_t type, const uint8_t* payload, uint16_t len);
void protocol_poll(WiFiClient& client);
void protocol_send_ping_if_needed(WiFiClient& client);

#endif
