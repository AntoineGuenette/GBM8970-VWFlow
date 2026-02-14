// ======================================
// Configuration matérielle
// ======================================
const int LED_IR  = 8;      // LED IR
const int ADC_PIN = A0;     // Sortie OPA350
const int N = 100;          // Moyennage
const int T_US = 300;       // Stabilisation (µs)

const unsigned long ACQ_TIME_MS = 300000; // 3 minutes
const unsigned long SAMPLE_DELAY = 100;   // 1 point / 500 ms

unsigned long t0;

// ======================================
// Setup
// ======================================
void setup() {
  pinMode(LED_IR, OUTPUT);
  digitalWrite(LED_IR, LOW);
  Serial.begin(9600);
  delay(1000);

  // Header CSV
  Serial.println("time_ms,Voff,Von,Vdiff");

  t0 = millis();
}

// ======================================
// Loop
// ======================================
void loop() {

  // Stop après 3 minutes
  if (millis() - t0 >= ACQ_TIME_MS) {
    while (1); // arrêt définitif
  }

  long sumOff = 0;
  long sumOn  = 0;
  long sumDiff = 0;

  for (int i = 0; i < N; i++) {

    digitalWrite(LED_IR, LOW);
    delayMicroseconds(T_US);
    int off = analogRead(ADC_PIN);

    digitalWrite(LED_IR, HIGH);
    delayMicroseconds(T_US);
    int on = analogRead(ADC_PIN);

    sumOff  += off;
    sumOn   += on;
    sumDiff += (on - off);
  }

  float Voff  = (sumOff  / (float)N) * (5.0 / 1023.0);
  float Von   = (sumOn   / (float)N) * (5.0 / 1023.0);
  float Vdiff = (sumDiff / (float)N) * (5.0 / 1023.0);

  unsigned long t = millis() - t0;

  // Ligne CSV
  Serial.print(t);
  Serial.print(",");
  Serial.print(Voff, 6);
  Serial.print(",");
  Serial.print(Von, 6);
  Serial.print(",");
  Serial.println(Vdiff, 6);

  delay(SAMPLE_DELAY);
}
