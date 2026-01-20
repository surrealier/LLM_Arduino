#ifndef LED_CONTROL_H
#define LED_CONTROL_H

#include <M5Unified.h>
#include <stdint.h>

void led_set_color(uint8_t r, uint8_t g, uint8_t b);
void led_show_emotion(const char* emotion);
void led_update_pattern();

#endif
