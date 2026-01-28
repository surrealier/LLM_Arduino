#ifndef LED_CONTROL_H
#define LED_CONTROL_H

#include <M5Unified.h>
#include <FastLED.h>
#include <stdint.h>

#define LED_PIN 27
#define NUM_LEDS 1

extern CRGB leds[NUM_LEDS];

void led_init();
void led_set_color(uint8_t r, uint8_t g, uint8_t b);
void led_show_emotion(const char* emotion);
void led_update_pattern();

#endif
