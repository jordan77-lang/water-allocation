#include "HX711.h"

struct ScaleChannel {
  HX711 scale;
  const uint8_t doutPin;
  const uint8_t sckPin;

  float calibrationFactor;  // Counts-per-gram derived from a known weight; negative flips direction
  long tareOffset;          // Saved offset from a prior tare; leave as 0 to tare automatically at boot
};

constexpr uint8_t NUM_CHANNELS = 4;
constexpr uint8_t AVERAGE_SAMPLES = 1;           // Set to 1 for fastest response (no blocking wait)
constexpr unsigned long READ_INTERVAL_MS = 100; // Lower for faster updates, raise if USB bandwidth is tight

ScaleChannel channels[NUM_CHANNELS] = {
  // Replace the placeholder calibration factors with the value produced by scale.get_units() / known_mass.
  {HX711(), 2, 3, 7050.0f, 0},   // Food bucket 1
  {HX711(), 4, 5, 7050.0f, 0},   // AI bucket 2
  {HX711(), 6, 7, 7050.0f, 0},   // Crops bucket 3
  {HX711(), 8, 9, 7050.0f, 0}    // Animals bucket 4
};

unsigned long lastReadMillis = 0;

void applyCalibration(ScaleChannel &channel) {
  channel.scale.begin(channel.doutPin, channel.sckPin);
  channel.scale.set_scale(channel.calibrationFactor);

  if (channel.tareOffset != 0) {
    // Use a pre-recorded tare when you need consistent offsets between power cycles.
    channel.scale.set_offset(channel.tareOffset);
  } else {
    // Let the load cell settle with empty buckets before capturing a fresh tare.
    delay(200);

    // Non-blocking wait for scale to be ready
    unsigned long start = millis();
    bool ready = false;
    while (millis() - start < 500) {
      if (channel.scale.is_ready()) {
        ready = true;
        break;
      }
      delay(10);
    }

    if (ready) {
      channel.scale.tare();
      Serial.println(" -> Tared");
    } else {
      Serial.println(" -> Timeout (Sensor not ready)");
    }
  }
}

float readWeight(ScaleChannel &channel) {
  if (!channel.scale.is_ready()) {
    return NAN;
  }
  return channel.scale.get_units(AVERAGE_SAMPLES);
}

void setup() {
  Serial.begin(9600);
  Serial.println("Starting setup...");
  pinMode(LED_BUILTIN, OUTPUT);

  for (uint8_t i = 0; i < NUM_CHANNELS; ++i) {
    Serial.print("Calibrating channel ");
    Serial.println(i);
    applyCalibration(channels[i]);
  }

  Serial.println("# Water allocation monitor ready (grams)");
}

void loop() {
  const unsigned long now = millis();
  if (now - lastReadMillis < READ_INTERVAL_MS) {
    return;
  }
  lastReadMillis = now;

  static bool ledState = false;
  ledState = !ledState;
  digitalWrite(LED_BUILTIN, ledState);

  for (uint8_t i = 0; i < NUM_CHANNELS; ++i) {
    float weight = readWeight(channels[i]);
    if (isnan(weight)) {
      weight = 0.0f;
    }

    if (i > 0) {
      Serial.print(",");
    }
    Serial.print(weight, 2);
  }

  Serial.println();
}
