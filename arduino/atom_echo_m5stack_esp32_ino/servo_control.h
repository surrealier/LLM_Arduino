// ============================================================
// servo_control.h — 서보 모터 제어 인터페이스
// ============================================================
// 역할: GPIO 25에 연결된 서보 모터의 각도 제어 및 동작 패턴.
//       ESP32Servo 라이브러리 사용 (LEDC PWM 채널 기반).
//
// 동작 모드:
//   IDLE     — 정지 상태 (마지막 각도 유지)
//   ROTATING — 0°↔180° 왕복 회전 (3초간)
//   WIGGLING — 60°→120°→90° 빠른 흔들기
//
// 안전 기능:
//   - 모든 각도는 0-180° 범위로 클램핑
//   - stop() 시 detach 하지 않음 (재사용 보장)
//   - ensure_attached()로 자동 재연결
// ============================================================

#ifndef SERVO_CONTROL_H
#define SERVO_CONTROL_H

#include <ESP32Servo.h>

// 서보 동작 상태 타입
enum ServoStateType {
  SERVO_IDLE,       // 정지 (각도 유지)
  SERVO_ROTATING,   // 좌우 왕복 회전
  SERVO_WIGGLING    // 빠른 흔들기 (감정 표현)
};

// 서보 비동기 동작 상태
struct ServoState {
  ServoStateType state;          // 현재 동작 모드
  unsigned long start_time;      // 동작 시작 시각 (millis)
  unsigned long next_step_time;  // 다음 스텝 실행 시각
  int step;                      // 현재 스텝 번호
  int target_angle;              // 목표 각도 (예약)
};

void servo_init(int pin);        // 초기화: PWM 50Hz, 중앙 위치
void servo_set_angle(int angle); // 각도 설정 (0-180 클램핑)
void servo_rotate();             // 왕복 회전 시작
void servo_stop();               // 정지 (중앙 위치로 복귀)
void servo_wiggle();             // 흔들기 시작
void servo_update();             // 매 loop()에서 호출: 비동기 스텝 처리

#endif
