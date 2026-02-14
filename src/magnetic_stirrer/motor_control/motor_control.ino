#include <PID_v1.h>

// =========================
// RUN TIME SET UP
// =========================
unsigned long RUN_TIME_MS = 0;
unsigned long runStartMillis = 0;
bool timedRunActive = false;
// =========================
// PIN SETUP
// =========================
const int pin_hall  = 2;    // digital hall sensor
const int pin_motor = 9;    // PWM output

// =========================
// CONTROL TIMING
// =========================
const unsigned long CTRL_PERIOD_MS = 250;   // PI + RPM update
unsigned long lastCtrlMillis = 0;

// =========================
// RPM MEASUREMENT
// =========================
volatile unsigned long pulseCount = 0;
const int PULSES_PER_REV = 1;

// =========================
// FILTERING
// =========================
double rawRPM = 0.0;
double rpmFiltered = 0.0;
const double alpha = 0.05;

// =========================
// CONTROL VARIABLES
// =========================
double Setpoint = 3000.0;
double Input    = 0.0;
double PIout    = 0.0;

// Feedforward
const double kFF = 0.0092;   // PWM per RPM

// PI gains 
double Kp = 0.02;
double Ki = 0.0015;
double Kd = 0.0;

// Limits
const double MAX_PI_STEP = 1.0;   // PWM per cycle
const double SOFT_BAND   = 150.0; // RPM

PID speedPI(&Input, &PIout, &Setpoint, Kp, Ki, Kd, DIRECT);

// =========================
// STATE
// =========================
bool motorEnabled = true;

// =========================
// ISR
// =========================
void hallISR() {
  pulseCount++;
}

// =========================
// SETUP
// =========================
void setup() {
  pinMode(pin_hall, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(pin_hall), hallISR, FALLING);

  pinMode(pin_motor, OUTPUT);
  analogWrite(pin_motor, 0);

  speedPI.SetSampleTime(CTRL_PERIOD_MS);
  speedPI.SetOutputLimits(-50, 50);  // PI is correction only
  speedPI.SetMode(AUTOMATIC);

  Serial.begin(9600);
}

// =========================
// LOOP
// =========================
void loop() {
  handleSerialUI();
  // =========================
  // TIMED AUTO-STOP
  // =========================
  if (timedRunActive && RUN_TIME_MS > 0 &&
    millis() - runStartMillis >= RUN_TIME_MS) {

    motorEnabled = false;
    timedRunActive = false;
    analogWrite(pin_motor, 0);
  }


  unsigned long now = millis();
  if (now - lastCtrlMillis < CTRL_PERIOD_MS) return;
  lastCtrlMillis = now;

  // -------------------------
  // RPM CALCULATION
  // -------------------------
  unsigned long pulses;
  noInterrupts();
  pulses = pulseCount;
  pulseCount = 0;
  interrupts();

  rawRPM = (pulses * 60000.0) / (CTRL_PERIOD_MS * PULSES_PER_REV);
  rpmFiltered = alpha * rawRPM + (1.0 - alpha) * rpmFiltered;
  // =========================
// SEND TIME LEFT
// =========================
  static unsigned long lastTimeMsg = 0;
  if (motorEnabled && millis() - lastTimeMsg > 500) { // 2 Hz update
    lastTimeMsg = millis();

    if (RUN_TIME_MS == 0) {
      Serial.println("TIME_LEFT,INF");
    } else {
      long remaining = (long)(RUN_TIME_MS - (millis() - runStartMillis));
      if (remaining < 0) remaining = 0;
      Serial.print("TIME_LEFT,");
      Serial.println(remaining);
    }
  }

  // -------------------------
  // MOTOR OFF
  // -------------------------
  if (!motorEnabled) {
    analogWrite(pin_motor, 0);
    return;
  }

  // -------------------------
  // ERROR
  // -------------------------
  double error = Setpoint - rpmFiltered;

  // -------------------------
  // FEEDFORWARD
  // -------------------------
  double pwmFF = kFF * Setpoint;

  // -------------------------
  // PI CONTROL WITH HOLD
  // -------------------------
  if (abs(error) < 80.0) {
    // HOLD MODE: disable PI completely
    speedPI.SetMode(MANUAL);
    PIout = 0;
  } else {
    speedPI.SetMode(AUTOMATIC);
    Input = rpmFiltered;
    speedPI.Compute();   // writes into PIout
  }


  // -------------------------
  // SLEW LIMIT (PI ONLY)
  // -------------------------
  static double lastPI = 0;
  if (PIout > lastPI + MAX_PI_STEP) PIout = lastPI + MAX_PI_STEP;
  if (PIout < lastPI - MAX_PI_STEP) PIout = lastPI - MAX_PI_STEP;
  lastPI = PIout;

  // -------------------------
  // APPLY PWM
  // -------------------------
  double pwmCmd = pwmFF + PIout;
  pwmCmd = constrain(pwmCmd, 0, 255);
  analogWrite(pin_motor, (int)pwmCmd);

  // -------------------------
  // DEBUG
  // -------------------------
  Serial.print(Setpoint);
  Serial.print(",");
  Serial.print(rpmFiltered);
  Serial.print(",");
  Serial.println(pwmCmd);
  Serial.println("b");
}


// =========================
// SERIAL UI
// =========================
void handleSerialUI() {
  if (!Serial.available()) return;

  String cmd = Serial.readStringUntil('\n');
  cmd.trim();

  if (cmd.startsWith("S ")) {
    Setpoint = constrain(cmd.substring(2).toFloat(), 0, 12000);
  }

  else if (cmd.startsWith("KP ")) {
    Kp = cmd.substring(3).toFloat();
    speedPI.SetTunings(Kp, Ki, 0);
  }

  else if (cmd.startsWith("KI ")) {
    Ki = cmd.substring(3).toFloat();
    speedPI.SetTunings(Kp, Ki, 0);
  }

  else if (cmd == "START") {
  motorEnabled = true;
  timedRunActive = true;
  runStartMillis = millis();
}

  else if (cmd == "STOP") {
    motorEnabled = false;
    timedRunActive = false;
    analogWrite(pin_motor, 0);
}
  else if (cmd.startsWith("T ")) {
  double seconds = cmd.substring(2).toFloat();
  if (seconds <= 0) {
    RUN_TIME_MS = 0;  // infinite
  } else {
    RUN_TIME_MS = (unsigned long)(seconds * 1000.0);
  }
}
}
