#include <PID_v1.h>
//PIN intit
const int pin_hall = 2; 
int pin_motor = 9;
int pin_pot   = A0;

//RPM init
const unsigned long RPMcalcTime = 200;  // ms
unsigned long RPMmesureMillis = 0;
volatile unsigned int revolution = 0;
bool hallHigh = false;

float rawRPM = 0.0;
double rpmFiltered = 0.0;
const double alpha = 0.25;

//PI variables 
double Setpoint = 5000.0;   // target RPM
double Input    = 0.0;      // filtered RPM
double Output   = 0.0;      // PWM 0–255
const double RPM_DEADBAND = 30.0;   // ±30 RPM
bool piFrozen = false;


// PI gains (start conservative)
double Kp = 0.05;
double Ki = 0.003;
double Kd = 0.0;            // OFF

PID speedPI(&Input, &Output, &Setpoint, Kp, Ki, Kd, DIRECT);

//UI
bool motorEnabled = true;

void setup() {

  pinMode(pin_hall, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(pin_hall), hallISR, FALLING);

  
  pinMode(pin_motor, OUTPUT);
  analogWrite(pin_motor, 0);

  speedPI.SetMode(AUTOMATIC);
  speedPI.SetSampleTime(RPMcalcTime);
  speedPI.SetOutputLimits(0, 255);

  Serial.begin(9600);
}

void loop() {
  handleSerialUI();

  unsigned long now = millis();

  const double RPM_DEADBAND = 30.0;

if (now - RPMmesureMillis >= RPMcalcTime) {
  rpmCalc(now);

  double error = Setpoint - rpmFiltered;
  if (!motorEnabled) {
      analogWrite(pin_motor, 0);   // ensure motor is off
      return;                      // skip PI + PWM only
    }
  if (abs(error) <= RPM_DEADBAND) {
    // --- Inside deadband: freeze PI ---
    if (!piFrozen) {
      speedPI.SetMode(MANUAL);
      piFrozen = true;
    }
  } else {
    // --- Outside deadband: normal PI ---
    if (piFrozen) {
      speedPI.SetMode(AUTOMATIC);
      piFrozen = false;
    }

    Input = rpmFiltered;
    speedPI.Compute();
  }

  analogWrite(pin_motor, (int)Output);

  Serial.print(Setpoint);
  Serial.print(",");
  Serial.print(rpmFiltered);
  Serial.print(",");
  Serial.println(Output);
}

}

void hallISR() {
  revolution++;
}

void rpmCalc(unsigned long now) {
  unsigned long dt = now - RPMmesureMillis;

  unsigned int rev;
  noInterrupts();
  rev = revolution;
  revolution = 0;
  interrupts();

  if (dt > 0 && rev > 0) {
    rawRPM = (rev * 60000.0) / dt;
  } else {
    rawRPM = 0;
  }

  rpmFiltered = alpha * rawRPM + (1.0 - alpha) * rpmFiltered;
  RPMmesureMillis = now;
}

// SERIAL UI
void handleSerialUI() {
  if (!Serial.available()) return;

  String cmd = Serial.readStringUntil('\n');
  cmd.trim();

  if (cmd.startsWith("S ")) {
    double rpm = cmd.substring(2).toFloat();
    Setpoint = constrain(rpm, 0, 12000);
    Serial.print("Setpoint set to ");
    Serial.println(Setpoint);
  }

  else if (cmd.startsWith("KP ")) {
    Kp = cmd.substring(2).toFloat();

    speedPI.SetMode(MANUAL);
    speedPI.SetTunings(Kp, Ki, 0.0);
    speedPI.SetMode(AUTOMATIC);

    Serial.print("Kp = ");
    Serial.println(Kp);

  }

  else if (cmd.startsWith("KI ")) {
    Kp = cmd.substring(2).toFloat();

    speedPI.SetMode(MANUAL);
    speedPI.SetTunings(Kp, Ki, 0.0);
    speedPI.SetMode(AUTOMATIC);

    Serial.print("Kp = ");
    Serial.println(Kp);

  }

  else if (cmd == "STOP") {
    motorEnabled = false;
    speedPI.SetMode(MANUAL);
    analogWrite(pin_motor, 0);
    Serial.println("Motor stopped");
  }

  else if (cmd == "START") {
    motorEnabled = true;                    // start near steady-state
    speedPI.SetMode(AUTOMATIC);
    analogWrite(pin_motor, Output);
}

  else if (cmd == "STATUS") {
    Serial.println("----- STATUS -----");
    Serial.print("Target RPM: "); Serial.println(Setpoint);
    Serial.print("RPM: "); Serial.println(rpmFiltered);
    Serial.print("PWM: "); Serial.println(Output);
    Serial.print("Kp: "); Serial.println(Kp);
    Serial.print("Ki: "); Serial.println(Ki);
    Serial.println("------------------");
  }

  else {
    Serial.println("Unknown command");
  }
}

