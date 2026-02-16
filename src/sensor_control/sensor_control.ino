// =========================
// PIN & ACQUISITION SETUP
// =========================
const int pin_ledIR = 8;     // IR LED
const int pin_adc   = A0;    // OPA350 output

const int N_AVG = 100;       // ADC averaging
const int T_US  = 300;       // LED settle time (µs)

const unsigned long ACQ_TIME_MS  = 5000; // measurement duration
const unsigned long SAMPLE_DELAY  = 100; // sample period

unsigned long runStartMillis = 0;
unsigned long lastSampleMillis = 0;

bool acquisitionActive = false; // initially off
String cmd; // last received serial command

// =========================
// SETUP
// =========================
void setup() {
  pinMode(pin_ledIR, OUTPUT);
  digitalWrite(pin_ledIR, LOW);

  Serial.begin(9600);

  // header is only printed when a run starts
  runStartMillis = millis();
}

// =========================
// LOOP
// =========================
void loop() {
  // -------------------------
  // SERIAL COMMANDS
  // -------------------------
  if (Serial.available()) {
    cmd = Serial.readStringUntil('\n');
    cmd.trim();

    // Identification
    if (cmd == "WHO") {
      Serial.println("DEVICE:SENSOR");
      return;
    }

    // START measurement
    if (cmd == "START") {
      acquisitionActive = true;
      runStartMillis    = millis();
      lastSampleMillis  = runStartMillis;
      Serial.println("time_ms,Voff,Von,Vdiff");
    }

    // STOP measurement
    if (cmd == "STOP") {
      acquisitionActive = false;
      digitalWrite(pin_ledIR, LOW);
      return;
    }
  }

  if (!acquisitionActive) return;

  unsigned long now = millis();

  // Auto-stop
  if (now - runStartMillis >= ACQ_TIME_MS) {
    acquisitionActive = false;
    digitalWrite(pin_ledIR, LOW);
    return;
  }

  // Sample timing
  if (now - lastSampleMillis < SAMPLE_DELAY) return;
  lastSampleMillis = now;

  // Acquisition averaging
  long sumOff  = 0;
  long sumOn   = 0;
  long sumDiff = 0;

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

  // Convert to voltage
  const double ADC_TO_V = 5.0 / 1023.0;
  double Voff  = (sumOff  / (double)N_AVG) * ADC_TO_V;
  double Von   = (sumOn   / (double)N_AVG) * ADC_TO_V;
  double Vdiff = (sumDiff / (double)N_AVG) * ADC_TO_V;

  // Output CSV
  unsigned long t = now - runStartMillis;
  Serial.print(t);
  Serial.print(",");
  Serial.print(Voff, 6);
  Serial.print(",");
  Serial.print(Von, 6);
  Serial.print(",");
  Serial.println(Vdiff, 6);
}