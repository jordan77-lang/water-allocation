"""Backend that smooths Arduino load-cell readings into water allocations."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import serial
from flask import Flask, jsonify
from flask_cors import CORS


# === Logging ===
logging.basicConfig(level=os.getenv("WATER_LOG_LEVEL", "INFO"))
logger = logging.getLogger("water-allocation")


# === Hardware configuration ===
# Override these via env vars when deploying on another machine, e.g. WATER_SERIAL_PORT=COM5.
SERIAL_PORT = os.getenv("WATER_SERIAL_PORT", "COM3")
BAUD_RATE = int(os.getenv("WATER_SERIAL_BAUD", "9600"))
SERIAL_RETRY_SECONDS = float(os.getenv("WATER_SERIAL_RETRY_SECONDS", "5"))


# === Bucket configuration ===
BUCKET_ORDER = ["food", "ai", "crops", "animals"]


# === Calibration constants ===
# Adjust these three sections after you weigh both bean bag types with the live rig.

# 1) Bag mass thresholds (grams). Any jump above these values will be treated as
#    a new bag drop. Update the defaults below or set WATER_LIGHT_THRESHOLD / WATER_HEAVY_THRESHOLD.
LIGHT_BAG_THRESHOLD = float(os.getenv("WATER_LIGHT_THRESHOLD", "300"))
HEAVY_BAG_THRESHOLD = float(os.getenv("WATER_HEAVY_THRESHOLD", "900"))

# 2) Water added per bag (water points). Decide how much each bag should raise
#    the bucket. These numbers are what the front-end bars will display. Override via env vars.
LIGHT_BAG_INCREMENT = float(os.getenv("WATER_LIGHT_INCREMENT", "10"))
HEAVY_BAG_INCREMENT = float(os.getenv("WATER_HEAVY_INCREMENT", "25"))

# 3) Water decay. This controls how quickly the stored water drains even if no
#    new bags are added. Increase for faster drain, decrease for a slower fade.
#    Keep this roughly aligned with the front-end constants in script.js so
#    the live sensor readings fall at the same pace you see during slider tests.
#    Use WATER_DECAY_PER_SEC to tweak without editing the file.
DECAY_POINTS_PER_SECOND = float(os.getenv("WATER_DECAY_PER_SEC", "0.005"))


@dataclass
class BucketState:
    water_points: float = 0.0
    last_raw_reading: float = 0.0
    last_decay_timestamp: float = field(default_factory=time.time)


bucket_state: Dict[str, BucketState] = {
    bucket: BucketState() for bucket in BUCKET_ORDER
}

latest_raw_values: Dict[str, float] = {bucket: 0.0 for bucket in BUCKET_ORDER}

ser: Optional[serial.Serial] = None

app = Flask(__name__)
CORS(app)


def _get_serial() -> Optional[serial.Serial]:
    global ser
    if ser and ser.is_open:
        return ser
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        logger.info("Connected to %s at %s baud", SERIAL_PORT, BAUD_RATE)
    except serial.SerialException as exc:
        logger.warning("Unable to open serial port %s: %s", SERIAL_PORT, exc)
        ser = None
    return ser


def _parse_serial_line() -> Optional[List[float]]:
    """Read a CSV line from the Arduino and return four floats."""
    connection = _get_serial()
    if connection is None:
        return None
    try:
        line = connection.readline().decode("utf-8").strip()
    except serial.SerialException as exc:
        logger.warning("Serial read failed: %s", exc)
        time.sleep(SERIAL_RETRY_SECONDS)
        return None

    if not line or line.startswith("#"):
        return None

    parts = line.split(",")
    if len(parts) != len(BUCKET_ORDER):
        logger.debug("Malformed payload: %s", line)
        return None
    try:
        return [float(part) for part in parts]
    except ValueError:
        logger.debug("Non-numeric payload: %s", line)
        return None


def _apply_decay(state: BucketState, now: float) -> None:
    elapsed = now - state.last_decay_timestamp
    if elapsed <= 0:
        return
    decay = DECAY_POINTS_PER_SECOND * elapsed
    if decay > 0:
        state.water_points = max(0.0, state.water_points - decay)
    state.last_decay_timestamp = now


def _ingest_raw_readings(raw_values: Optional[List[float]]) -> Dict[str, float]:
    """Update bucket state using the latest raw readings and return water totals."""
    now = time.time()
    for idx, bucket in enumerate(BUCKET_ORDER):
        state = bucket_state[bucket]

        if raw_values is not None:
            raw = raw_values[idx]
            latest_raw_values[bucket] = raw
            delta = raw - state.last_raw_reading

            if delta >= HEAVY_BAG_THRESHOLD:
                state.water_points += HEAVY_BAG_INCREMENT
                logger.info("Detected heavy bag on %s (delta %.2f)", bucket, delta)
            elif delta >= LIGHT_BAG_THRESHOLD:
                state.water_points += LIGHT_BAG_INCREMENT
                logger.info("Detected light bag on %s (delta %.2f)", bucket, delta)

            state.last_raw_reading = raw

        _apply_decay(state, now)

    return {bucket: round(bucket_state[bucket].water_points, 2) for bucket in BUCKET_ORDER}


@app.route("/data")
def get_data():
    raw_values = _parse_serial_line()
    totals = _ingest_raw_readings(raw_values)
    return jsonify(totals)


@app.route("/debug/raw")
def debug_raw():
    """Expose the latest raw readings and current water points for troubleshooting."""
    serial_ok = ser is not None and ser.is_open
    payload = {
        "raw": latest_raw_values,
        "water_points": {bucket: state.water_points for bucket, state in bucket_state.items()},
        "serial_port": SERIAL_PORT,
        "serial_connected": serial_ok,
        "light_threshold": LIGHT_BAG_THRESHOLD,
        "heavy_threshold": HEAVY_BAG_THRESHOLD,
    }
    return jsonify(payload)


@app.route("/config")
def get_config():
    """Return runtime tuning values so the frontend stays in sync with the backend."""
    return jsonify({"decay_per_sec": DECAY_POINTS_PER_SECOND})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
