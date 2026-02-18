import os
import time
import tkinter as tk
import pandas as pd
import numpy as np

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

CONTROL_POINTS = np.array(
    [ # (Turbidity, VWF activity) pairs for the calibration curve
        (0.45, 100), # Temporary turbidity value
        (1.2, 75), # Temporary turbidity value
        (1.95, 50), # Temporary turbidity value
        (2.7, 25), # Temporary turbidity value
        (3.25, 0) # Add a point for 0% activity (optional, but can help with extrapolation)
    ]
)

# =========================
# TURBIDITY -> VWF ACTIVITY CONVERSION
# =========================
m, b = np.polyfit(x=CONTROL_POINTS[:, 0], y=CONTROL_POINTS[:, 1], deg=1)

def turb_to_vwf_activity(turbidity: float) -> float:
    return m * turbidity + b

# =========================
# UI
# =========================
class SensorUI:
    def __init__(self, parent, ser=None, simulation_mode=False):
        # Initialize tab UI
        self.root = parent
        self.ser = ser
        self.simulation_mode = simulation_mode

        # Status variables
        try:
            v0 = self.read_V0()
            self.V0_text = tk.StringVar(value=f"Preivously measured V0: {v0:.3f}\n")
        except Exception:
            self.V0_text = tk.StringVar(value="Preivously measured V0: ---\n")

        self.V_text = tk.StringVar(value="Mean Vdiff: --- V\n")
        self.mean_turb_text = tk.StringVar(value="Mean turbidity: ---")
        self.std_turb_text = tk.StringVar(value="Std deviation: ---\n")
        self.activity_text = tk.StringVar(value="---\n")

        # Initialize serial connection
        if simulation_mode:
            self.port = "SIMULATION (UI only)"
        else:
            if self.ser is None:
                messagebox.showerror("Serial error", "No Arduino detected.")
                raise SystemExit
            self.port = self.ser.port

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
        tk.Label(left, textvariable=self.V_text,
                 font=("Helvetica", 12)).pack(pady=2)
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
        self.ax_cal.set_xlabel("Relative turbidity (%)")
        self.ax_cal.set_ylabel("VWF Activity (%)")
        self.ax_cal.grid(True)

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
    
    def acquire_data(self, duration_s=ACQ_DURATION_S):
        # Generate synthetic data in simulation mode
        if self.simulation_mode:
            t = np.linspace(0, duration_s, int(duration_s * 50))
            v0 = 1.0
            noise = np.random.normal(0, 0.02, size=len(t))
            vdiff = v0 - 0.15 + noise

            df = pd.DataFrame({
                "time_ms": t * 1000,
                "Voff": np.zeros_like(t),
                "Von": np.zeros_like(t),
                "Vdiff": vdiff
            })
            df["time_s"] = t
            return df

        # Real acquisition mode
        ser = self.ser
        time.sleep(0.1)

        rows = []
        t_start = time.time()
        while time.time() - t_start < duration_s:
            line = ser.readline().decode(errors="ignore").strip()
            if not line:
                continue
            try:
                t_ms, voff, von, vdiff = map(float, line.split(","))
                rows.append([t_ms, voff, von, vdiff])
            except ValueError:
                continue

        if not rows:
            raise RuntimeError("No data received")

        df = pd.DataFrame(rows, columns=["time_ms","Voff","Von","Vdiff"])
        df["time_s"] = df["time_ms"] / 1000.0
        return df

    def calibrate(self):
        try:
            if not self.simulation_mode:
                self.ser.write(b"START\n")

            df = self.acquire_data()
            V0 = df["Vdiff"].mean()

            os.makedirs(os.path.dirname(V0_PATH), exist_ok=True)
            with open(V0_PATH, "w") as f:
                f.write(f"{V0}\n")

            self.V0_text.set(f"Current V0: {V0:.3f} V\n")

        except Exception as e:
            messagebox.showerror("Calibration error",
                                 f"Calibration failed:\n{e}")

    def measure(self):
        try:
            if not os.path.exists(V0_PATH):
                raise RuntimeError("Calibration required")

            if not self.simulation_mode:
                self.ser.write(b"START\n")

            # Read V0 from file
            V0 = self.read_V0()

            # Acquire data and compute turbidity
            df = self.acquire_data()
            df["turbidity_percent"] = (V0 - df["Vdiff"]) / V0 * 100.0

            # Show turbidity stats
            mean_V = df["Vdiff"].mean()
            mean_turb = df["turbidity_percent"].mean()
            std_turb  = df["turbidity_percent"].std()

            self.V_text.set(f"Mean Vdiff: {mean_V:.3f} V\n")
            self.mean_turb_text.set(f"Mean turbidity: {mean_turb:.2f} %")
            self.std_turb_text.set(f"Std deviation: {std_turb:.2f} %\n")

            # Update turbidity plot
            self.ax_turb.clear()
            self.ax_turb.plot(df["time_s"], df["turbidity_percent"])
            self.ax_turb.hlines(
                [mean_turb],
                xmin=df["time_s"].min(),
                xmax=df["time_s"].max(),
                color="red",
                linestyle="--",
                label=f"Mean: {mean_turb:.2f}%"
            )
            self.ax_turb.set_xlabel("Time (s)")
            self.ax_turb.set_ylabel("Relative turbidity (%)")
            self.ax_turb.set_title("Turbidity measurement")
            self.ax_turb.grid(True)
            self.ax_turb.legend()
            self.canvas.draw_idle()

            # Show activity
            activity = turb_to_vwf_activity(mean_turb)
            max_activity = turb_to_vwf_activity(mean_turb - std_turb)
            min_activity = turb_to_vwf_activity(mean_turb + std_turb)
            std_activity = (max_activity - min_activity) / 2

            self.activity_text.set(f"({activity:.2f} ± {std_activity:.2f}) %\n")

            # Update calibration curve plot
            x_vals = np.linspace(0, CONTROL_POINTS[:, 0].max() + 0.1, 100)
            y_vals = m * x_vals + b

            self.ax_cal.clear()
            self.ax_cal.plot(x_vals, y_vals, color="black", linestyle="--",
                             label="Calibration Curve")
            self.ax_cal.scatter(
                CONTROL_POINTS[:, 0], CONTROL_POINTS[:, 1],
                color="blue",
                label="Control Points"
            )
            self.ax_cal.errorbar(
                mean_turb, activity,
                xerr=std_turb,
                yerr=std_activity,
                fmt="o",
                color="red",
                ecolor="red",
                elinewidth=2,
                capsize=5,
                label=f"Measured Point ({activity:.2f}% ± {std_activity:.2f}%)"
            )
            self.ax_cal.set_xlabel("Relative turbidity (%)")
            self.ax_cal.set_ylabel("VWF Activity (%)")
            self.ax_cal.set_ylim(0, 200)
            self.ax_cal.set_title("VWF Activity vs Turbidity Calibration Curve")
            self.ax_cal.legend()
            self.ax_cal.grid(True)
            self.canvas.draw_idle()

        except Exception as e:
            messagebox.showerror("Measurement error",
                                 f"Measurement failed:\n{e}")