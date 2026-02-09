import serial
import serial.tools.list_ports
import threading
import tkinter as tk
from tkinter import messagebox
from collections import deque
import time

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# =========================
# CONFIG
# =========================
BAUD = 9600
RPM_MIN = 1000
RPM_MAX = 7500

PLOT_WINDOW_SEC = 10        # seconds shown on plot
PLOT_REFRESH_MS = 100       # plot refresh rate

SIMULATION_MODE = True   # True = simulate the Arduino

# =========================
# AUTO-DETECT SERIAL PORT
# =========================
def find_arduino_port():
    ports = serial.tools.list_ports.comports()
    for p in ports:
        if ("usbmodem" in p.device.lower() or
            "usbserial" in p.device.lower() or
            "arduino" in p.description.lower()):
            return p.device
    return None

if SIMULATION_MODE:
    ser = None
    PORT = "SIMULATION (UI only)"
else:
    PORT = find_arduino_port()
    if PORT is None:
        messagebox.showerror(
            "Serial error",
            "No Arduino detected.\nPlug it in and retry."
        )
        raise SystemExit

    ser = serial.Serial(PORT, BAUD, timeout=1)

# =========================
# UI SETUP
# =========================
root = tk.Tk()
root.title("Motor Speed Controller")
root.geometry("700x500")
root.resizable(True, True)

# =========================
# VARIABLES
# =========================
target_var = tk.StringVar(value="Speed")
rpm_text = tk.StringVar(value="RPM: ---")
pwm_text = tk.StringVar(value="PWM: ---")
status_text = tk.StringVar(value=f"Connected to {PORT}")

# =========================
# DATA BUFFERS (for plot)
# =========================
time_buffer = deque(maxlen=1000)
rpm_buffer = deque(maxlen=1000)
start_time = time.time()

# =========================
# COMMAND FUNCTIONS
# =========================
def apply_target(event=None):
    if SIMULATION_MODE:
        return
    try:
        rpm = int(target_var.get())
        if rpm < RPM_MIN or rpm > RPM_MAX:
            raise ValueError
        ser.write(f"S {rpm}\n".encode())
    except ValueError:
        messagebox.showwarning(
            "Invalid input",
            f"Enter an integer between {RPM_MIN} and {RPM_MAX}"
        )

def start_motor():
    if SIMULATION_MODE:
        return
    ser.write(b"START\n")

def stop_motor():
    if SIMULATION_MODE:
        return
    ser.write(b"STOP\n")

# =========================
# UI LAYOUT (LEFT PANEL)
# =========================
left = tk.Frame(root)
left.pack(side=tk.LEFT, padx=10, pady=10)

tk.Label(left, text="Target RPM", font=("Helvetica", 12)).pack(pady=5)

entry = tk.Entry(
    left,
    textvariable=target_var,
    width=10,
    justify="center",
    font=("Helvetica", 16)
)
entry.pack()
entry.bind("<Return>", apply_target)

tk.Button(left, text="Apply", width=12, command=apply_target).pack(pady=5)
tk.Button(left, text="START", width=12, command=start_motor).pack(pady=2)
tk.Button(left, text="STOP", width=12, command=stop_motor).pack(pady=2)

tk.Label(left, textvariable=rpm_text, font=("Helvetica", 12)).pack(pady=10)
tk.Label(left, textvariable=pwm_text, font=("Helvetica", 12)).pack()

tk.Label(left, textvariable=status_text, font=("Helvetica", 9)).pack(pady=10)

# =========================
# PLOT SETUP (RIGHT PANEL)
# =========================
fig = Figure(figsize=(6.5, 6.5), dpi=100)
fig.patch.set_facecolor("#f0f0f0")   # background color

ax_full = fig.add_subplot(211)
ax_zoom = fig.add_subplot(212)

ax_full.set_facecolor("white")
ax_zoom.set_facecolor("white")

fig.subplots_adjust(
    left=0.12,
    right=0.98,
    top=0.95,
    bottom=0.1,
    hspace=0.4
)

# ---- FULL SCALE ----
ax_full.set_title("RPM vs Time (Full Scale)")
ax_full.set_ylabel("RPM")
ax_full.set_ylim(RPM_MIN, RPM_MAX)
ax_full.grid(True)

# ---- ZOOMED ----
ax_zoom.set_title("RPM vs Time (Zoomed)")
ax_zoom.set_xlabel("Time (s)")
ax_zoom.set_ylabel("RPM")
ax_zoom.grid(True)

line_full, = ax_full.plot([], [], lw=2)
line_zoom, = ax_zoom.plot([], [], lw=2)

canvas = FigureCanvasTkAgg(fig, master=root)
canvas.get_tk_widget().pack(
    side=tk.RIGHT,
    fill=tk.BOTH,
    expand=True,
    padx=10,
    pady=10
)

# =========================
# SERIAL READER THREAD
# =========================
def serial_reader():
    while True:
        try:
            line_in = ser.readline().decode(errors="ignore").strip()
            if line_in:
                # Expected: Setpoint,RPM,PWM
                parts = line_in.split(",")
                if len(parts) == 3:
                    _, rpm, pwm = parts

                    now = time.time() - start_time
                    rpm_val = float(rpm)

                    time_buffer.append(now)
                    rpm_buffer.append(rpm_val)

                    rpm_text.set(f"RPM: {rpm}")
                    pwm_text.set(f"PWM: {pwm}")
        except:
            pass

if not SIMULATION_MODE:
    threading.Thread(target=serial_reader, daemon=True).start()

def on_close():
    if not SIMULATION_MODE:
        try:
            ser.write(b"STOP\n")
            ser.flush()
            time.sleep(0.1)
        except:
            pass

        try:
            ser.close()
        except:
            pass

    root.destroy()

# =========================
# PLOT UPDATE FUNCTION
# =========================
def update_plot():
    if time_buffer:
        t0 = time_buffer[-1] - PLOT_WINDOW_SEC
        times = [t for t in time_buffer if t >= t0]
        rpms = list(rpm_buffer)[-len(times):]

        # ---- Full plot ----
        line_full.set_data(times, rpms)
        ax_full.set_xlim(max(0, t0), time_buffer[-1])

        # ---- Zoomed plot ----
        line_zoom.set_data(times, rpms)
        ax_zoom.set_xlim(max(0, t0), time_buffer[-1])

        ZOOM_RANGE = 200  # RPM zoom window
        center = rpms[-1]
        ax_zoom.set_ylim(center - ZOOM_RANGE, center + ZOOM_RANGE)

    canvas.draw_idle()
    root.after(PLOT_REFRESH_MS, update_plot)

update_plot()
root.protocol("WM_DELETE_WINDOW", on_close)

# =========================
# RUN UI
# =========================
root.mainloop()