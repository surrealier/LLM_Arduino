#ifndef AUDIO_BUFFER_H
#define AUDIO_BUFFER_H

#include <stdint.h>
#include <stddef.h>
#include <WiFi.h>
#include "config.h"

static constexpr size_t PREROLL_SAMPLES = (AUDIO_SAMPLE_RATE * PREROLL_MS) / 1000;

struct PrerollBuffer {
  int16_t buf[PREROLL_SAMPLES];
  size_t pos;
  bool full;
};

void preroll_init(PrerollBuffer* pr);
void preroll_push(PrerollBuffer* pr, const int16_t* x, size_t n);
void preroll_send(PrerollBuffer* pr, WiFiClient& client);

#endif
