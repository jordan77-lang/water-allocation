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
SERIAL_PORT = os.getenv("WATER_SERIAL_PORT", "COM6")
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


# 4) Debounce. Time in seconds to ignore new bags after a drop is detected.
#    This prevents the "shock" or bounce of a bag from registering as a second drop.
BAG_DEBOUNCE_SECONDS = float(os.getenv("WATER_BAG_DEBOUNCE_SECONDS", "0.5"))


@dataclass
class BucketState:
    water_points: float = 0.0
    last_raw_reading: float = 0.0
    last_decay_timestamp: float = field(default_factory=time.time)
    last_trigger_timestamp: float = 0.0


bucket_state: Dict[str, BucketState] = {
    bucket: BucketState() for bucket in BUCKET_ORDER
}

latest_raw_values: Dict[str, float] = {bucket: 0.0 for bucket in BUCKET_ORDER}

last_serial_error = None
ser: Optional[serial.Serial] = None

app = Flask(__name__)
CORS(app)


import serial.tools.list_ports

# List ports on startup to help user debug
print("--- Available COM Ports ---")
for p in serial.tools.list_ports.comports():
    print(f"  {p.device}: {p.description}")
print("---------------------------")


def _get_serial() -> Optional[serial.Serial]:
    global ser, last_serial_error
    if ser and ser.is_open:
        return ser
    try:
        print(f"Attempting to connect to {SERIAL_PORT}...")
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        # DTR/RTS dance to ensure reset or stable connection
        ser.dtr = False
        time.sleep(0.1)
        ser.dtr = True
        ser.reset_input_buffer()
        
        last_serial_error = None
        logger.info("Connected to %s at %s baud", SERIAL_PORT, BAUD_RATE)
    except serial.SerialException as exc:
        last_serial_error = str(exc)
        if "Access is denied" in str(exc):
            logger.error("!!! PORT BUSY !!!")
            logger.error("Please CLOSE the Arduino Serial Monitor or any other app using %s.", SERIAL_PORT)
        else:
            logger.warning("Unable to open serial port %s: %s", SERIAL_PORT, exc)
        ser = None
    return ser


def _parse_serial_line() -> Optional[List[float]]:
    """Read the LATEST line from the Arduino (drain buffer)."""
    try:
        connection = _get_serial()
        if connection is None:
            return None
        
        last_valid_line = None
        
        try:
            # Read all waiting lines to get the freshest data
            while connection.in_waiting > 0:
                line_bytes = connection.readline()
                try:
                    line = line_bytes.decode("utf-8").strip()
                    if line and not line.startswith("#"):
                        last_valid_line = line
                    elif line.startswith("#"):
                        print(f"[ARDUINO LOG] {line}")
                except UnicodeDecodeError:
                    continue # Ignore garbage bytes
                    
            # If buffer was empty, try a blocking read for one line
            if last_valid_line is None:
                line = connection.readline().decode("utf-8").strip()
                if line and not line.startswith("#"):
                    last_valid_line = line
                elif line.startswith("#"):
                    print(f"[ARDUINO LOG] {line}")

        except serial.SerialException as exc:
            logger.warning("Serial read failed: %s", exc)
            time.sleep(SERIAL_RETRY_SECONDS)
            return None
        except Exception as e:
            logger.error(f"Error reading serial: {e}")
            return None

        if not last_valid_line:
            return None

        # Reject obviously invalid data early
        if len(last_valid_line) > 100 or len(last_valid_line) < 3:
            logger.debug("Line too long or too short: %s", last_valid_line)
            return None

        print(f"[RAW] {last_valid_line}")

        parts = last_valid_line.split(",")
        if len(parts) != len(BUCKET_ORDER):
            logger.debug("Malformed payload: %s", last_valid_line)
            return None
        
        # Validate each part is actually a number before converting
        for part in parts:
            if not part.replace('-', '').replace('.', '').replace(' ', '').isdigit():
                logger.debug("Non-numeric part in payload: %s", last_valid_line)
                return None
        
        try:
            return [float(part) for part in parts]
        except ValueError:
            logger.debug("Non-numeric payload: %s", last_valid_line)
            return None
    except Exception as e:
        logger.error(f"Critical error in _parse_serial_line: {e}")
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

            # Check debounce to prevent double-counting shock/bounces
            if delta >= LIGHT_BAG_THRESHOLD:
                if now - state.last_trigger_timestamp > BAG_DEBOUNCE_SECONDS:
                    if delta >= HEAVY_BAG_THRESHOLD:
                        state.water_points += HEAVY_BAG_INCREMENT
                        state.last_trigger_timestamp = now
                        logger.info("Detected heavy bag on %s (delta %.2f)", bucket, delta)
                    else:
                        state.water_points += LIGHT_BAG_INCREMENT
                        state.last_trigger_timestamp = now
                        logger.info("Detected light bag on %s (delta %.2f)", bucket, delta)
                else:
                    logger.info("Ignored drop on %s (debounce active, delta %.2f)", bucket, delta)
            elif delta > 50: # Log significant movements that are below threshold
                 logger.debug("Ignored small movement on %s (delta %.2f < threshold)", bucket, delta)

            state.last_raw_reading = raw

        _apply_decay(state, now)

    return {bucket: round(bucket_state[bucket].water_points, 2) for bucket in BUCKET_ORDER}


@app.route("/data")
def get_data():
    raw_values = _parse_serial_line()
    totals = _ingest_raw_readings(raw_values)
    
    status = "ok"
    if ser is None:
        status = "disconnected"
    elif raw_values is None:
        status = "no_data"

    return jsonify({
        "totals": totals, 
        "raw": raw_values if raw_values else [],
        "status": status,
        "error": last_serial_error
    })


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


@app.route("/reset", methods=["POST"])
def reset_state():
    """Reset all bucket water levels to zero."""
    global bucket_state
    bucket_state = {bucket: BucketState() for bucket in BUCKET_ORDER}
    logger.info("State reset triggered by client.")
    return jsonify({"status": "reset"})


@app.route("/config")
def get_config():
    """Return runtime tuning values so the frontend stays in sync with the backend."""
    return jsonify({"decay_per_sec": DECAY_POINTS_PER_SECOND})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
