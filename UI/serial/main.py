import argparse
import time
import serial
import serial.tools.list_ports
import tkinter as tk

from tkinter import ttk

from UI.serial.stirrer_tab import StirrerUI
from UI.counter_tab import CounterUI

# =========================
# ARGUMENT PARSING
# =========================
def parse_args():
    parser = argparse.ArgumentParser(description="GBM8970 – VWFlow serial controller")

    parser.add_argument(
        "--simulate-device",
        action="store_true",
        help="Run the device in simulation mode"
    )

    return parser.parse_args()


# =========================
# FIND SERIAL DEVICE
# =========================
def find_serial_device(ports, baud=9600, simulation=False):

     # Skip serial discovery if simulation mode is enabled
    if simulation:
        print("Simulation mode enabled. Skipping serial device scan.\nLaunching UI...")
        return "SIMULATION"

    print("Identifying Arduino...")

    for p in ports:
        try:
            print(f"Testing {p.device}...")

            with serial.Serial(p.device, baud, timeout=0.5) as ser:
                time.sleep(1)  # allow reset
                ser.write(b"WHO\n")
                time.sleep(0.1)

                t0 = time.time()
                while time.time() - t0 < 1:
                    line = ser.readline().decode(errors="ignore").strip()
                    if line == "DEVICE:STIRRER":
                        print(f"Found Arduino on {p.device}.\nLaunching UI...")
                        return p.device

        except Exception as e:
            print(f"Error on {p.device}: {e}")

    print("No Arduino found.")
    return None

# =========================
# MAIN
# =========================
def main():

    # Parse command-line arguments
    args = parse_args()

    # Set global simulation flag
    global SIMULATION
    SIMULATION = args.simulate_device

    # Set serial connection
    BAUD = 9600
    ports = list(serial.tools.list_ports.comports())
    port = find_serial_device(ports, BAUD, SIMULATION)
    if not SIMULATION and port is None:
        raise RuntimeError("Could not identify Arduino")
    ser = None if SIMULATION else serial.Serial(port, BAUD, timeout=2)

    # Initialize UI
    root = tk.Tk()
    root.title("VWFlow")
    root.geometry("1200x800")

    # Create notebook and tabs
    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True)

    # Create stirrer tab
    stirrer_frame = ttk.Frame(notebook)
    notebook.add(stirrer_frame, text="Stirrer")
    stirrer_ui = StirrerUI(stirrer_frame, ser, simulation_mode=SIMULATION)

    # Create counter tab
    counter_frame = ttk.Frame(notebook)
    notebook.add(counter_frame, text="Counter")
    counter_ui = CounterUI(counter_frame)

    # Handle window close event
    def on_close():
        stirrer_ui.on_close()
        counter_ui.on_close()
        root.destroy()
        print("\nApplication closed with success.")
    root.protocol("WM_DELETE_WINDOW", on_close)

    # Start the main event loop
    root.mainloop()


if __name__ == "__main__":
    main()
