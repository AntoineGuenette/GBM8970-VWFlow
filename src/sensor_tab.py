import os
import time
import asyncio
import threading
import tkinter as tk
import pandas as pd
import numpy as np

from tkinter import messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from bleak import BleakClient

# =========================
# CONFIG
# =========================
ACQ_DURATION_S = 5.0

V0_FILE = "V0.txt"
SCRIPT_DIR = os.path.dirname(__file__)
V0_PATH = os.path.join(SCRIPT_DIR, "..", "data", V0_FILE)

CONTROL_POINTS = np.array(
    [
        (3.2, 100),
        (4.4, 75),
        (5.9, 50),
        (7.1, 25),
        (8.2, 0)
    ]
)

SIMULATION_MODE = False

# =========================
# TURBIDITY -> VWF ACTIVITY
# =========================
m, b = np.polyfit(x=CONTROL_POINTS[:, 0], y=CONTROL_POINTS[:, 1], deg=1)

def turb_to_vwf_activity(turbidity: float) -> float:
    return m * turbidity + b

# =========================
# BLE MANAGER (same pattern as stirrer)
# =========================
class BLEManager:
    def __init__(self, address, rx_uuid, tx_uuid, on_line_received):
        self.address = address
        self.rx_uuid = rx_uuid
        self.tx_uuid = tx_uuid
        self.on_line_received = on_line_received

        self._loop = asyncio.new_event_loop()
        self._client = None
        self._connected = False
        self._rx_buf = ""

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        asyncio.run_coroutine_threadsafe(self._connect(), self._loop)

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def _connect(self):
        try:
            self._client = BleakClient(self.address)
            await self._client.connect()
            self._connected = True
            await self._client.start_notify(self.tx_uuid, self._on_notify)
        except Exception as e:
            print(f"Sensor BLE connection error: {e}")
            self._connected = False

    def _on_notify(self, sender, data: bytearray):
        text = data.decode(errors="ignore")
        self._rx_buf += text
        while "\n" in self._rx_buf:
            line, self._rx_buf = self._rx_buf.split("\n", 1)
            line = line.strip()
            if line:
                self.on_line_received(line)

    def write(self, text: str):
        if not self._connected:
            return
        asyncio.run_coroutine_threadsafe(self._write(text), self._loop)

    async def _write(self, text: str):
        try:
            await self._client.write_gatt_char(self.rx_uuid, text.encode(), response=False)
        except Exception as e:
            print(f"Sensor BLE write error: {e}")

    def disconnect(self):
        if self._connected and self._client:
            asyncio.run_coroutine_threadsafe(self._client.disconnect(), self._loop)

# =========================
# UI
# =========================
class SensorUI:
    def __init__(self, parent, ble_address=None, rx_uuid=None, tx_uuid=None):
        self.root = parent

        # Incoming data buffer (filled by BLE thread, read by acquire_data)
        self._data_rows = []
        self._collecting = False
        self._data_lock = threading.Lock()

        # Status variables
        self.V0_text = tk.StringVar(value=f"Previously measured V0: {self._safe_read_V0()}\n")
        self.mean_turb_text = tk.StringVar(value="Mean turbidity: ---")
        self.std_turb_text  = tk.StringVar(value="Std deviation: ---\n")
        self.activity_text  = tk.StringVar(value="---\n")

        # BLE connection
        if not SIMULATION_MODE:
            self.ble = BLEManager(
                address=ble_address,
                rx_uuid=rx_uuid,
                tx_uuid=tx_uuid,
                on_line_received=self._on_line_received,
            )
            self.status_text = tk.StringVar(value=f"Connecting sensor BLE to {ble_address}...")
            self.root.after(2000, self._check_connected)
        else:
            self.ble = None
            self.status_text = tk.StringVar(value="SIMULATION (UI only)")

        self._build_ui()

    def _check_connected(self):
        if self.ble and self.ble._connected:
            self.status_text.set(f"Sensor BLE connected to {self.ble.address}")
        else:
            self.status_text.set("Sensor BLE connecting…")
            self.root.after(1000, self._check_connected)

    def _safe_read_V0(self):
        try:
            return f"{self.read_V0():.3f}"
        except Exception:
            return "Not calibrated"

    # ================= BLE LINE HANDLER =================
    def _on_line_received(self, line: str):
        """Called from BLE background thread."""
        # Skip the CSV header line
        if line.startswith("time_ms"):
            return
        # Parse CSV data rows while collecting
        if self._collecting:
            try:
                t_ms, voff, von, vdiff = map(float, line.split(","))
                with self._data_lock:
                    self._data_rows.append([t_ms, voff, von, vdiff])
            except ValueError:
                pass

    # ================= UI =================
    def _build_ui(self):
        left = tk.Frame(self.root)
        left.pack(side=tk.LEFT, padx=10, pady=10)

        tk.Button(left, text="Calibrate", width=15,
                  command=self.calibrate).pack(pady=2)
        tk.Label(left, textvariable=self.V0_text,
                 font=("Helvetica", 12)).pack(pady=2)

        tk.Button(left, text="Measure", width=15,
                  command=self.measure).pack(pady=2)
        tk.Label(left, textvariable=self.mean_turb_text,
                 font=("Helvetica", 12)).pack(pady=2)
        tk.Label(left, textvariable=self.std_turb_text,
                 font=("Helvetica", 12)).pack(pady=2)

        tk.Label(left, text="VWF Activity",
                 font=("Helvetica", 16)).pack(pady=(20, 5))
        tk.Label(left, textvariable=self.activity_text,
                 font=("Helvetica", 12)).pack(pady=2)

        tk.Label(left, textvariable=self.status_text,
                 font=("Helvetica", 9)).pack(pady=2)

        self.fig = Figure(figsize=(6.5, 6.5), dpi=100)
        self.ax_turb = self.fig.add_subplot(211)
        self.ax_cal  = self.fig.add_subplot(212)
        self.fig.subplots_adjust(hspace=0.35)

        self.ax_turb.set_title("Turbidity measurement")
        self.ax_turb.set_xlabel("Time (s)")
        self.ax_turb.set_ylabel("Relative turbidity (%)")
        self.ax_turb.grid(True)

        self.ax_cal.set_title("Calibration curve")
        self.ax_cal.set_xlabel("Relative turbidity (%)")
        self.ax_cal.set_ylabel("VWF Activity (%)")
        self.ax_cal.grid(True)

        canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        canvas.get_tk_widget().pack(side=tk.RIGHT, fill=tk.BOTH, expand=True,
                                    padx=10, pady=10)
        self.canvas = canvas

    # ================= LOGIC =================
    def read_V0(self):
        if os.path.exists(V0_PATH):
            with open(V0_PATH, "r") as f:
                return float(f.read())
        raise RuntimeError("Not calibrated")

    def acquire_data(self, duration_s=ACQ_DURATION_S):
        """Send START, collect BLE data for duration_s seconds, return DataFrame."""
        with self._data_lock:
            self._data_rows = []
        self._collecting = True

        if self.ble:
            self.ble.write("START\n")

        time.sleep(duration_s + 0.5)  # wait for acquisition to finish

        self._collecting = False

        with self._data_lock:
            rows = list(self._data_rows)

        if not rows:
            raise RuntimeError("No data received over BLE")

        df = pd.DataFrame(rows, columns=["time_ms", "Voff", "Von", "Vdiff"])
        df["time_s"] = df["time_ms"] / 1000.0
        return df

    def calibrate(self):
        try:
            df = self.acquire_data()
            V0 = df["Vdiff"].mean()
            os.makedirs(os.path.dirname(V0_PATH), exist_ok=True)
            with open(V0_PATH, "w") as f:
                f.write(f"{V0}\n")
            self.V0_text.set(f"Current V0: {V0:.3f} V\n")
        except Exception as e:
            messagebox.showerror("Calibration error", f"Calibration failed:\n{e}")

    def measure(self):
        try:
            if not os.path.exists(V0_PATH):
                raise RuntimeError("Calibration required")

            V0 = self.read_V0()
            df = self.acquire_data()
            df["turbidity_percent"] = (V0 - df["Vdiff"]) / V0 * 100.0

            mean_turb = df["turbidity_percent"].mean()
            std_turb  = df["turbidity_percent"].std()
            self.mean_turb_text.set(f"Mean turbidity: {mean_turb:.2f} %")
            self.std_turb_text.set(f"Std deviation: {std_turb:.2f} %\n")

            self.ax_turb.clear()
            self.ax_turb.plot(df["time_s"], df["turbidity_percent"])
            self.ax_turb.hlines([mean_turb], xmin=df["time_s"].min(), xmax=df["time_s"].max(),
                                color="red", linestyle="--", label=f"Mean: {mean_turb:.2f}%")
            self.ax_turb.set_xlabel("Time (s)")
            self.ax_turb.set_xlim(df["time_s"].min(), df["time_s"].max())
            self.ax_turb.set_ylabel("Relative turbidity (%)")
            self.ax_turb.set_title("Turbidity measurement")
            self.ax_turb.grid(True)
            self.ax_turb.legend()
            self.canvas.draw_idle()

            activity     = turb_to_vwf_activity(mean_turb)
            max_activity = turb_to_vwf_activity(mean_turb - std_turb)
            min_activity = turb_to_vwf_activity(mean_turb + std_turb)
            std_activity = (max_activity - min_activity) / 2
            self.activity_text.set(f"({activity:.2f} ± {std_activity:.2f}) %\n")

            x_vals = np.linspace(0, CONTROL_POINTS[:, 0].max() + 0.5, 100)
            y_vals = m * x_vals + b

            self.ax_cal.clear()
            self.ax_cal.plot(x_vals, y_vals, color="black", linestyle="--", label="Calibration Curve")
            self.ax_cal.scatter(CONTROL_POINTS[:, 0], CONTROL_POINTS[:, 1],
                                color="blue", label="Control Points")
            self.ax_cal.errorbar(mean_turb, activity, xerr=std_turb, yerr=std_activity,
                                 fmt="o", color="red", ecolor="red", elinewidth=2, capsize=5,
                                 label=f"Measured Point ({activity:.2f}% ± {std_activity:.2f}%)")
            self.ax_cal.set_xlabel("Relative turbidity (%)")
            self.ax_cal.set_xlim(0, CONTROL_POINTS[:, 0].max() + 0.5)
            self.ax_cal.set_ylabel("VWF Activity (%)")
            self.ax_cal.set_ylim(0, 200)
            self.ax_cal.set_title("VWF Activity vs Turbidity Calibration Curve")
            self.ax_cal.legend()
            self.ax_cal.grid(True)
            self.canvas.draw_idle()

        except Exception as e:
            messagebox.showerror("Measurement error", f"Measurement failed:\n{e}")

    def on_close(self):
        try:
            if self.ble:
                self.ble.write("STOP\n")
                time.sleep(0.2)
                self.ble.disconnect()
        except Exception:
            pass
