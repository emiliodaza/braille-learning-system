const int vibradores[] = {2, 3, 4, 5, 6, 7};

void setup() {
  // Initialize vibrator pins as outputs
  for (int i = 0; i < 6; i++) {
    pinMode(vibradores[i], OUTPUT);
    digitalWrite(vibradores[i], LOW);
  }
  Serial.begin(9600);  // Start serial communication at 9600 baud
}

void loop() {
  // Check if data is available on the serial port
  if (Serial.available() > 0) {
    // Read until newline and trim any extra whitespace
    String braille_code = Serial.readStringUntil('\n');
    braille_code.trim();
    
    // Only process valid six-character Braille codes
    if (braille_code.length() == 6) {
      displayBraille(braille_code);
    }
  }
}

void displayBraille(String braille_code) {
  // Set each vibrator based on the corresponding bit in the code
  for (int i = 0; i < 6; i++) {
    if (braille_code.charAt(i) == '1') {
      digitalWrite(vibradores[i], HIGH);
    } else {
      digitalWrite(vibradores[i], LOW);
    }
  }
  delay(1000);  // Keep the vibrators on for 1 second

  // Turn off all vibrators
  for (int i = 0; i < 6; i++) {
    digitalWrite(vibradores[i], LOW);
  }
  delay(1000);  // Pause before processing the next code
}
