#include <MD_Parola.h>
#include <MD_MAX72xx.h>
#include <SPI.h>

#define HARDWARE_TYPE MD_MAX72XX::FC16_HW
#define MAX_DEVICES 4
#define CS_PIN 10
#define AVG_SIZE 5
int rpmHistory[AVG_SIZE] = {0};     // store last 5 readings
int avgIndex = 0;
bool bufferFilled = false;

MD_Parola matrix = MD_Parola(HARDWARE_TYPE, CS_PIN, MAX_DEVICES);

// PIN SETUP
int pin_motor = 9;
int pin_pot   = A0;
int pin_hall= A5;
int rpm = 0;
bool hallHigh = false;

char buffer[8];
int rpmMax = 15000; 

int getRollingAverage(int newValue) {
  rpmHistory[avgIndex] = newValue;
  avgIndex++;

  if (avgIndex >= AVG_SIZE) {
    avgIndex = 0;
    bufferFilled = true;
  }

  long sum = 0;
  int count = bufferFilled ? AVG_SIZE : avgIndex;

  for (int i = 0; i < count; i++) {
    sum += rpmHistory[i];
  }

  return sum / count;
}

void setup() {
  Serial.begin(9600);
  pinMode(pin_motor, OUTPUT);
  pinMode(pin_pot, INPUT);

  matrix.begin();
  matrix.setIntensity(5);
  matrix.displayClear();

  // ROTATE DISPLAY BY 180°
  matrix.setZoneEffect(0, true, PA_FLIP_UD);
  matrix.setZoneEffect(0, true, PA_FLIP_LR);
}

void loop() {

  // ---------- MOTOR CONTROL ----------
  int pot = analogRead(pin_pot);
  int speed = map(pot, 1023, 0, 0, 255);
  analogWrite(pin_motor, speed);
  
  // ---------- RPM MEASUREMENT (1 sec) ----------
  int revolution = 0;
  hallHigh = false;

  unsigned long startTime = millis();
  while (millis() - startTime < 1000) {

    int v = analogRead(pin_hall);

    if (v > 650 && !hallHigh) {
      revolution++;
      hallHigh = true;
    }
    if (v < 620 && hallHigh) {
      hallHigh = false;
    }
  }

int rawRPM = revolution * 60;

// If no pulse → RPM is zero
if (revolution == 0) {
  rawRPM = 0;
}

// Apply rolling average smoothing
rpm = getRollingAverage(rawRPM);
Serial.println(rpm);

  // ---------- DISPLAY RPM NUMBER ----------
  sprintf(buffer, "%d", rpm);

  matrix.displayText(buffer, PA_CENTER, 0, 0, PA_PRINT, PA_NO_EFFECT);
  matrix.displayReset();
  matrix.displayAnimate();

// ----------------------------------------------
//              GRAPHICS BAR (BOTTOM ROW)
// ----------------------------------------------
MD_MAX72XX *gfx = matrix.getGraphicObject();

// Clear bottom row -> but after rotation it's row 0
gfx->setRow(0, 0x00);

// Compute bar length 0–32
int barLength = map(rpm, 0, rpmMax, 0, 32);
barLength = constrain(barLength, 0, 32);

// Draw the bar LEFT → RIGHT on row 0 (actual bottom after rotation)
for (int col = 0; col < barLength; col++) {
  gfx->setPoint(0, col, true);
}
}
