
#include <SoftwareSerial.h>

SoftwareSerial bluetooth(4, 5);

const int buttonA = 2;
const int buttonB = 3;

const int RED = 9;
const int GREEN = 10;
const int BLUE = 11;

const bool COMMON_ANODE = false;

int lastA = HIGH;
int lastB = HIGH;
int stableA = HIGH;
int stableB = HIGH;

unsigned long timeA = 0;
unsigned long timeB = 0;

void setColor(int r, int g, int b) {
  analogWrite(RED, COMMON_ANODE ? 255-r : r);
  analogWrite(GREEN, COMMON_ANODE ? 255-g : g);
  analogWrite(BLUE, COMMON_ANODE ? 255-b : b);
}

void checkButton(int pin, int &last,
                 int &stable, unsigned long &t,
                 const char* name) {
  int reading = digitalRead(pin);

  if (reading != last) {
    t = millis();
  }

  if (millis() - t >= 30 && reading != stable) {
    stable = reading;

    if (stable == LOW) {
      Serial.println(name);
    }
  }

  last = reading;
}

void setup() {
  Serial.begin(9600);
  bluetooth.begin(9600);

  pinMode(buttonA, INPUT_PULLUP);
  pinMode(buttonB, INPUT_PULLUP);

  pinMode(RED, OUTPUT);
  pinMode(GREEN, OUTPUT);
  pinMode(BLUE, OUTPUT);

  setColor(255, 0, 0);
  Serial.println("PET DOCK READY");
}

void loop() {
  checkButton(buttonA, lastA, stableA,
              timeA, "BTN_A");

  checkButton(buttonB, lastB, stableB,
              timeB, "BTN_B");

  if (bluetooth.available()) {
    char cmd = bluetooth.read();

    if (cmd == 'R') setColor(255, 0, 0);
    if (cmd == 'G') setColor(0, 255, 0);
    if (cmd == 'B') setColor(0, 0, 255);
    if (cmd == 'X') setColor(0, 0, 0);
  }
}
