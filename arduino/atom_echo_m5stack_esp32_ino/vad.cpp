#include "vad.h"
#include "config.h"

void vad_init(VadState* state) {
  state->noise_floor = VAD_INITIAL_NOISE_FLOOR;
  state->talk_samples = 0;
  state->silence_samples = 0;
  state->start_hit = 0;
  state->talking = false;
}

VadEvent vad_update(VadState* state, float rms, uint32_t frame_samples, uint32_t sr) {
  if (!state->talking) {
    state->noise_floor = VAD_NOISE_ALPHA * state->noise_floor + (1.0f - VAD_NOISE_ALPHA) * rms;
  }

  float thr_on = state->noise_floor * VAD_ON_MULTIPLIER;
  float thr_off = state->noise_floor * VAD_OFF_MULTIPLIER;
  bool voice = (rms > thr_on);

  if (!state->talking) {
    if (voice) {
      state->start_hit++;
      if (state->start_hit >= 2) {
        state->talking = true;
        state->talk_samples = 0;
        state->silence_samples = 0;
        return VAD_START;
      }
    } else {
      state->start_hit = 0;
    }
    return VAD_NONE;
  }

  state->talk_samples += frame_samples;
  if (rms > thr_off) {
    state->silence_samples = 0;
  } else {
    state->silence_samples += frame_samples;
  }

  uint32_t talk_ms = (state->talk_samples * 1000) / sr;
  uint32_t silence_ms = (state->silence_samples * 1000) / sr;

  bool end_silence = (talk_ms >= VAD_MIN_TALK_MS && silence_ms >= VAD_SILENCE_END_MS);
  bool end_timeout = (talk_ms >= VAD_MAX_TALK_MS);

  if (end_silence || end_timeout) {
    state->talking = false;
    state->start_hit = 0;
    return VAD_END;
  }

  return VAD_CONTINUE;
}
