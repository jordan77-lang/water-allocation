import serial
import time
import serial.tools.list_ports

PORT = "COM6"
BAUD = 9600

print(f"--- Serial Diagnostic Tool ---")
print(f"Target: {PORT} @ {BAUD}")

# List ports
print("\nAvailable Ports:")
ports = list(serial.tools.list_ports.comports())
for p in ports:
    print(f"  {p.device}: {p.description}")

if not any(p.device == PORT for p in ports):
    print(f"\nERROR: {PORT} not found in available ports!")
    exit(1)

print(f"\nAttempting to connect to {PORT}...")

try:
    ser = serial.Serial(PORT, BAUD, timeout=2)
    print("SUCCESS: Port opened.")
    
    # Toggle DTR to reset Arduino (standard procedure)
    print("Resetting board (DTR toggle)...")
    ser.dtr = False
    time.sleep(0.1)
    ser.dtr = True
    
    print("Waiting for data (Ctrl+C to stop)...")
    print("-" * 40)
    
    start_time = time.time()
    while True:
        if ser.in_waiting > 0:
            try:
                line = ser.readline().decode('utf-8').strip()
                print(f"[{time.time() - start_time:.2f}s] RECV: {line}")
            except UnicodeDecodeError:
                print(f"[{time.time() - start_time:.2f}s] ERROR: Decode failed (garbage data)")
        else:
            # Small sleep to prevent CPU hogging
            time.sleep(0.01)
            
except serial.SerialException as e:
    print(f"\nFATAL ERROR: Could not open port: {e}")
    if "Access is denied" in str(e):
        print("HINT: Close the Arduino Serial Monitor or any other app using the port.")
except KeyboardInterrupt:
    print("\nStopped by user.")
finally:
    if 'ser' in locals() and ser.is_open:
        ser.close()
        print("Port closed.")
