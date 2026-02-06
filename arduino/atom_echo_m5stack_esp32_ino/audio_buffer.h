// ============================================================
// audio_buffer.h — 프리롤 오디오 버퍼 인터페이스
// ============================================================
// 역할: VAD가 음성 시작을 감지하기 전의 오디오를 순환 버퍼에 보관.
//       VAD_START 이벤트 발생 시 이 버퍼의 내용을 먼저 서버에 전송하여
//       발화의 첫 부분(약 200ms)이 잘리지 않도록 보존.
//
// 구조: 고정 크기 순환 버퍼 (PREROLL_SAMPLES = SR × PREROLL_MS / 1000)
//       16kHz × 200ms = 3200샘플 = 6400바이트
// ============================================================

#ifndef AUDIO_BUFFER_H
#define AUDIO_BUFFER_H

#include <stdint.h>
#include <stddef.h>
#include <WiFi.h>
#include "config.h"

// 프리롤 버퍼 크기 (샘플 수) — 컴파일 타임 계산
static constexpr size_t PREROLL_SAMPLES = (AUDIO_SAMPLE_RATE * PREROLL_MS) / 1000;
static_assert(PREROLL_SAMPLES > 0, "PREROLL_SAMPLES must be > 0");

// 프리롤 순환 버퍼 구조체
struct PrerollBuffer {
  int16_t buf[PREROLL_SAMPLES];  // PCM16 샘플 저장소
  size_t pos;                     // 현재 쓰기 위치 (순환)
  bool full;                      // 버퍼가 한 바퀴 이상 돌았는지
};

// 버퍼 초기화 (pos=0, full=false)
void preroll_init(PrerollBuffer* pr);

// 프레임을 순환 버퍼에 추가 (오래된 데이터는 자동 덮어쓰기)
void preroll_push(PrerollBuffer* pr, const int16_t* x, size_t n);

// 버퍼 내용을 시간순으로 서버에 AUDIO 패킷으로 전송
void preroll_send(PrerollBuffer* pr, WiFiClient& client);

#endif
