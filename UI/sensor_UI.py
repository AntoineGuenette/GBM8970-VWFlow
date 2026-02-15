import os
import time
import tkinter as tk
import serial
import serial.tools.list_ports
import pandas as pd

from tkinter import messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# =========================
# CONFIG
# =========================
BAUD = 9600
ACQ_DURATION_S = 5.0

V0_FILE = "V0.txt"
SCRIPT_DIR = os.path.dirname(__file__)
V0_PATH = os.path.join(SCRIPT_DIR, "..", "data", V0_FILE)

SIMULATION_MODE = False   # True = simulate the Arduino

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
# UI
# =========================
class SensorUI:
    def __init__(self, root):
        # Initialize UI
        self.root = root
        root.title("Turbidity Sensor Controller")
        root.geometry("1200x800")
        root.resizable(True, True)

        # Status variables
        self.V0_text = tk.StringVar(value=f"Preivously measured V0: {self.read_V0():.3f}\n")
        self.mean_turb_text = tk.StringVar(value="Mean turbidity: ---")
        self.std_turb_text = tk.StringVar(value="Std deviation: ---\n")
        self.activity_text = tk.StringVar(value="---\n")

        # Initialize serial connection
        if SIMULATION_MODE:
            self.ser = None
            self.port = "SIMULATION (UI only)"
        else:
            self.port = find_arduino_port()
            if self.port is None:
                messagebox.showerror("Serial error", "No Arduino detected.")
                raise SystemExit
        self.status_text = tk.StringVar(value=f"Connected to {self.port}")

        # Build the UI
        self._build_ui()

    # ================= UI =================
    def _build_ui(self):

        # Initialize left side bar
        left = tk.Frame(self.root)
        left.pack(side=tk.LEFT, padx=10, pady=10)

        # Calibration button
        tk.Button(left, text="Calibrate", width=15,
                  command=self.calibrate).pack(pady=2)
        tk.Label(left, textvariable=self.V0_text,
                 font=("Helvetica", 12)).pack(pady=2)

        # Measurement button
        tk.Button(left, text="Measure", width=15,
                  command=self.measure).pack(pady=2)
        tk.Label(left, textvariable=self.mean_turb_text,
                 font=("Helvetica", 12)).pack(pady=2)
        tk.Label(left, textvariable=self.std_turb_text,
                 font=("Helvetica", 12)).pack(pady=2)
        
        # Activity status
        tk.Label(left, text="VWF Activity",
                 font=("Helvetica", 16)).pack(pady=(20, 5))
        tk.Label(left, textvariable=self.activity_text,
                 font=("Helvetica", 12)).pack(pady=2)

        # Connection status
        tk.Label(left, textvariable=self.status_text,
                 font=("Helvetica", 9)).pack(pady=2)
        
        # Initialize right side plots
        self.fig = Figure(figsize=(6.5, 6.5), dpi=100)
        self.ax_turb = self.fig.add_subplot(211)
        self.ax_cal = self.fig.add_subplot(212)
        self.fig.subplots_adjust(hspace=0.35)

        self.ax_turb.set_title("Turbidity measurement")
        self.ax_turb.set_xlabel("Time (s)")
        self.ax_turb.set_ylabel("Relative turbidity (%)")
        self.ax_turb.grid(True)

        self.ax_cal.set_title("Calibration curve")
        self.ax_cal.grid(True)
        # TODO : add labels to calibration curve axes

        self.line_full, = self.ax_turb.plot([], [], lw=2)
        self.line_zoom, = self.ax_cal.plot([], [], lw=2)

        # Graph widget
        canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        canvas.get_tk_widget().pack(side=tk.RIGHT,
                                    fill=tk.BOTH, expand=True,
                                    padx=10, pady=10)
        self.canvas = canvas

    # ================= LOGIC =================
    def read_V0(self):
        if os.path.exists(V0_PATH):
            with open(V0_PATH, "r") as f:
                return float(f.read())
        else:
            raise RuntimeError("Not calibrated")

    def calibrate(self):
        try:
            df = acquire_data()
            V0 = df["Vdiff"].mean()

            with open(V0_PATH, "w") as f:
                f.write(f"{V0}\n")

            self.V0_text.set(f"Current V0: {V0:.3f} V\n")

        except Exception as e:
            messagebox.showerror("Calibration error",
                                 f"Calibration failed:\n{e}")
            return

    def measure(self):
        try :
            if not os.path.exists(V0_PATH):
                raise RuntimeError("Calibration required")

            V0 = self.read_V0()

            df = acquire_data()
            df["turbidity_percent"] = (V0 - df["Vdiff"]) / V0 * 100.0

            mean = df["turbidity_percent"].mean()
            std  = df["turbidity_percent"].std()

            self.mean_turb_text.set(f"Mean turbidity: {mean:.2f} %\n")
            self.std_turb_text.set(f"Std deviation: {std:.2f} %\n")

            self.ax_turb.clear()
            self.ax_turb.plot(df["time_s"], df["turbidity_percent"])
            self.ax_turb.set_xlabel("Time (s)")
            self.ax_turb.set_ylabel("Relative turbidity (%)")
            self.ax_turb.set_title("Turbidity measurement")
            self.ax_turb.grid(True)
            self.canvas.draw_idle()

        except Exception as e:
            messagebox.showerror("Measurement error",
                                 f"Measurement failed:\n{e}")
            
    # TODO : add method to update calibration curve plot

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    root = tk.Tk()
    app = SensorUI(root)
    root.mainloop()