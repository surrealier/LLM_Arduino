// ============================================================
// vad.cpp — Voice Activity Detection 구현
// ============================================================
// 역할: 에너지 기반 VAD. 적응형 노이즈 플로어 대비 RMS 비율로
//       음성 여부를 판정.
//
// 알고리즘:
//   1) 침묵 시: noise_floor = α × noise_floor + (1-α) × rms
//   2) 음성 시작: rms > noise_floor × ON_MUL 이 2프레임 연속
//   3) 음성 종료: (MIN_TALK 이상 + SILENCE_END 이상 침묵) OR MAX_TALK 초과
//
// 컴파일 타임 검증: static_assert로 설정값 범위 보장
// ============================================================

#include "vad.h"
#include "config.h"

// ── 설정값 유효성 검증 (컴파일 타임) ──
static_assert(VAD_MIN_TALK_MS < VAD_MAX_TALK_MS, "VAD_MIN_TALK_MS must be < VAD_MAX_TALK_MS");
static_assert(VAD_ON_MULTIPLIER > 0, "VAD_ON_MULTIPLIER must be > 0");
static_assert(VAD_OFF_MULTIPLIER > 0, "VAD_OFF_MULTIPLIER must be > 0");

// vad_init — VAD 상태를 초기값으로 리셋
void vad_init(VadState* state) {
  state->noise_floor = VAD_INITIAL_NOISE_FLOOR;
  state->talk_samples = 0;
  state->silence_samples = 0;
  state->start_hit = 0;
  state->talking = false;
}

// vad_update — 1프레임(20ms)의 RMS로 VAD 이벤트 판정
// @param rms: 현재 프레임의 RMS 음량
// @param frame_samples: 프레임 내 샘플 수 (320)
// @param sr: 샘플레이트 (16000)
// @return: VAD_NONE / VAD_START / VAD_CONTINUE / VAD_END
VadEvent vad_update(VadState* state, float rms, uint32_t frame_samples, uint32_t sr) {
  // 방어: 0으로 나누기 방지
  if (sr == 0 || frame_samples == 0) return VAD_NONE;

  // ── 노이즈 플로어 적응 (발화 중이 아닐 때만) ──
  // 지수이동평균으로 환경 소음 레벨을 천천히 추적
  if (!state->talking) {
    state->noise_floor = VAD_NOISE_ALPHA * state->noise_floor + (1.0f - VAD_NOISE_ALPHA) * rms;
  }

  // ── 임계값 계산 ──
  float thr_on = state->noise_floor * VAD_ON_MULTIPLIER;   // 음성 시작 임계값
  float thr_off = state->noise_floor * VAD_OFF_MULTIPLIER;  // 침묵 판정 임계값
  bool voice = (rms > thr_on);

  // ── 침묵 상태에서의 처리 ──
  if (!state->talking) {
    if (voice) {
      state->start_hit++;
      // 2프레임 연속 음성 → 발화 시작 확정 (단발 소음 필터링)
      if (state->start_hit >= 2) {
        state->talking = true;
        state->talk_samples = 0;
        state->silence_samples = 0;
        return VAD_START;
      }
    } else {
      state->start_hit = 0;  // 연속성 깨짐 → 카운터 리셋
    }
    return VAD_NONE;
  }

  // ── 발화 중 처리 ──
  state->talk_samples += frame_samples;

  // 침묵 구간 추적 (thr_off 기준)
  if (rms > thr_off) {
    state->silence_samples = 0;       // 음성 감지 → 침묵 카운터 리셋
  } else {
    state->silence_samples += frame_samples;
  }

  // 시간 변환 (샘플 → ms)
  uint32_t talk_ms = (state->talk_samples * 1000) / sr;
  uint32_t silence_ms = (state->silence_samples * 1000) / sr;

  // ── 발화 종료 조건 ──
  // 조건1: 최소 발화 시간 충족 + 충분한 침묵
  bool end_silence = (talk_ms >= VAD_MIN_TALK_MS && silence_ms >= VAD_SILENCE_END_MS);
  // 조건2: 최대 발화 시간 초과 (강제 종료)
  bool end_timeout = (talk_ms >= VAD_MAX_TALK_MS);

  if (end_silence || end_timeout) {
    state->talking = false;
    state->start_hit = 0;
    return VAD_END;
  }

  return VAD_CONTINUE;
}
