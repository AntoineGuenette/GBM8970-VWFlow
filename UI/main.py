import argparse
import time
import serial
import serial.tools.list_ports
import tkinter as tk
from tkinter import ttk

from stirrer_tab import StirrerUI
from sensor_tab import SensorUI

def parse_args():
    # Parse command-line arguments for simulation modes
    parser = argparse.ArgumentParser(description="GBM8970 – VWFlow controller")

    parser.add_argument(
        "--simulate-stirrer",
        action="store_true",
        help="Run the stirrer in simulation mode"
    )

    parser.add_argument(
        "--simulate-sensor",
        action="store_true",
        help="Run the sensor in simulation mode"
    )

    return parser.parse_args()

def identify_arduinos(ports, baud=9600, stirrer_simulation=False, sensor_simulation=False):

    stirrer_port = None if not stirrer_simulation else "SIMULATION"
    sensor_port = None if not sensor_simulation else "SIMULATION"

    print("Identifying Arduinos...")

    for p in ports:

        if stirrer_simulation and sensor_simulation:
            break
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
                if not line:
                    continue

                if line == "DEVICE:STIRRER" and not stirrer_simulation:
                    stirrer_port = p.device
                    print(f"Identified stirrer on {stirrer_port}")
                elif line == "DEVICE:SENSOR" and not sensor_simulation:
                    sensor_port = p.device
                    print(f"Identified sensor on {sensor_port}")

                if stirrer_simulation :
                    stirrer_port = "SIMULATION"
                if sensor_simulation:
                    sensor_port = "SIMULATION"

            ser.close()

        except Exception as e:
            print("Error on", p.device, e)

    print(f"\nFound stirrer on {stirrer_port} and sensor on {sensor_port}")
    
    print("\nLaunching UI...")
    return stirrer_port, sensor_port


def main():

    # Parse command-line arguments
    args = parse_args()

    # Set global simulation flags
    global STIRRER_SIMULATION, SENSOR_SIMULATION
    STIRRER_SIMULATION = args.simulate_stirrer
    SENSOR_SIMULATION  = args.simulate_sensor

    # Identify Arduinos and open serial connections
    BAUD = 9600
    ports = list(serial.tools.list_ports.comports())
    STIRRER_PORT, SENSOR_PORT = identify_arduinos(
        ports,
        BAUD,
        stirrer_simulation=STIRRER_SIMULATION,
        sensor_simulation=SENSOR_SIMULATION
    )
    if (not STIRRER_SIMULATION and STIRRER_PORT is None) or \
       (not SENSOR_SIMULATION and SENSOR_PORT is None):
        raise RuntimeError("Could not identify required Arduinos")
    ser_stirrer = None if STIRRER_SIMULATION else serial.Serial(STIRRER_PORT, BAUD, timeout=2)
    ser_sensor  = None if SENSOR_SIMULATION else serial.Serial(SENSOR_PORT, BAUD, timeout=2)

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
    stirrer_ui = StirrerUI(stirrer_frame, ser_stirrer, simulation_mode=STIRRER_SIMULATION)

    # Create sensor tab
    sensor_frame = ttk.Frame(notebook)
    notebook.add(sensor_frame, text="Sensor")
    sensor_ui  = SensorUI(sensor_frame, ser_sensor, simulation_mode=SENSOR_SIMULATION)

    # Handle window close event
    def on_close():
        stirrer_ui.on_close()
        sensor_ui.on_close()
        root.destroy()
        print("\nApplication closed with success.")
    root.protocol("WM_DELETE_WINDOW", on_close)

    # Start the main event loop
    root.mainloop()

if __name__ == "__main__":
    main()
