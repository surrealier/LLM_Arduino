// ============================================================
// audio_buffer.cpp — 프리롤 오디오 버퍼 구현
// ============================================================
// 역할: 순환 버퍼로 최근 PREROLL_MS(200ms) 분량의 오디오를 유지.
//       VAD_START 시 시간순으로 서버에 전송.
//
// 순환 버퍼 동작:
//   push: buf[pos++] = sample, pos가 끝에 도달하면 0으로 wrap
//   send: full이면 pos~끝 + 0~pos 순서로 전송 (시간순 보장)
//         full이 아니면 0~pos만 전송
// ============================================================

#include "audio_buffer.h"
#include "protocol.h"

// preroll_init — 버퍼를 빈 상태로 초기화
void preroll_init(PrerollBuffer* pr) {
  pr->pos = 0;
  pr->full = false;
}

// preroll_push — n개 샘플을 순환 버퍼에 추가
// 버퍼가 가득 차면 가장 오래된 데이터부터 덮어씀
void preroll_push(PrerollBuffer* pr, const int16_t* x, size_t n) {
  for (size_t i = 0; i < n; i++) {
    pr->buf[pr->pos++] = x[i];
    if (pr->pos >= PREROLL_SAMPLES) {
      pr->pos = 0;
      pr->full = true;  // 최소 한 바퀴 돌았음을 표시
    }
  }
}

// preroll_send — 버퍼 내용을 시간순으로 서버에 전송
// 순환 버퍼이므로 full일 때는 두 번에 나눠 전송:
//   1) pos ~ PREROLL_SAMPLES-1 (오래된 부분)
//   2) 0 ~ pos-1 (최신 부분)
void preroll_send(PrerollBuffer* pr, WiFiClient& client) {
  size_t count = pr->full ? PREROLL_SAMPLES : pr->pos;
  if (count == 0) return;

  // 아직 한 바퀴 안 돌았으면 0~pos만 전송
  if (!pr->full) {
    protocol_send_packet(client, PTYPE_AUDIO, (uint8_t*)pr->buf, (uint16_t)(count * sizeof(int16_t)));
    return;
  }

  // 순환 버퍼: 오래된 부분(pos~끝) 먼저 전송
  size_t tail = PREROLL_SAMPLES - pr->pos;
  if (!protocol_send_packet(client, PTYPE_AUDIO, (uint8_t*)(pr->buf + pr->pos),
                            (uint16_t)(tail * sizeof(int16_t)))) {
    return;
  }
  // 최신 부분(0~pos) 전송
  if (pr->pos > 0) {
    protocol_send_packet(client, PTYPE_AUDIO, (uint8_t*)pr->buf, (uint16_t)(pr->pos * sizeof(int16_t)));
  }
}
