"""Backend that smooths Arduino load-cell readings into water allocations."""

from __future__ import annotations

import serial
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from flask import Flask, jsonify
from flask_cors import CORS


# === Hardware configuration ===
SERIAL_PORT = "COM3"  # TODO: change to whichever port your Arduino enumerates as
BAUD_RATE = 9600


# === Bucket configuration ===
BUCKET_ORDER = ["food", "ai", "crops", "animals"]


# === Calibration constants ===
# Adjust these three sections after you weigh both bean bag types with the live rig.

# 1) Bag mass thresholds (raw HX711 counts). Any jump above these values will
#    be treated as a new bag drop. Start with rough guesses, then calibrate.
LIGHT_BAG_THRESHOLD = 300  # TODO: replace with actual count for the lighter bag
HEAVY_BAG_THRESHOLD = 900  # TODO: replace with actual count for the heavier bag

# 2) Water added per bag (water points). Decide how much each bag should raise
#    the bucket. These numbers are what the front-end bars will display.
LIGHT_BAG_INCREMENT = 10  # TODO: change to the number of “water points” a light bag adds
HEAVY_BAG_INCREMENT = 25  # TODO: change to the number of “water points” a heavy bag adds

# 3) Water decay. This controls how quickly the stored water drains even if no
#    new bags are added. Increase for faster drain, decrease for a slower fade.
DECAY_POINTS_PER_SECOND = 0.4  # TODO: tune until the on-screen drain feels right


@dataclass
class BucketState:
    water_points: float = 0.0
    last_raw_reading: int = 0
    last_decay_timestamp: float = field(default_factory=time.time)


bucket_state: Dict[str, BucketState] = {
    bucket: BucketState() for bucket in BUCKET_ORDER
}


ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)

app = Flask(__name__)
CORS(app)


def _parse_serial_line() -> Optional[List[int]]:
    """Read a CSV line from the Arduino and return four raw integers."""
    line = ser.readline().decode("utf-8").strip()
    if not line:
        return None
    parts = line.split(",")
    if len(parts) != len(BUCKET_ORDER):
        return None
    try:
        return [int(part) for part in parts]
    except ValueError:
        return None


def _apply_decay(state: BucketState, now: float) -> None:
    elapsed = now - state.last_decay_timestamp
    if elapsed <= 0:
        return
    decay = DECAY_POINTS_PER_SECOND * elapsed
    if decay > 0:
        state.water_points = max(0.0, state.water_points - decay)
    state.last_decay_timestamp = now


def _ingest_raw_readings(raw_values: Optional[List[int]]) -> Dict[str, float]:
    """Update bucket state using the latest raw readings and return water totals."""
    now = time.time()
    for idx, bucket in enumerate(BUCKET_ORDER):
        state = bucket_state[bucket]

        if raw_values is not None:
            raw = raw_values[idx]
            delta = raw - state.last_raw_reading

            if delta >= HEAVY_BAG_THRESHOLD:
                state.water_points += HEAVY_BAG_INCREMENT
            elif delta >= LIGHT_BAG_THRESHOLD:
                state.water_points += LIGHT_BAG_INCREMENT

            state.last_raw_reading = raw

        _apply_decay(state, now)

    return {bucket: round(bucket_state[bucket].water_points, 2) for bucket in BUCKET_ORDER}


@app.route("/data")
def get_data():
    raw_values = _parse_serial_line()
    totals = _ingest_raw_readings(raw_values)
    return jsonify(totals)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
