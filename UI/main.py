import time
import serial
import serial.tools.list_ports
import tkinter as tk
from tkinter import ttk

from stirrer_tab import StirrerUI
from sensor_tab import SensorUI

def identify_arduinos(ports, baud=9600):
    import time

    stirrer_port = None
    sensor_port = None

    print("Identifying Arduinos...")

    for p in ports:
        try:
            print(f"\nTesting {p.device}...")
            ser = serial.Serial(p.device, baud, timeout=0.5)
            time.sleep(1)  # allow Arduino reset

            # Try multiple WHO attempts to catch boards that reset slowly
            for _ in range(2):
                ser.write(b"WHO\n")
                time.sleep(0.1)

            t0 = time.time()
            while time.time() - t0 < 1:
                line = ser.readline().decode(errors="ignore").strip()
                print(f"{p.device} → '{line}'")
                if not line:
                    continue

                if line == "DEVICE:STIRRER":
                    stirrer_port = p.device
                elif line == "DEVICE:SENSOR":
                    sensor_port = p.device

            ser.close()
        except Exception as e:
            print("Error on", p.device, e)

    print(f"\nIdentified stirrer on {stirrer_port}, sensor on {sensor_port}")
    print("\nLaunching UI...")
    return stirrer_port, sensor_port


def main():

    BAUD = 9600

    ports = list(serial.tools.list_ports.comports())

    STIRRER_PORT, SENSOR_PORT = identify_arduinos(ports, BAUD)

    if STIRRER_PORT is None or SENSOR_PORT is None:
        raise RuntimeError("Could not identify both Arduinos")

    ser_stirrer = serial.Serial(STIRRER_PORT, BAUD, timeout=2)
    ser_sensor  = serial.Serial(SENSOR_PORT, BAUD, timeout=2)

    # Initialize UI
    root = tk.Tk()
    root.title("GBM8970 – VWFlow")
    root.geometry("1200x800")

    # Create notebook and tabs
    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True)

    # Create stirrer tab
    stirrer_frame = ttk.Frame(notebook)
    notebook.add(stirrer_frame, text="Stirrer")
    stirrer_ui = StirrerUI(stirrer_frame, ser_stirrer)

    # Create sensor tab
    sensor_frame = ttk.Frame(notebook)
    notebook.add(sensor_frame, text="Sensor")
    sensor_ui  = SensorUI(sensor_frame, ser_sensor)

    # Handle window close event
    def on_close():
        stirrer_ui.on_close()
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", on_close)

    # Start the main event loop
    root.mainloop()

if __name__ == "__main__":
    main()
