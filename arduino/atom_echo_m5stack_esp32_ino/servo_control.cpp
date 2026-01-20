#include "servo_control.h"

static Servo s_servo;

void servo_init(int pin) {
  s_servo.attach(pin);
  s_servo.write(90);
}

void servo_set_angle(int angle) {
  s_servo.write(angle);
}

void servo_rotate() {
  unsigned long t0 = millis();
  while (millis() - t0 < 3000) {
    s_servo.write(180);
    delay(250);
    s_servo.write(0);
    delay(250);
  }
  s_servo.write(0);
}

void servo_stop() {
  s_servo.write(0);
}

void servo_wiggle() {
  s_servo.write(60);
  delay(150);
  s_servo.write(120);
  delay(150);
  s_servo.write(90);
}
