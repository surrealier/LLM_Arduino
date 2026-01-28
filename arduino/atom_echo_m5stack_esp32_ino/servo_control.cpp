#include "servo_control.h"

static Servo s_servo;
static ServoState servo_state = {SERVO_IDLE, 0, 0, 0, 0};

void servo_init(int pin) {
  s_servo.attach(pin);
  s_servo.write(90);
}

void servo_set_angle(int angle) {
  s_servo.write(angle);
}

void servo_rotate() {
  servo_state.state = SERVO_ROTATING;
  servo_state.start_time = millis();
  servo_state.step = 0;
  servo_state.next_step_time = millis();
}

void servo_stop() {
  s_servo.detach();
  servo_state.state = SERVO_IDLE;
}

void servo_wiggle() {
  servo_state.state = SERVO_WIGGLING;
  servo_state.start_time = millis();
  servo_state.step = 0;
  servo_state.next_step_time = millis();
}

void servo_update() {
  unsigned long now = millis();
  
  switch (servo_state.state) {
    case SERVO_ROTATING:
      if (now >= servo_state.next_step_time) {
        if (servo_state.step % 2 == 0) {
          s_servo.write(180);
        } else {
          s_servo.write(0);
        }
        servo_state.step++;
        servo_state.next_step_time = now + 250;
        
        if (now - servo_state.start_time >= 3000) {
          servo_stop();
        }
      }
      break;
      
    case SERVO_WIGGLING:
      if (now >= servo_state.next_step_time) {
        switch (servo_state.step) {
          case 0:
            s_servo.write(60);
            servo_state.next_step_time = now + 150;
            break;
          case 1:
            s_servo.write(120);
            servo_state.next_step_time = now + 150;
            break;
          case 2:
            s_servo.write(90);
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