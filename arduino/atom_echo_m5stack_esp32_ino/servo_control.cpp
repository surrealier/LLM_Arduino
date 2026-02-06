// ============================================================
// servo_control.cpp — 서보 모터 제어 구현
// ============================================================
// 역할: ESP32Servo 라이브러리로 PWM 서보 제어.
//       비동기 동작 패턴 (회전, 위글)을 servo_update()에서 처리.
//
// 주요 설계 결정:
//   - setPeriodHertz(50): 표준 서보 PWM 주파수
//   - attach(pin, 500, 2400): 펄스 범위 (μs) 명시
//   - clamp_angle(): 모든 각도를 SERVO_MIN~MAX 범위로 제한
//   - ensure_attached(): stop() 후에도 자동 재연결
//   - stop()에서 detach() 하지 않음 → 재사용 보장
// ============================================================

#include "servo_control.h"
#include "config.h"

// ── 내부 상태 ──
static Servo s_servo;                                       // ESP32Servo 인스턴스
static ServoState servo_state = {SERVO_IDLE, 0, 0, 0, 0};  // 비동기 동작 상태
static int s_pin = -1;                                      // 연결된 GPIO 핀 번호
static bool s_attached = false;                              // PWM 채널 연결 여부

// ensure_attached — 서보가 분리되었으면 자동으로 재연결
// stop() 등에서 detach된 경우에도 안전하게 동작 보장
static void ensure_attached() {
  if (!s_attached && s_pin >= 0) {
    s_servo.setPeriodHertz(50);          // 서보 표준 50Hz PWM
    s_servo.attach(s_pin, 500, 2400);    // 펄스 범위: 500~2400μs
    s_attached = true;
  }
}

// clamp_angle — 각도를 안전 범위(0-180)로 제한
// 범위 초과 시 서보 하드웨어 손상 방지
static int clamp_angle(int angle) {
  if (angle < SERVO_MIN_ANGLE) return SERVO_MIN_ANGLE;
  if (angle > SERVO_MAX_ANGLE) return SERVO_MAX_ANGLE;
  return angle;
}

// servo_init — 서보 초기화: PWM 설정 + 중앙 위치로 이동
void servo_init(int pin) {
  s_pin = pin;
  s_servo.setPeriodHertz(50);
  s_servo.attach(pin, 500, 2400);
  s_attached = true;
  s_servo.write(SERVO_CENTER_ANGLE);  // 90° (중앙)
}

// servo_set_angle — 지정 각도로 즉시 이동 (0-180 클램핑)
void servo_set_angle(int angle) {
  ensure_attached();
  s_servo.write(clamp_angle(angle));
}

// servo_rotate — 좌우 왕복 회전 시작 (3초간, 250ms 간격)
void servo_rotate() {
  ensure_attached();
  servo_state.state = SERVO_ROTATING;
  servo_state.start_time = millis();
  servo_state.step = 0;
  servo_state.next_step_time = millis();
}

// servo_stop — 동작 중단 + 중앙 위치 복귀
// detach() 하지 않으므로 이후 set_angle() 즉시 사용 가능
void servo_stop() {
  ensure_attached();
  s_servo.write(SERVO_CENTER_ANGLE);
  servo_state.state = SERVO_IDLE;
}

// servo_wiggle — 빠른 흔들기 시작 (60°→120°→90°, 감정 표현용)
void servo_wiggle() {
  ensure_attached();
  servo_state.state = SERVO_WIGGLING;
  servo_state.start_time = millis();
  servo_state.step = 0;
  servo_state.next_step_time = millis();
}

// servo_update — 매 loop()에서 호출: 비동기 동작 스텝 처리
// ROTATING: 250ms마다 0°↔180° 전환, 3초 후 자동 정지
// WIGGLING: 60°(150ms) → 120°(150ms) → 90°(완료)
void servo_update() {
  unsigned long now = millis();

  switch (servo_state.state) {
    case SERVO_ROTATING:
      if (now >= servo_state.next_step_time) {
        ensure_attached();
        // 짝수 스텝: MAX, 홀수 스텝: MIN
        s_servo.write((servo_state.step % 2 == 0) ? SERVO_MAX_ANGLE : SERVO_MIN_ANGLE);
        servo_state.step++;
        servo_state.next_step_time = now + 250;
        // 3초 경과 시 자동 정지
        if (now - servo_state.start_time >= 3000) {
          servo_stop();
        }
      }
      break;

    case SERVO_WIGGLING:
      if (now >= servo_state.next_step_time) {
        ensure_attached();
        switch (servo_state.step) {
          case 0:  // 왼쪽으로
            s_servo.write(clamp_angle(60));
            servo_state.next_step_time = now + 150;
            break;
          case 1:  // 오른쪽으로
            s_servo.write(clamp_angle(120));
            servo_state.next_step_time = now + 150;
            break;
          case 2:  // 중앙 복귀 + 완료
            s_servo.write(SERVO_CENTER_ANGLE);
            servo_state.state = SERVO_IDLE;
            break;
        }
        servo_state.step++;
      }
      break;

    case SERVO_IDLE:
    default:
      break;
  }
}
