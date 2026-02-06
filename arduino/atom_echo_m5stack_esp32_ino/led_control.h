// ============================================================
// led_control.h — LED 제어 인터페이스
// ============================================================
// 역할: Atom Echo의 SK6812 RGB LED (GPIO 27) 제어.
//       시스템 상태 표시 및 감정 표현.
//
// 구현: M5Unified 내장 API 사용 (FastLED 라이브러리 미사용).
//       M5Unified가 Atom Echo의 LED를 자동으로 인식하여 관리.
// ============================================================

#ifndef LED_CONTROL_H
#define LED_CONTROL_H

#include <M5Unified.h>
#include <stdint.h>

// LED 초기화 (M5.begin()에서 자동 처리되므로 현재 no-op)
void led_init();

// RGB 색상 설정 (0-255 각 채널)
void led_set_color(uint8_t r, uint8_t g, uint8_t b);

// 감정 문자열에 따른 LED 색상 설정
// 지원: "happy", "sad", "excited", "sleepy", "angry", 기타(neutral)
void led_show_emotion(const char* emotion);

// 애니메이션 패턴 업데이트 (매 loop()에서 호출, 현재 placeholder)
void led_update_pattern();

#endif
