import os
import time
import tkinter as tk
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import serial
import serial.tools.list_ports
import pandas as pd

# =========================
# CONFIG
# =========================
BAUD = 9600
ACQ_DURATION_S = 5.0
V0_FILE = "V0.txt"
SCRIPT_DIR = os.path.dirname(__file__)
V0_PATH = os.path.join(SCRIPT_DIR, "..", "data", V0_FILE)
print(f"V0 path: {V0_PATH}")

# =========================
# SERIAL
# =========================
def find_arduino_port():
    for p in serial.tools.list_ports.comports():
        if ("usbmodem" in p.device.lower() or
            "usbserial" in p.device.lower() or
            "arduino" in p.description.lower()):
            return p.device
    return None

# =========================
# ACQUISITION
# =========================
def acquire_data(duration_s=ACQ_DURATION_S):
    PORT = find_arduino_port()
    if PORT is None:
        raise RuntimeError("No Arduino detected")

    ser = serial.Serial(PORT, BAUD, timeout=1)
    time.sleep(2)

    rows = []
    t_start = time.time()

    while time.time() - t_start < duration_s:
        line = ser.readline().decode(errors="ignore").strip()

        if not line or line.startswith("time_ms"):
            continue

        try:
            t_ms, voff, von, vdiff = map(float, line.split(","))
            rows.append([t_ms, voff, von, vdiff])
        except ValueError:
            continue

    ser.close()

    if not rows:
        raise RuntimeError("No data received")

    df = pd.DataFrame(rows, columns=["time_ms","Voff","Von","Vdiff"])
    df["time_s"] = df["time_ms"] / 1000.0
    return df

# =========================
# CALIBRATION
# =========================
def calibrate():
    df = acquire_data()
    V0 = df["Vdiff"].mean()

    with open(V0_PATH, "w") as f:
        f.write(f"{V0}\n")

    return V0

# =========================
# MEASUREMENT
# =========================
def measure():
    if not os.path.exists(V0_PATH):
        raise RuntimeError("Calibration required")

    with open(V0_PATH, "r") as f:
        V0 = float(f.read())

    df = acquire_data()
    df["turbidity_percent"] = (1.0 - df["Vdiff"] / V0) * 100.0

    mean = df["turbidity_percent"].mean()
    std  = df["turbidity_percent"].std()

    return df, mean, std

# =========================
# UI
# =========================
class TurbidityUI:
    def __init__(self, root):
        self.root = root
        root.title("Turbidity Sensor")

        self.result_text = tk.StringVar(value="---")

        # Buttons
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="Calibrate", width=15, command=self.on_calibrate).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Measure", width=15, command=self.on_measure).pack(side=tk.LEFT, padx=5)

        # Result label
        tk.Label(root, textvariable=self.result_text, font=("Helvetica", 12)).pack(pady=5)

        # Plot
        self.fig = Figure(figsize=(6, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.grid(True)

        self.canvas = FigureCanvasTkAgg(self.fig, master=root)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def on_calibrate(self):
        try:
            V0 = calibrate()
            self.result_text.set(f"Calibration done\nV0 = {V0:.6f} V")
        except Exception as e:
            self.result_text.set(f"Calibration failed:\n{e}")

    def on_measure(self):
        try:
            df, mean, std = measure()
            self.ax.clear()
            self.ax.plot(df["time_s"], df["turbidity_percent"])
            self.ax.set_xlabel("Time (s)")
            self.ax.set_ylabel("Relative turbidity (%)")
            self.ax.set_title("Turbidity measurement")
            self.ax.grid(True)
            self.canvas.draw_idle()

            self.result_text.set(
                f"Mean turbidity: {mean:.2f} %\n"
                f"Std deviation: {std:.2f} %"
            )
        except Exception as e:
            self.result_text.set(f"Measurement failed:\n{e}")

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    root = tk.Tk()
    app = TurbidityUI(root)
    root.mainloop()