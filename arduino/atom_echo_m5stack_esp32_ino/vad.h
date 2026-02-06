// ============================================================
// vad.h — Voice Activity Detection 인터페이스
// ============================================================
// 역할: 오디오 프레임의 RMS 값을 기반으로 음성 시작/진행/종료를 감지.
//       에너지 기반 VAD로, 적응형 노이즈 플로어를 사용.
//
// 이벤트 흐름:
//   침묵 → (RMS > threshold × 2프레임 연속) → VAD_START
//   발화 중 → VAD_CONTINUE
//   (침묵 지속 OR 타임아웃) → VAD_END
// ============================================================

#ifndef VAD_H
#define VAD_H

#include <stdint.h>

// VAD 이벤트 타입
enum VadEvent {
  VAD_NONE,      // 변화 없음 (침묵 지속)
  VAD_START,     // 발화 시작 감지
  VAD_CONTINUE,  // 발화 진행 중
  VAD_END        // 발화 종료 (침묵 or 타임아웃)
};

// VAD 내부 상태
struct VadState {
  float noise_floor;        // 적응형 노이즈 플로어 (지수이동평균)
  uint32_t talk_samples;    // 현재 발화의 누적 샘플 수
  uint32_t silence_samples; // 현재 침묵 구간의 누적 샘플 수
  uint8_t start_hit;        // 연속 음성 프레임 카운터 (2회 연속 시 START)
  bool talking;             // 현재 발화 중 여부
};

// 상태 초기화 (부팅 시 또는 TTS 재생 후 리셋)
void vad_init(VadState* state);

// 프레임 단위 업데이트: RMS 값으로 이벤트 판정
VadEvent vad_update(VadState* state, float rms, uint32_t frame_samples, uint32_t sr);

#endif
