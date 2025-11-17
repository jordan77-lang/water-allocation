# Water Allocation Project

This interactive installation uses Arduino load cells to simulate water allocation choices.

## Setup
1. Connect Arduino with HX711 load cells.
2. Upload Arduino sketch that prints CSV values: `val1,val2,val3,val4`.
3. Run backend:
   ```
   cd backend
   python server.py
   ```
4. Open `frontend/index.html` in a browser (served locally or via VS Code Live Server).

Place bean bags in buckets → bars rise + sounds play.

## Repo Structure
- backend/ → Python server reading serial
- frontend/ → Web visualization
- sounds/ → Audio cues
