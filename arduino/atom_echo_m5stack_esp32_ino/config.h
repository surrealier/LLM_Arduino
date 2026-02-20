// Shared firmware configuration for ccoli.
// Credential values (SSID/PASS/SERVER_IP/SERVER_PORT) are defined in
// `device_secrets.h` and declared here as extern symbols.

#ifndef CONFIG_H
#define CONFIG_H

#include <stdint.h>

// Credentials / server target from device_secrets.h
extern const char* SSID;
extern const char* PASS;
extern const char* SERVER_IP;
extern const uint16_t SERVER_PORT;

// Servo settings
#define SERVO_PIN 25
#define SERVO_MIN_ANGLE 0
#define SERVO_MAX_ANGLE 180
#define SERVO_CENTER_ANGLE 90

// VAD (Voice Activity Detection) settings
#define VAD_NOISE_ALPHA 0.995f
#define VAD_ON_MULTIPLIER 3.0f
#define VAD_OFF_MULTIPLIER 1.8f
#define VAD_MIN_TALK_MS 500
#define VAD_SILENCE_END_MS 350
#define VAD_MAX_TALK_MS 8000
#define VAD_INITIAL_NOISE_FLOOR 120.0f

// Audio settings
#define AUDIO_SAMPLE_RATE 16000
#define AUDIO_FRAME_SIZE 320
#define PREROLL_MS 200
#define AUDIO_RING_BUFFER_SIZE 81920
#define ENABLE_BUTTON_INTERRUPT 1

// Connection settings
#define WIFI_RECONNECT_INTERVAL_MS 5000
#define PING_INTERVAL_MS 3000

// LED colors (RGB)
#define LED_COLOR_CONNECTING_R 255
#define LED_COLOR_CONNECTING_G 0
#define LED_COLOR_CONNECTING_B 0

#define LED_COLOR_IDLE_R 0
#define LED_COLOR_IDLE_G 0
#define LED_COLOR_IDLE_B 255

#define LED_COLOR_RECORDING_R 0
#define LED_COLOR_RECORDING_G 255
#define LED_COLOR_RECORDING_B 0

#define LED_COLOR_PLAYING_R 255
#define LED_COLOR_PLAYING_G 255
#define LED_COLOR_PLAYING_B 0

// Protocol receive safety cap (bytes)
#define RX_AUDIO_MAX_ALLOC 16384

#endif  // CONFIG_H
