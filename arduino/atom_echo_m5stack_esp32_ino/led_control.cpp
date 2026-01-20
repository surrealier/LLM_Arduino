#include "led_control.h"
#include <string.h>

void led_set_color(uint8_t r, uint8_t g, uint8_t b) {
  M5.dis.fillpix(M5.dis.color565(r, g, b));
}

void led_show_emotion(const char* emotion) {
  if (!emotion) {
    led_set_color(100, 255, 100);
    return;
  }

  if (strcmp(emotion, "happy") == 0) {
    led_set_color(255, 200, 0);
  } else if (strcmp(emotion, "sad") == 0) {
    led_set_color(0, 100, 255);
  } else if (strcmp(emotion, "excited") == 0) {
    led_set_color(255, 50, 200);
  } else if (strcmp(emotion, "sleepy") == 0) {
    led_set_color(100, 100, 150);
  } else if (strcmp(emotion, "angry") == 0) {
    led_set_color(255, 0, 0);
  } else {
    led_set_color(100, 255, 100);
  }
}

void led_update_pattern() {
  // Placeholder for animated patterns
}
