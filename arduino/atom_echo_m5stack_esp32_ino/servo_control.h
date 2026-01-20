#ifndef SERVO_CONTROL_H
#define SERVO_CONTROL_H

#include <ESP32Servo.h>

void servo_init(int pin);
void servo_set_angle(int angle);
void servo_rotate();
void servo_stop();
void servo_wiggle();

#endif
