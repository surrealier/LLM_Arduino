#include "audio_buffer.h"
#include "protocol.h"

void preroll_init(PrerollBuffer* pr) {
  pr->pos = 0;
  pr->full = false;
}

void preroll_push(PrerollBuffer* pr, const int16_t* x, size_t n) {
  for (size_t i = 0; i < n; i++) {
    pr->buf[pr->pos++] = x[i];
    if (pr->pos >= PREROLL_SAMPLES) {
      pr->pos = 0;
      pr->full = true;
    }
  }
}

void preroll_send(PrerollBuffer* pr, WiFiClient& client) {
  size_t count = pr->full ? PREROLL_SAMPLES : pr->pos;
  if (count == 0) return;

  if (!pr->full) {
    protocol_send_packet(client, PTYPE_AUDIO, (uint8_t*)pr->buf, (uint16_t)(count * sizeof(int16_t)));
    return;
  }

  size_t tail = PREROLL_SAMPLES - pr->pos;
  if (!protocol_send_packet(client, PTYPE_AUDIO, (uint8_t*)(pr->buf + pr->pos),
                            (uint16_t)(tail * sizeof(int16_t)))) {
    return;
  }
  if (pr->pos > 0) {
    protocol_send_packet(client, PTYPE_AUDIO, (uint8_t*)pr->buf, (uint16_t)(pr->pos * sizeof(int16_t)));
  }
}
