#include "HX711.h"

// HX711 circuit wiring for four scales
const int LOADCELL_DOUT_PIN_1 = 2;
const int LOADCELL_SCK_PIN_1 = 3;
const int LOADCELL_DOUT_PIN_2 = 4;
const int LOADCELL_SCK_PIN_2 = 5;
const int LOADCELL_DOUT_PIN_3 = 6;
const int LOADCELL_SCK_PIN_3 = 7;
const int LOADCELL_DOUT_PIN_4 = 8;
const int LOADCELL_SCK_PIN_4 = 9;

HX711 scale1;
HX711 scale2;
HX711 scale3;
HX711 scale4;

void setup() {
  Serial.begin(9600);
  scale1.begin(LOADCELL_DOUT_PIN_1, LOADCELL_SCK_PIN_1);
  scale2.begin(LOADCELL_DOUT_PIN_2, LOADCELL_SCK_PIN_2);
  scale3.begin(LOADCELL_DOUT_PIN_3, LOADCELL_SCK_PIN_3);
  scale4.begin(LOADCELL_DOUT_PIN_4, LOADCELL_SCK_PIN_4);

  // Set calibration factors after determining them
  // scale1.set_scale(calibration_factor_1);
  // scale2.set_scale(calibration_factor_2);
  // scale3.set_scale(calibration_factor_3);
  // scale4.set_scale(calibration_factor_4);

  // Set offset (tare)
  // scale1.tare();
  // scale2.tare();
  // scale3.tare();
  // scale4.tare();
}

void loop() {
  long reading1 = scale1.is_ready() ? scale1.read() : 0;
  long reading2 = scale2.is_ready() ? scale2.read() : 0;
  long reading3 = scale3.is_ready() ? scale3.read() : 0;
  long reading4 = scale4.is_ready() ? scale4.read() : 0;

  // Output as CSV: food,ai,crops,animals
  Serial.print(reading1);
  Serial.print(",");
  Serial.print(reading2);
  Serial.print(",");
  Serial.print(reading3);
  Serial.print(",");
  Serial.println(reading4);

  delay(1000); // Read every second
}
