#ifndef SERVO_CONTROL_H
#define SERVO_CONTROL_H

#include <ESP32Servo.h>

enum ServoStateType {
  SERVO_IDLE,
  SERVO_ROTATING,
  SERVO_WIGGLING
};

struct ServoState {
  ServoStateType state;
  unsigned long start_time;
  unsigned long next_step_time;
  int step;
  int target_angle;
};

void servo_init(int pin);
void servo_set_angle(int angle);
void servo_rotate();
void servo_stop();
void servo_wiggle();
void servo_update();

#endif