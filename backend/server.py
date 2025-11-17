import serial
import time
from flask import Flask, jsonify
from flask_cors import CORS

# Adjust COM port for your system (Windows: COM3, Mac/Linux: /dev/ttyUSB0)
ser = serial.Serial('COM3', 9600, timeout=1)

app = Flask(__name__)
CORS(app)

@app.route("/data")
def get_data():
    line = ser.readline().decode('utf-8').strip()
    values = {"food":0, "ai":0, "crops":0, "animals":0}
    try:
        # Expect CSV format: val1,val2,val3,val4
        parts = line.split(",")
        if len(parts) == 4:
            values["food"] = int(parts[0])
            values["ai"] = int(parts[1])
            values["crops"] = int(parts[2])
            values["animals"] = int(parts[3])
    except:
        pass
    return jsonify(values)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
