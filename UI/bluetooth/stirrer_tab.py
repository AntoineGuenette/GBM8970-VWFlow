import asyncio
import threading
import tkinter as tk
import time
import matplotlib
matplotlib.use("TkAgg")

from tkinter import messagebox
from collections import deque
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from bleak import BleakClient

# =========================
# CONFIG
# =========================
RPM_MIN = 1000
RPM_MAX = 7500
SHEAR_MIN = 500
SHEAR_MAX = 3800

SIMULATION_POINTS = [
    (1000, 451.5),
    (3000, 1464.5),
    (7500, 3869.5),
]

PLOT_WINDOW_SEC = 10
PLOT_REFRESH_MS = 100

SIMULATION_MODE = False

# =========================
# RPM <-> SHEAR CONVERSIONS
# =========================
def linear_coeff(p1, p2):
    (x1, y1), (x2, y2) = p1, p2
    a = (y2 - y1) / (x2 - x1)
    b = y1 - a * x1
    return a, b

LINEAR_SEGMENTS = []
for i in range(len(SIMULATION_POINTS) - 1):
    a, b = linear_coeff(SIMULATION_POINTS[i], SIMULATION_POINTS[i + 1])
    LINEAR_SEGMENTS.append((SIMULATION_POINTS[i][0],
                            SIMULATION_POINTS[i + 1][0], a, b))

def rpm_to_shear(rpm):
    for rpm_min, rpm_max, a, b in LINEAR_SEGMENTS:
        if rpm <= rpm_max:
            return a * rpm + b
    _, _, a, b = LINEAR_SEGMENTS[-1]
    return a * rpm + b

def shear_to_rpm(gamma):
    for rpm_min, rpm_max, a, b in LINEAR_SEGMENTS:
        gamma_max = a * rpm_max + b
        if gamma <= gamma_max:
            return (gamma - b) / a
    _, _, a, b = LINEAR_SEGMENTS[-1]
    return (gamma - b) / a


# =========================
# BLE MANAGER
# Runs an asyncio event loop in a background thread.
# All BLE calls are scheduled into that loop from the tkinter thread.
# =========================
class BLEManager:
    def __init__(self, address, rx_uuid, tx_uuid, on_line_received):
        self.address = address
        self.rx_uuid = rx_uuid
        self.tx_uuid = tx_uuid
        self.on_line_received = on_line_received  # callback(str)

        self._loop = asyncio.new_event_loop()
        self._client: BleakClient = None
        self._connected = False
        self._rx_buf = ""  # accumulate partial lines

        # Start background event loop thread
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        # Connect asynchronously
        asyncio.run_coroutine_threadsafe(self._connect(), self._loop)

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def _connect(self):
        try:
            self._client = BleakClient(self.address)
            await self._client.connect()
            self._connected = True
            print(f"BLE connected to {self.address}")

            # Subscribe to TX notifications (Arduino → Python)
            await self._client.start_notify(self.tx_uuid, self._on_notify)
        except Exception as e:
            print(f"BLE connection error: {e}")
            self._connected = False

    def _on_notify(self, sender, data: bytearray):
        """Called on the asyncio thread whenever Arduino sends data."""
        text = data.decode(errors="ignore")
        self._rx_buf += text
        # Split on newlines; dispatch complete lines to the callback
        while "\n" in self._rx_buf:
            line, self._rx_buf = self._rx_buf.split("\n", 1)
            line = line.strip()
            if line:
                self.on_line_received(line)

    def write(self, text: str):
        """Thread-safe: schedule a BLE write from any thread."""
        if not self._connected:
            return
        asyncio.run_coroutine_threadsafe(self._write(text), self._loop)

    async def _write(self, text: str):
        try:
            await self._client.write_gatt_char(
                self.rx_uuid,
                text.encode(),
                response=False,
            )
        except Exception as e:
            print(f"BLE write error: {e}")

    def disconnect(self):
        """Fire-and-forget disconnect (kept for compatibility)."""
        if self._connected and self._client:
            asyncio.run_coroutine_threadsafe(
                self._client.disconnect(), self._loop
            )

    def disconnect_and_wait(self, timeout: float = 3.0):
        """
        Fully disconnect from the BLE device and block until done.
        This ensures the Arduino releases its BLE slot so another
        computer can connect immediately after.
        """
        if self._connected and self._client:
            future = asyncio.run_coroutine_threadsafe(
                self._client.disconnect(), self._loop
            )
            try:
                future.result(timeout=timeout)
                print("BLE disconnected cleanly.")
            except Exception as e:
                print(f"BLE disconnect error: {e}")
        # Stop the background event loop so the thread exits cleanly
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=timeout)
        print("BLE background thread stopped.")


# =========================
# UI
# =========================
class StirrerUI:
    def __init__(self, parent, ble_address=None, rx_uuid=None, tx_uuid=None):
        self.root = parent

        # Data buffers
        self.start_time = time.time()
        self.time_buffer = deque(maxlen=1000)
        self.rpm_buffer = deque(maxlen=1000)

        # Control state
        self.target_var = tk.IntVar(value=RPM_MIN)
        self.control_mode = tk.StringVar(value="RPM")
        self.previous_mode = "RPM"
        self.last_rpm_value = RPM_MIN
        self.last_shear_value = SHEAR_MIN

        # Status variables
        self.shear_text = tk.StringVar(value="Mean shear rate: ---")
        self.rpm_text = tk.StringVar(value="Rotation speed: ---")
        self.pwm_text = tk.StringVar(value="PWM: ---\n")
        self.runtime_var = tk.IntVar(value=0)
        self.time_left_text = tk.StringVar(value="Time left: ∞")

        # BLE connection
        if not SIMULATION_MODE:
            self.ble = BLEManager(
                address=ble_address,
                rx_uuid=rx_uuid,
                tx_uuid=tx_uuid,
                on_line_received=self._threadsafe_on_line_received,
            )
            self.status_text = tk.StringVar(value=f"Connecting BLE to {ble_address}...")
            # Enable streaming once connected (poll until connected)
            self.root.after(2000, self._init_stream)
        else:
            self.ble = None
            self.status_text = tk.StringVar(value="SIMULATION (UI only)")

        self._build_ui()
        self.update_slider_mode()
        self.update_plot()

    def _init_stream(self):
        """Send STREAM ON after BLE has had time to connect."""
        self._ble_write("STREAM ON\n")
        if self.ble and self.ble._connected:
            self.status_text.set(f"BLE connected to {self.ble.address}")
        else:
            self.status_text.set("BLE connecting… (retrying)")
            self.root.after(1000, self._init_stream)

    # ================= BLE HELPERS =================
    def _ble_write(self, text: str):
        if not SIMULATION_MODE and self.ble:
            self.ble.write(text)

    def _threadsafe_on_line_received(self, line: str):
        """Ensure BLE callbacks are executed in the Tkinter main thread."""
        self.root.after(0, self._on_line_received, line)

    def _on_line_received(self, line: str):
        """
        Called from the BLE background thread — only update tkinter
        variables (thread-safe); never call tkinter widgets directly.
        """
        try:
            # ===== PID OUTPUT =====
            if line.startswith("PID"):
                print("\n=== NEW PID GAINS ===")
                print(line)
                print("=====================\n")
                return
            if line.startswith("TIME_LEFT"):
                _, v = line.split(",")
                if v == "INF":
                    self.time_left_text.set("Time left: ∞")
                else:
                    s = int(v) // 1000
                    self.time_left_text.set(f"Time left: {s//60:02d}:{s%60:02d}")
                return

            if line == "b":
                return  # heartbeat, ignore

            parts = line.split(",")
            if len(parts) == 3:
                _, rpm, pwm = parts
                rpm = float(rpm.replace(",", "."))
                t = time.time() - self.start_time
                self.time_buffer.append(t)
                self.rpm_buffer.append(rpm)
                self.rpm_text.set(f"Rotation speed: {rpm:.0f} RPM")
                self.shear_text.set(f"Mean shear rate: {rpm_to_shear(rpm):.1f} s⁻¹")
                self.pwm_text.set(f"PWM: {pwm}\n")
        except Exception:
            pass

    # ================= UI =================
    def _build_ui(self):
        left = tk.Frame(self.root)
        left.pack(side=tk.LEFT, padx=10, pady=10)

        tk.Label(left, text="Control Mode",
                 font=("Helvetica", 16)).pack(pady=5)
        tk.Radiobutton(left, text="Rotation speed (RPM)",
                       variable=self.control_mode, value="RPM",
                       command=self.update_slider_mode).pack(anchor="w")
        tk.Radiobutton(left, text="Mean shear rate (s⁻¹)",
                       variable=self.control_mode, value="SHEAR",
                       command=self.update_slider_mode).pack(anchor="w")
        self.rpm_slider = tk.Scale(left, orient=tk.HORIZONTAL,
                                   length=220,
                                   variable=self.target_var)
        self.rpm_slider.pack(pady=10)

        tk.Button(left, text="Apply Speed/Shear", width=12,
                  command=self.apply_target).pack(pady=2)
        tk.Button(left, text="START", width=12,
                  command=self.start_motor).pack(pady=2)
        tk.Button(left, text="STOP", width=12,
                  command=self.stop_motor).pack(pady=2)

        tk.Label(left, text="Run time (seconds)",
                 font=("Helvetica", 12)).pack(pady=(10, 2))
        tk.Label(left, text="0 = run forever",
                 font=("Helvetica", 9)).pack()
        tk.Entry(left, textvariable=self.runtime_var,
                 width=10, justify="center").pack()
        tk.Button(left, text="Apply Time", width=12,
                  command=self.apply_runtime).pack(pady=5)
        tk.Label(left, textvariable=self.time_left_text,
                 font=("Helvetica", 12, "bold")).pack(pady=5)

        tk.Label(left, textvariable=self.rpm_text,
                 font=("Helvetica", 12)).pack(pady=5)
        tk.Label(left, textvariable=self.shear_text,
                 font=("Helvetica", 12)).pack()
        tk.Label(left, textvariable=self.pwm_text,
                 font=("Helvetica", 12)).pack()
        tk.Label(left, textvariable=self.status_text,
                 font=("Helvetica", 9)).pack(pady=10)

        self.fig = Figure(figsize=(6.5, 6.5), dpi=100)
        self.ax_full = self.fig.add_subplot(211)
        self.ax_zoom = self.fig.add_subplot(212)
        self.fig.subplots_adjust(hspace=0.35)

        self.ax_full.set_title("RPM vs Time (Full Scale)")
        self.ax_full.set_xlabel("Time (s)")
        self.ax_full.set_ylabel("RPM")
        self.ax_full.set_ylim(RPM_MIN, RPM_MAX)
        self.ax_full.grid(True)

        self.ax_zoom.set_title("RPM vs Time (Zoomed)")
        self.ax_zoom.set_xlabel("Time (s)")
        self.ax_zoom.set_ylabel("RPM")
        self.ax_zoom.grid(True)

        self.line_full, = self.ax_full.plot([], [], lw=2)
        self.line_zoom, = self.ax_zoom.plot([], [], lw=2)

        canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        canvas.get_tk_widget().pack(side=tk.RIGHT,
                                    fill=tk.BOTH, expand=True,
                                    padx=10, pady=10)
        self.canvas = canvas

    # ================= LOGIC =================
    def update_slider_mode(self):
        if self.previous_mode == "RPM":
            self.last_rpm_value = self.target_var.get()
            self.last_shear_value = rpm_to_shear(self.last_rpm_value)
        else:
            self.last_shear_value = self.target_var.get()
            self.last_rpm_value = shear_to_rpm(self.last_shear_value)

        if self.control_mode.get() == "RPM":
            self.rpm_slider.config(from_=RPM_MIN, to=RPM_MAX,
                                   resolution=100,
                                   tickinterval=1500,
                                   label="Rotation speed (RPM)")
            self.target_var.set(int(self.last_rpm_value))
        else:
            self.rpm_slider.config(from_=SHEAR_MIN, to=SHEAR_MAX,
                                   resolution=50,
                                   tickinterval=750,
                                   label="Mean shear rate (s⁻¹)")
            self.target_var.set(int(self.last_shear_value))

        self.previous_mode = self.control_mode.get()

    def apply_target(self):
        if SIMULATION_MODE:
            return
        if self.control_mode.get() == "RPM":
            rpm = int(self.target_var.get())
        else:
            rpm = int(shear_to_rpm(self.target_var.get()))
        rpm = max(RPM_MIN, min(RPM_MAX, rpm))
        self._ble_write(f"S {rpm}\n")

    def start_motor(self):
        self._ble_write("STREAM ON\n")
        self._ble_write("START\n")

    def stop_motor(self):
        self._ble_write("STOP\n")

    def apply_runtime(self):
        self._ble_write(f"T {self.runtime_var.get()}\n")

    def update_plot(self):
        if self.time_buffer:
            t0 = self.time_buffer[-1] - PLOT_WINDOW_SEC
            times = [t for t in self.time_buffer if t >= t0]
            rpms = list(self.rpm_buffer)[-len(times):]

            self.line_full.set_data(times, rpms)
            self.line_zoom.set_data(times, rpms)

            self.ax_full.set_xlim(max(0, t0), self.time_buffer[-1])
            self.ax_zoom.set_xlim(max(0, t0), self.time_buffer[-1])

            if rpms:
                c = rpms[-1]
                self.ax_zoom.set_ylim(c - 200, c + 200)

        self.canvas.draw_idle()
        self.root.after(PLOT_REFRESH_MS, self.update_plot)

    def on_close(self):
        try:
            self._ble_write("STREAM OFF\n")
            self._ble_write("STOP\n")
            time.sleep(0.5)  # give BLE writes time to flush
            if self.ble:
                self.ble.disconnect_and_wait()
        except Exception as e:
            print(f"on_close error: {e}")
        # NOTE: do NOT call self.root.destroy() here — main.py handles it
