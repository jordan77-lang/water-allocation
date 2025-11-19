# Water Allocation Project

This interactive installation uses Arduino load cells to simulate water allocation choices.

## Prerequisites
Install these once on each laptop that will run the installation:
- **Python 3.10+ for Windows** (https://www.python.org/downloads/). During install, check “Add python.exe to PATH”.
- **Node.js 18+ for Windows** (https://nodejs.org). This gives you `npm`.
- **Git** (only if you are cloning directly from GitHub).

## Step-by-step setup (non-technical walkthrough)

> ✅ Tip: All commands below run in **Command Prompt**. Open it by pressing the Windows key, typing `cmd`, and hitting Enter.

1. **Download the project**
   - Clone or copy the `water-allocation` folder onto your laptop (e.g., `C:\Users\you\Documents\water`).

2. **Wire the hardware**
   - Connect the Arduino and four HX711 load cells exactly as shown in your build guide.
   - Plug the Arduino into the laptop with a USB cable.

3. **Calibrate the load cells**
   - Open `arduino_water_allocation.ino` in the Arduino IDE.
   - Place a known weight (e.g., 500 g) on each bucket, run `scale.get_units()` in the serial monitor, and calculate `calibrationFactor = reading / weight`.
   - Update the four `calibrationFactor` entries in the sketch with your measured numbers. Leave `tareOffset` at `0` unless you have stored offsets.
   - Upload the sketch to the Arduino. When it runs, it will print four comma-separated gram values every second.

4. **Create a Python virtual environment** (this keeps dependencies self-contained):
   ```cmdnpm start
   cd C:\Users\you\Documents\water
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r water-allocation\requirements.txt
   ```
   - Run these commands once per laptop. In the future, activate the env with `.venv\Scripts\activate` before launching the app.

5. **Install Node.js packages** (while the virtualenv is still active):
   ```cmd
   cd water-allocation
   npm install
   ```
   - This installs the local web server and helper tools defined in `package.json`.

6. **Provide your hardware settings via `.env`**
   - Copy the template: `copy .env.example .env`
   - Edit `.env` (Notepad works). Change `WATER_SERIAL_PORT` to the COM port shown in Arduino IDE (e.g., `COM5`).
   - Adjust the threshold numbers if your bean bags weigh different amounts.

7. **Start everything with one command**
   ```cmd
   npm start
   ```
   - The script launches the Python backend on `http://localhost:5000` and serves the website at `http://127.0.0.1:4173`.
   - The browser automatically reads the decay rate from the backend, so you only change `WATER_DECAY_PER_SEC` inside `.env`.
   - Leave this Command Prompt window open while guests use the installation. Press `Ctrl+C` twice to stop both servers.

8. **Optional individual control**
   - Run only the backend: `npm run backend`
   - Run only the frontend: `npm run frontend`

9. **Verify the system**
   - In a browser, open `http://127.0.0.1:4173`. You should see the water allocation UI.
   - Drop a bean bag. If the bar doesn’t move, visit `http://localhost:5000/debug/raw` to confirm grams are changing.

Place bean bags in buckets → bars rise + sounds play.

During troubleshooting, hit `http://localhost:5000/debug/raw` to see the most recent raw readings and confirm your thresholds match the gram deltas.

## Repo Structure
- backend/ → Python server reading serial
- frontend/ → Web visualization
- sounds/ → Audio cues
