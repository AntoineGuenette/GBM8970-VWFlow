#include <PID_v1.h>

// =========================
// RUN TIME SETUP
// =========================
unsigned long RUN_TIME_MS = 0;
unsigned long runStartMillis = 0;
bool timedRunActive = false;

// =========================
// PIN SETUP
// =========================
const int pin_hall  = 2;    // Digital hall sensor
const int pin_motor = 9;    // PWM output

// =========================
// CONTROL TIMING
// =========================
const unsigned long CTRL_PERIOD_MS = 250;   // PI & RPM update period
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
const double MAX_PI_STEP = 1.0;

// PID Controller
PID speedPI(&Input, &PIout, &Setpoint, Kp, Ki, Kd, DIRECT);

// =========================
// STATE
// =========================
bool motorEnabled = false;
bool streamEnabled = false;  // Only stream serial data when enabled

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
  // Handle serial commands
  handleSerialUI();

  // Timed auto-stop
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

  // -------------------------
  // SEND TIME LEFT (only if streaming enabled)
  // -------------------------
  static unsigned long lastTimeMsg = 0;
  if (streamEnabled && motorEnabled && millis() - lastTimeMsg > 500) {
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

  // Motor off
  if (!motorEnabled) {
    analogWrite(pin_motor, 0);
    return;
  }

  // -------------------------
  // ERROR & CONTROL
  // -------------------------
  double error = Setpoint - rpmFiltered;
  double pwmFF = kFF * Setpoint;

  if (abs(error) < 80.0) {
    speedPI.SetMode(MANUAL);
    PIout = 0;
  } else {
    speedPI.SetMode(AUTOMATIC);
    Input = rpmFiltered;
    speedPI.Compute();
  }

  // Slew limit
  static double lastPI = 0;
  if (PIout > lastPI + MAX_PI_STEP) PIout = lastPI + MAX_PI_STEP;
  if (PIout < lastPI - MAX_PI_STEP) PIout = lastPI - MAX_PI_STEP;
  lastPI = PIout;

  // Apply PWM
  double pwmCmd = pwmFF + PIout;
  pwmCmd = constrain(pwmCmd, 0, 255);
  analogWrite(pin_motor, (int)pwmCmd);

  // -------------------------
  // DEBUG OUTPUT (only if streaming enabled)
  // -------------------------
  if (streamEnabled) {
    Serial.print(Setpoint);
    Serial.print(",");
    Serial.print(rpmFiltered);
    Serial.print(",");
    Serial.println(pwmCmd);
    Serial.println("b");
  }
}

// =========================
// SERIAL UI
// =========================
void handleSerialUI() {
  if (!Serial.available()) return;

  String cmd = Serial.readStringUntil('\n');
  cmd.trim();

  // -------------------------
  // Identification
  // -------------------------
  if (cmd == "WHO") {
    Serial.println("DEVICE:STIRRER");
    return;
  }

  // -------------------------
  // Start/Stop motor
  // -------------------------
  if (cmd == "START") {
    motorEnabled = true;
    timedRunActive = true;
    runStartMillis = millis();
  } else if (cmd == "STOP") {
    motorEnabled = false;
    timedRunActive = false;
    analogWrite(pin_motor, 0);
  }

  // -------------------------
  // Setpoint & PID tuning
  // -------------------------
  if (cmd.startsWith("S ")) {
    Setpoint = constrain(cmd.substring(2).toFloat(), 0, 12000);
  } else if (cmd.startsWith("KP ")) {
    Kp = cmd.substring(3).toFloat();
    speedPI.SetTunings(Kp, Ki, 0);
  } else if (cmd.startsWith("KI ")) {
    Ki = cmd.substring(3).toFloat();
    speedPI.SetTunings(Kp, Ki, 0);
  }

  // -------------------------
  // Set runtime
  // -------------------------
  else if (cmd.startsWith("T ")) {
    double seconds = cmd.substring(2).toFloat();
    RUN_TIME_MS = (seconds <= 0) ? 0 : (unsigned long)(seconds * 1000.0);
  }

  // -------------------------
  // Streaming control
  // -------------------------
  else if (cmd == "STREAM ON") streamEnabled = true;
  else if (cmd == "STREAM OFF") streamEnabled = false;
}