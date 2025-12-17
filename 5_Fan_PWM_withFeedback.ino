/* =====================================================
   5x PC FAN CONTROLLER – MEGA 2560
   25 kHz PWM + RPM FEEDBACK
   ===================================================== */

#define PULSES_PER_REV 2
#define SAMPLE_TIME 1000  // ms

volatile uint16_t tachCount[5] = {0, 0, 0, 0, 0};
uint16_t rpm[5] = {0, 0, 0, 0, 0};

unsigned long lastSample = 0;

/* =====================
   INTERRUPT HANDLERS
   ===================== */
void tach1() { tachCount[0]++; }
void tach2() { tachCount[1]++; }
void tach3() { tachCount[2]++; }
void tach4() { tachCount[3]++; }
void tach5() { tachCount[4]++; }

/* =====================
   FAN SPEED SETTERS
   ===================== */
void setFanSpeed(uint8_t fan, uint8_t percent) {
  percent = constrain(percent, 0, 100);
  uint16_t duty;

  switch (fan) {
    case 0: duty = (ICR1 * percent) / 100; OCR1A = duty; break;
    case 1: duty = (ICR1 * percent) / 100; OCR1B = duty; break;
    case 2: duty = (ICR3 * percent) / 100; OCR3A = duty; break;
    case 3: duty = (ICR3 * percent) / 100; OCR3B = duty; break;
    case 4: duty = (ICR4 * percent) / 100; OCR4A = duty; break;
  }
}

/* =====================
   SETUP
   ===================== */
void setup() {
  Serial.begin(115200);

  /* -------- PWM OUTPUTS -------- */
  pinMode(11, OUTPUT); //Fan 1 
  pinMode(12, OUTPUT); //Fan 2
  pinMode(5, OUTPUT);  //Fan 3
  pinMode(2, OUTPUT);  //Fan 4
  pinMode(6, OUTPUT);  //Fan 5

  /* -------- TACH INPUTS -------- */
  pinMode(18, INPUT_PULLUP); //Fan 1
  pinMode(19, INPUT_PULLUP); //Fan 2
  pinMode(20, INPUT_PULLUP); //Fan 3
  pinMode(21, INPUT_PULLUP); //Fan 4
  pinMode(3, INPUT_PULLUP);  //Fan 5

  attachInterrupt(digitalPinToInterrupt(18), tach1, FALLING);
  attachInterrupt(digitalPinToInterrupt(19), tach2, FALLING);
  attachInterrupt(digitalPinToInterrupt(20), tach3, FALLING);
  attachInterrupt(digitalPinToInterrupt(21), tach4, FALLING);
  attachInterrupt(digitalPinToInterrupt(3),  tach5, FALLING);

  /* -------- TIMER 1 -------- */
  TCCR1A = (1 << COM1A1) | (1 << COM1B1) | (1 << WGM11);
  TCCR1B = (1 << WGM13) | (1 << WGM12) | (1 << CS10);
  ICR1 = 640;

  /* -------- TIMER 3 -------- */
  TCCR3A = (1 << COM3A1) | (1 << COM3B1) | (1 << WGM31);
  TCCR3B = (1 << WGM33) | (1 << WGM32) | (1 << CS30);
  ICR3 = 640;

  /* -------- TIMER 4 -------- */
  TCCR4A = (1 << COM4A1) | (1 << WGM41);
  TCCR4B = (1 << WGM43) | (1 << WGM42) | (1 << CS40);
  ICR4 = 640;

  /* -------- INITIAL SPEEDS -------- */
  for (int i = 0; i < 5; i++) setFanSpeed(i, 50);
}

/* =====================
   LOOP
   ===================== */
void loop() {
  if (millis() - lastSample >= SAMPLE_TIME) {
    noInterrupts();
    for (int i = 0; i < 5; i++) {
      rpm[i] = (tachCount[i] * 60000UL) / (PULSES_PER_REV * SAMPLE_TIME);
      tachCount[i] = 0;
    }
    interrupts();

    for (int i = 0; i < 5; i++) {
      Serial.print("Fan ");
      Serial.print(i + 1);
      Serial.print(": ");
      Serial.print(rpm[i]);
      Serial.print(" RPM  ");
    }
    Serial.println();

    lastSample = millis();
  }
}
