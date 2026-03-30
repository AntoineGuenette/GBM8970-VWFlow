#include <ArduinoBLE.h>
#include <AutoTunePID.h>

// =========================
// BLE
// =========================
BLEService stirrerService("12345678-1234-1234-1234-123456789abc");

BLEStringCharacteristic stirrerRX(
  "12345678-1234-1234-1234-123456789abd",
  BLEWrite | BLEWriteWithoutResponse,
  64
);

BLEStringCharacteristic stirrerTX(
  "12345678-1234-1234-1234-123456789abe",
  BLERead | BLENotify,
  128
);

void stirrerSend(const String& s) {
  if (BLE.connected()) stirrerTX.setValue(s);
}

// =========================
// PINS
// =========================
const int pin_hall  = 14;
const int pin_motor = 5;

// =========================
// TUNED CONSTANTS  ← edit only here
// =========================

// RPM filter
const int   WINDOW_SIZE  = 3;       // ticks × 100ms per RPM average
const float EMA_ALPHA    = 0.4f;    // EMA smoothing (0=max smooth, 1=raw)

// Hall sensor debounce (safe for 1 pulse/rev at 8000 RPM = 7500 µs/rev)
const unsigned long DEBOUNCE_US = 4000;

// Feedforward:  PWM = FF_OFFSET + KFF × Setpoint
const float KFF       = 0.00398f;
const float FF_OFFSET = 41.0f;

// PI gains  (D = 0)
const float KP = 0.008f;
const float KI = 0.0004f;

// Setpoint limits
const float SP_MIN = 0.0f;
const float SP_MAX = 5000.0f;

// Pulses per revolution from hall sensor
const int PULSES_PER_REV = 1;

// Control loop period
const unsigned long CTRL_PERIOD_MS = 100;

// =========================
// TIMING
// =========================
unsigned long lastCtrlMillis = 0;

// =========================
// RPM MEASUREMENT
// =========================
volatile unsigned long pulseCount  = 0;
volatile unsigned long lastPulseUs = 0;

float rawRPM      = 0.0f;
float rpmFiltered = 0.0f;

static unsigned long pulseSum    = 0;
static int           windowCount = 0;

// =========================
// CONTROLLER
// =========================
float Setpoint = 0.0f;

AutoTunePID pid(0.0f, 255.0f, TuningMethod::CohenCoon);

// =========================
// STATE
// =========================
bool motorEnabled  = false;
bool streamEnabled = true;

unsigned long RUN_TIME_MS    = 0;
unsigned long runStartMillis = 0;
bool timedRunActive          = false;

// =========================
// ISR
// =========================
void hallISR() {
  unsigned long now = micros();
  if (now - lastPulseUs >= DEBOUNCE_US) {
    pulseCount++;
    lastPulseUs = now;
  }
}

// =========================
// SETUP
// =========================
void setup() {
  Serial.begin(9600);

  pinMode(pin_hall, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(pin_hall), hallISR, FALLING);

  pinMode(pin_motor, OUTPUT);
  analogWrite(pin_motor, 0);

  pid.setSetpoint(Setpoint);
  pid.setManualGains(KP, KI, 0.0f);
  pid.enableAntiWindup(true, 0.8f);
  pid.setOscillationMode(OscillationMode::Normal);

  if (!BLE.begin()) { while (1) {} }

  BLE.setLocalName("Arduino");
  BLE.setDeviceName("Arduino");

  stirrerService.addCharacteristic(stirrerRX);
  stirrerService.addCharacteristic(stirrerTX);
  BLE.addService(stirrerService);
  BLE.setAdvertisedService(stirrerService);

  stirrerTX.setValue("");
  BLE.advertise();
}

// =========================
// LOOP
// =========================
void loop() {
  BLE.poll();
  handleCommands();
  runControl();
}

// =========================
// COMMANDS
// =========================
//   WHO         → identify device
//   START       → enable motor
//   STOP        → disable motor
//   S <rpm>     → set target RPM
//   T <seconds> → set run duration (0 = forever)
//   STREAM ON   → enable data stream
//   STREAM OFF  → disable data stream
// =========================
void handleCommands() {
  if (!stirrerRX.written()) return;

  String cmd = stirrerRX.value();
  cmd.trim();

  if (cmd == "WHO") {
    stirrerSend("DEVICE:STIRRER\n");
  }
  else if (cmd == "START") {
    motorEnabled    = true;
    timedRunActive  = true;
    runStartMillis  = millis();
    pid.setManualGains(KP, KI, 0.0f);  // reset integrator on each start
  }
  else if (cmd == "STOP") {
    motorEnabled   = false;
    timedRunActive = false;
    analogWrite(pin_motor, 0);
    stirrerSend("STOPPED\n");
  }
  else if (cmd.startsWith("S ")) {
    Setpoint = constrain(cmd.substring(2).toFloat(), SP_MIN, SP_MAX);
    pid.setSetpoint(Setpoint);
    stirrerSend("SETPOINT," + String(Setpoint, 0) + "\n");
  }
  else if (cmd.startsWith("T ")) {
    float seconds = cmd.substring(2).toFloat();
    RUN_TIME_MS = (seconds <= 0.0f) ? 0UL : (unsigned long)(seconds * 1000.0f);
  }
  else if (cmd == "STREAM ON") {
    streamEnabled = true;
  }
  else if (cmd == "STREAM OFF") {
    streamEnabled = false;
  }
}

// =========================
// CONTROL LOOP
// =========================
void runControl() {
  unsigned long now = millis();
  if (now - lastCtrlMillis < CTRL_PERIOD_MS) return;
  lastCtrlMillis = now;

  // --- Timed run check ---
  if (timedRunActive && RUN_TIME_MS > 0 && (now - runStartMillis >= RUN_TIME_MS)) {
    motorEnabled   = false;
    timedRunActive = false;
    analogWrite(pin_motor, 0);
    stirrerSend("STOPPED\n");
    return;
  }

  // --- RPM measurement ---
  unsigned long pulses;
  noInterrupts();
  pulses     = pulseCount;
  pulseCount = 0;
  interrupts();

  pulseSum += pulses;
  windowCount++;

  if (windowCount >= WINDOW_SIZE) {
    rawRPM = (pulseSum * 60000.0f) /
             ((float)(CTRL_PERIOD_MS * windowCount) * PULSES_PER_REV);
    pulseSum    = 0;
    windowCount = 0;
  }

  rpmFiltered = EMA_ALPHA * rawRPM + (1.0f - EMA_ALPHA) * rpmFiltered;

  // --- Motor off ---
  if (!motorEnabled) {
    analogWrite(pin_motor, 0);
    return;
  }

  // --- Feedforward + PI ---
  float pwmFF  = FF_OFFSET + KFF * Setpoint;
  pid.update(rpmFiltered);
  float pwmPID = pid.getOutput();

  int pwm = constrain((int)(pwmFF + pwmPID), 0, 255);
  analogWrite(pin_motor, pwm);

  // --- Stream: Setpoint,RPM,PWM ---
  if (streamEnabled) {
    stirrerSend(
      String(Setpoint,    0) + "," +
      String(rpmFiltered, 1) + "," +
      String(pwm)            + "\n"
    );
  }
}
