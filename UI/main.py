import tkinter as tk
from tkinter import ttk

from stirrer_tab import StirrerUI
from sensor_tab import SensorUI

def main():
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
    stirrer_ui = StirrerUI(stirrer_frame)

    # Create sensor tab
    sensor_frame = ttk.Frame(notebook)
    notebook.add(sensor_frame, text="Sensor")
    sensor_ui = SensorUI(sensor_frame)

    # Handle window close event
    def on_close():
        stirrer_ui.on_close()
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", on_close)

    # Start the main event loop
    root.mainloop()

if __name__ == "__main__":
    main()
