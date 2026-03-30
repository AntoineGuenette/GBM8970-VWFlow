import asyncio
import argparse
import tkinter as tk

from tkinter import ttk
from bleak import BleakScanner

from UI.bluetooth.stirrer_tab import StirrerUI
from UI.counter_tab import CounterUI

# =========================
# ARGUMENT PARSING
# =========================
def parse_args():
    parser = argparse.ArgumentParser(description="GBM8970 – VWFlow bluetooth controller")

    parser.add_argument(
        "--simulate-device",
        action="store_true",
        help="Run the device in simulation mode"
    )

    return parser.parse_args()

# =========================
# BLE CONFIG (must match Arduino sketch)
# =========================
DEVICE_BLE_NAME = "Arduino"

# Stirrer characteristics
STIRRER_RX_UUID = "12345678-1234-1234-1234-123456789abd"
STIRRER_TX_UUID = "12345678-1234-1234-1234-123456789abe"

# =========================
# FIND BLE DEVICE
# =========================
def find_ble_device(simulation=False):
    print(f"Scanning BLE for '{DEVICE_BLE_NAME}'...")

    # Skip BLE discovery if simulation mode is enabled
    if simulation:
        print("Simulation mode enabled – skipping BLE device scan.\nLaunching UI...")
        return None

    async def scan():
        devices = await BleakScanner.discover(timeout=5.0)
        for d in devices:
            if d.name == DEVICE_BLE_NAME:
                print(f"  Found: {d.address}.\nLaunching UI...")
                return d.address
        return None

    loop = asyncio.new_event_loop()
    address = loop.run_until_complete(scan())
    loop.close()
    return address

# =========================
# MAIN
# =========================
def main():

    # Parse command-line arguments
    args = parse_args()

    # Set global simulation flag
    global SIMULATION
    SIMULATION = args.simulate_device

    # Set BLE connection
    ble_address = find_ble_device(SIMULATION)
    if SIMULATION:
        # Use a dummy address so downstream BLE code that expects a string does not crash
        ble_address = "00:00:00:00:00:00"
    else:
        if ble_address is None:
            raise RuntimeError(
                f"Could not find BLE device named '{DEVICE_BLE_NAME}'. "
                "Make sure the Arduino is powered on and nearby."
            )

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
    stirrer_ui = StirrerUI(
        stirrer_frame,
        ble_address=ble_address,
        rx_uuid=STIRRER_RX_UUID,
        tx_uuid=STIRRER_TX_UUID,
    )

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
