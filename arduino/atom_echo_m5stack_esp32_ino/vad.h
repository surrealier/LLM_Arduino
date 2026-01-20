#ifndef VAD_H
#define VAD_H

#include <stdint.h>

enum VadEvent { VAD_NONE, VAD_START, VAD_CONTINUE, VAD_END };

struct VadState {
  float noise_floor;
  uint32_t talk_samples;
  uint32_t silence_samples;
  uint8_t start_hit;
  bool talking;
};

void vad_init(VadState* state);
VadEvent vad_update(VadState* state, float rms, uint32_t frame_samples, uint32_t sr);

#endif
