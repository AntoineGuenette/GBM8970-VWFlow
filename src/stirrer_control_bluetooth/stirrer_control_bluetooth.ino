#include <ArduinoBLE.h>
#include <PID_v1.h>

// =========================
// BLE SERVICES & CHARACTERISTICS
// =========================

// --- Stirrer Service ---
BLEService stirrerService("12345678-1234-1234-1234-123456789abc");
BLEStringCharacteristic stirrerRX("12345678-1234-1234-1234-123456789abd", BLEWrite | BLEWriteWithoutResponse, 64);
BLEStringCharacteristic stirrerTX("12345678-1234-1234-1234-123456789abe", BLERead | BLENotify, 128);

// --- Sensor Service ---
BLEService sensorService("87654321-4321-4321-4321-cba987654321");
BLEStringCharacteristic sensorRX("87654321-4321-4321-4321-cba987654322", BLEWrite | BLEWriteWithoutResponse, 64);
BLEStringCharacteristic sensorTX("87654321-4321-4321-4321-cba987654323", BLERead | BLENotify, 256);

// Helper to send data over BLE
void stirrerSend(const String& s) { if (BLE.connected()) stirrerTX.setValue(s); }
void sensorSend(const String& s)  { if (BLE.connected()) sensorTX.setValue(s);  }

// =========================
// STIRRER: PIN & TIMING
// =========================
const int pin_hall  = 2;
const int pin_motor = 9;

const unsigned long CTRL_PERIOD_MS = 250;
unsigned long lastCtrlMillis = 0;

// =========================
// STIRRER: RPM & FILTER
// =========================
volatile unsigned long pulseCount = 0;
const int PULSES_PER_REV = 1;

double rawRPM      = 0.0;
double rpmFiltered = 0.0;
const double alpha = 0.05;

// =========================
// STIRRER: CONTROL
// =========================
double Setpoint = 3000.0;
double Input    = 0.0;
double PIout    = 0.0;

const double kFF        = 0.0092;
double Kp               = 0.02;
double Ki               = 0.0015;
double Kd               = 0.0;
const double MAX_PI_STEP = 1.0;

PID speedPI(&Input, &PIout, &Setpoint, Kp, Ki, Kd, DIRECT);

// =========================
// STIRRER: STATE
// =========================
bool motorEnabled  = false;
bool streamEnabled = false;
unsigned long RUN_TIME_MS    = 0;
unsigned long runStartMillis = 0;
bool timedRunActive          = false;

// =========================
// SENSOR: PINS & CONFIG
// =========================
const int pin_ledIR = 8;
const int pin_adc   = A0;

const int N_AVG                    = 100;
const int T_US                     = 300;
const unsigned long ACQ_TIME_MS    = 5000;
const unsigned long SAMPLE_DELAY   = 100;

// =========================
// SENSOR: STATE
// =========================
bool acquisitionActive       = false;
unsigned long acqStartMillis = 0;
unsigned long lastSampleMillis = 0;

// =========================
// ISR
// =========================
void hallISR() { pulseCount++; }

// =========================
// SETUP
// =========================
void setup() {
  Serial.begin(9600);

  // Stirrer pins
  pinMode(pin_hall, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(pin_hall), hallISR, FALLING);
  pinMode(pin_motor, OUTPUT);
  analogWrite(pin_motor, 0);

  // Sensor pins
  pinMode(pin_ledIR, OUTPUT);
  digitalWrite(pin_ledIR, LOW);

  // PID
  speedPI.SetSampleTime(CTRL_PERIOD_MS);
  speedPI.SetOutputLimits(-50, 50);
  speedPI.SetMode(AUTOMATIC);

  // BLE init
  if (!BLE.begin()) {
    Serial.println("BLE init failed!");
    while (1);
  }

  BLE.setLocalName("VWFlow");

  // Register stirrer service
  stirrerService.addCharacteristic(stirrerRX);
  stirrerService.addCharacteristic(stirrerTX);
  BLE.addService(stirrerService);

  // Register sensor service
  sensorService.addCharacteristic(sensorRX);
  sensorService.addCharacteristic(sensorTX);
  BLE.addService(sensorService);

  // Advertise both services
  BLE.setAdvertisedService(stirrerService);
  stirrerTX.setValue("");
  sensorTX.setValue("");

  BLE.advertise();
  Serial.println("BLE advertising as 'VWFlow'");
}

// =========================
// LOOP
// =========================
void loop() {
  BLE.poll();

  handleStirrerCommands();
  handleSensorCommands();
  runStirrerControl();
  runSensorAcquisition();
}

// =========================
// STIRRER COMMAND HANDLER
// =========================
void handleStirrerCommands() {
  if (!stirrerRX.written()) return;

  String cmd = stirrerRX.value();
  cmd.trim();

  if (cmd == "WHO") {
    stirrerSend("DEVICE:STIRRER\n");
    return;
  }
  if (cmd == "START") {
    motorEnabled    = true;
    timedRunActive  = true;
    runStartMillis  = millis();
  } else if (cmd == "STOP") {
    motorEnabled   = false;
    timedRunActive = false;
    analogWrite(pin_motor, 0);
  } else if (cmd.startsWith("S ")) {
    Setpoint = constrain(cmd.substring(2).toFloat(), 0, 12000);
  } else if (cmd.startsWith("KP ")) {
    Kp = cmd.substring(3).toFloat();
    speedPI.SetTunings(Kp, Ki, 0);
  } else if (cmd.startsWith("KI ")) {
    Ki = cmd.substring(3).toFloat();
    speedPI.SetTunings(Kp, Ki, 0);
  } else if (cmd.startsWith("T ")) {
    double seconds = cmd.substring(2).toFloat();
    RUN_TIME_MS = (seconds <= 0) ? 0 : (unsigned long)(seconds * 1000.0);
  } else if (cmd == "STREAM ON")  { streamEnabled = true;  }
  else if (cmd == "STREAM OFF") { streamEnabled = false; }
}

// =========================
// STIRRER CONTROL LOOP
// =========================
void runStirrerControl() {
  // Timed auto-stop
  if (timedRunActive && RUN_TIME_MS > 0 &&
      millis() - runStartMillis >= RUN_TIME_MS) {
    motorEnabled   = false;
    timedRunActive = false;
    analogWrite(pin_motor, 0);
  }

  unsigned long now = millis();
  if (now - lastCtrlMillis < CTRL_PERIOD_MS) return;
  lastCtrlMillis = now;

  // RPM calculation
  unsigned long pulses;
  noInterrupts();
  pulses = pulseCount;
  pulseCount = 0;
  interrupts();

  rawRPM      = (pulses * 60000.0) / (CTRL_PERIOD_MS * PULSES_PER_REV);
  rpmFiltered = alpha * rawRPM + (1.0 - alpha) * rpmFiltered;

  // Time left message
  static unsigned long lastTimeMsg = 0;
  if (streamEnabled && motorEnabled && millis() - lastTimeMsg > 500) {
    lastTimeMsg = millis();
    if (RUN_TIME_MS == 0) {
      stirrerSend("TIME_LEFT,INF\n");
    } else {
      long remaining = (long)(RUN_TIME_MS - (millis() - runStartMillis));
      if (remaining < 0) remaining = 0;
      stirrerSend("TIME_LEFT," + String(remaining) + "\n");
    }
  }

  if (!motorEnabled) {
    analogWrite(pin_motor, 0);
    return;
  }

  // PID control
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

  static double lastPI = 0;
  if (PIout > lastPI + MAX_PI_STEP) PIout = lastPI + MAX_PI_STEP;
  if (PIout < lastPI - MAX_PI_STEP) PIout = lastPI - MAX_PI_STEP;
  lastPI = PIout;

  double pwmCmd = constrain(pwmFF + PIout, 0, 255);
  analogWrite(pin_motor, (int)pwmCmd);

  if (streamEnabled) {
    stirrerSend(String(Setpoint) + "," + String(rpmFiltered) + "," + String(pwmCmd) + "\n");
    stirrerSend("b\n");
  }
}

// =========================
// SENSOR COMMAND HANDLER
// =========================
void handleSensorCommands() {
  if (!sensorRX.written()) return;

  String cmd = sensorRX.value();
  cmd.trim();

  if (cmd == "WHO") {
    sensorSend("DEVICE:SENSOR\n");
  } else if (cmd == "START") {
    acquisitionActive  = true;
    acqStartMillis     = millis();
    lastSampleMillis   = acqStartMillis;
    sensorSend("time_ms,Voff,Von,Vdiff\n");
  } else if (cmd == "STOP") {
    acquisitionActive = false;
    digitalWrite(pin_ledIR, LOW);
  }
}

// =========================
// SENSOR ACQUISITION LOOP
// =========================
void runSensorAcquisition() {
  if (!acquisitionActive) return;

  unsigned long now = millis();

  // Auto-stop after ACQ_TIME_MS
  if (now - acqStartMillis >= ACQ_TIME_MS) {
    acquisitionActive = false;
    digitalWrite(pin_ledIR, LOW);
    return;
  }

  if (now - lastSampleMillis < SAMPLE_DELAY) return;
  lastSampleMillis = now;

  // Averaging
  long sumOff = 0, sumOn = 0, sumDiff = 0;
  for (int i = 0; i < N_AVG; i++) {
    digitalWrite(pin_ledIR, LOW);
    delayMicroseconds(T_US);
    int off = analogRead(pin_adc);

    digitalWrite(pin_ledIR, HIGH);
    delayMicroseconds(T_US);
    int on = analogRead(pin_adc);

    sumOff  += off;
    sumOn   += on;
    sumDiff += (on - off);
  }

  // ESP32 ADC: 12-bit (0–4095), 3.3V reference
  const double ADC_TO_V = 3.3 / 4095.0;
  double Voff  = (sumOff  / (double)N_AVG) * ADC_TO_V;
  double Von   = (sumOn   / (double)N_AVG) * ADC_TO_V;
  double Vdiff = (sumDiff / (double)N_AVG) * ADC_TO_V;

  unsigned long t = now - acqStartMillis;
  String line = String(t) + "," +
                String(Voff, 6) + "," +
                String(Von, 6) + "," +
                String(Vdiff, 6) + "\n";
  sensorSend(line);
}
