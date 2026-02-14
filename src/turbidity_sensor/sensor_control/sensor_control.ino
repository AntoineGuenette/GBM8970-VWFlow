// =========================
// PIN SETUP
// =========================
const int pin_ledIR = 8;     // IR LED
const int pin_adc   = A0;    // OPA350 output

// =========================
// ACQUISITION CONFIG
// =========================
const int N_AVG = 100;       // ADC averaging
const int T_US  = 300;       // LED settle time (µs)

// =========================
// TIMING
// =========================
const unsigned long ACQ_TIME_MS    = 5000;   // total run time
const unsigned long SAMPLE_DELAY  = 100;    // sample period
unsigned long runStartMillis = 0;
unsigned long lastSampleMillis = 0;

// =========================
// STATE
// =========================
bool acquisitionActive = true;

// =========================
// SETUP
// =========================
void setup() {
  pinMode(pin_ledIR, OUTPUT);
  digitalWrite(pin_ledIR, LOW);

  Serial.begin(9600);
  delay(1000);

  // CSV header
  Serial.println("time_ms,Voff,Von,Vdiff");

  runStartMillis = millis();
}

// =========================
// LOOP
// =========================
void loop() {

  if (!acquisitionActive) return;

  unsigned long now = millis();

  // -------------------------
  // AUTO STOP
  // -------------------------
  if (now - runStartMillis >= ACQ_TIME_MS) {
    acquisitionActive = false;
    digitalWrite(pin_ledIR, LOW);
    return;
  }

  // -------------------------
  // SAMPLE TIMING
  // -------------------------
  if (now - lastSampleMillis < SAMPLE_DELAY) return;
  lastSampleMillis = now;

  // -------------------------
  // ACQUISITION
  // -------------------------
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

  // -------------------------
  // CONVERSION
  // -------------------------
  const double ADC_TO_V = 5.0 / 1023.0;

  double Voff  = (sumOff  / (double)N_AVG) * ADC_TO_V;
  double Von   = (sumOn   / (double)N_AVG) * ADC_TO_V;
  double Vdiff = (sumDiff / (double)N_AVG) * ADC_TO_V;

  // -------------------------
  // OUTPUT CSV
  // -------------------------
  unsigned long t = now - runStartMillis;

  Serial.print(t);
  Serial.print(",");
  Serial.print(Voff, 6);
  Serial.print(",");
  Serial.print(Von, 6);
  Serial.print(",");
  Serial.println(Vdiff, 6);
}