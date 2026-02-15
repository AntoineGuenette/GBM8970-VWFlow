import serial
import serial.tools.list_ports
import threading
import tkinter as tk
import time
import matplotlib
matplotlib.use("TkAgg")

from tkinter import messagebox
from collections import deque
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# =========================
# CONFIG
# =========================
BAUD = 9600
RPM_MIN = 1000
RPM_MAX = 7500
SHEAR_MIN = 500     # Real value : 451.5
SHEAR_MAX = 3800    # Real value : 3869.5

SIMULATION_POINTS = [
    (1000, 451.5),
    (3000, 1464.5),
    (7500, 3869.5),
]

PLOT_WINDOW_SEC = 10
PLOT_REFRESH_MS = 100

SIMULATION_MODE = True # True = simulate the Arduino

# =========================
# SERIAL
# =========================
def find_arduino_port():
    for p in serial.tools.list_ports.comports():
        if ("usbmodem" in p.device.lower()
            or "usbserial" in p.device.lower()
            or "arduino" in p.description.lower()):
            return p.device
    return None

# =========================
# CONVERSION RPM <-> SHEAR
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
# UI
# =========================
class StirrerUI:
    def __init__(self, root):
        # Initialize UI
        self.root = root
        root.title("Magnetic Stirrer Controller")
        root.geometry("1200x800")
        root.resizable(True, True)

        # Initialize data buffers and state
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

        # Initialize serial connection
        if SIMULATION_MODE:
            self.ser = None
            self.port = "SIMULATION (UI only)"
        else:
            self.port = find_arduino_port()
            if self.port is None:
                messagebox.showerror("Serial error", "No Arduino detected.")
                raise SystemExit
            self.ser = serial.Serial(self.port, BAUD, timeout=1)
        self.status_text = tk.StringVar(value=f"Connected to {self.port}")

        # Build the UI
        self._build_ui()
        self.update_slider_mode()
        self.update_plot()

        # Start serial reader thread
        if not SIMULATION_MODE:
            threading.Thread(target=self.serial_reader, daemon=True).start()

        # Handle window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ================= UI =================
    def _build_ui(self):
        # Initialize left side bar
        left = tk.Frame(self.root)
        left.pack(side=tk.LEFT, padx=10, pady=10)

        # Rotation speed control
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

        # Action buttons
        tk.Button(left, text="Apply", width=12,
                  command=self.apply_target).pack(pady=2)
        tk.Button(left, text="START", width=12,
                  command=self.start_motor).pack(pady=2)
        tk.Button(left, text="STOP", width=12,
                  command=self.stop_motor).pack(pady=2)

        # Runtime control
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

        # Status display
        tk.Label(left, textvariable=self.rpm_text,
                 font=("Helvetica", 12)).pack(pady=5)
        tk.Label(left, textvariable=self.shear_text,
                 font=("Helvetica", 12)).pack()
        tk.Label(left, textvariable=self.pwm_text,
                 font=("Helvetica", 12)).pack()
        
        # Connection status
        tk.Label(left, textvariable=self.status_text,
                 font=("Helvetica", 9)).pack(pady=10)

        # Initialize right side plots
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

        # Graph widget
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
        self.ser.write(f"S {rpm}\n".encode())

    def start_motor(self):
        if not SIMULATION_MODE:
            self.ser.write(b"START\n")

    def stop_motor(self):
        if not SIMULATION_MODE:
            self.ser.write(b"STOP\n")

    def apply_runtime(self):
        if not SIMULATION_MODE:
            self.ser.write(f"T {self.runtime_var.get()}\n".encode())

    def serial_reader(self):
        while True:
            try:
                line = self.ser.readline().decode(errors="ignore").strip()
                if not line:
                    continue

                if line.startswith("TIME_LEFT"):
                    _, v = line.split(",")
                    if v == "INF":
                        self.time_left_text.set("Time left: ∞")
                    else:
                        s = int(v) // 1000
                        self.time_left_text.set(f"Time left: {s//60:02d}:{s%60:02d}")
                    continue

                _, rpm, pwm = line.split(",")
                rpm = float(rpm)
                t = time.time() - self.start_time

                self.time_buffer.append(t)
                self.rpm_buffer.append(rpm)

                self.rpm_text.set(f"Rotation speed: {rpm:.0f} RPM")
                self.shear_text.set(f"Mean shear rate: {rpm_to_shear(rpm):.1f} s⁻¹")
                self.pwm_text.set(f"PWM: {pwm}\n")

            except:
                pass

    def update_plot(self):
        if self.time_buffer:
            t0 = self.time_buffer[-1] - PLOT_WINDOW_SEC
            times = [t for t in self.time_buffer if t >= t0]
            rpms = list(self.rpm_buffer)[-len(times):]

            self.line_full.set_data(times, rpms)
            self.line_zoom.set_data(times, rpms)

            self.ax_full.set_xlim(max(0, t0), self.time_buffer[-1])
            self.ax_zoom.set_xlim(max(0, t0), self.time_buffer[-1])

            c = rpms[-1]
            self.ax_zoom.set_ylim(c - 200, c + 200)

        self.canvas.draw_idle()
        self.root.after(PLOT_REFRESH_MS, self.update_plot)

    def on_close(self):
        if not SIMULATION_MODE:
            try:
                self.ser.write(b"STOP\n")
                self.ser.close()
            except:
                pass
        self.root.destroy()


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    root = tk.Tk()
    app = StirrerUI(root)
    root.mainloop()