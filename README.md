# GBM8970-VWFlow

This repository contains the software used to run the graphical user interface (UI) that controls a custom **2-in-1 aggregometer and turbidimetry sensor**, designed to measure **von Willebrand Factor (VWF) activity**.

The UI can be launched either with the real hardware connected or in simulation mode for development and testing.

---

## Repository Structure

After cloning the repository, you should see the following main directories:

- `UI/` – User interface source code  
- `src/` – Core logic and hardware interfaces  
- `data/` – Data files generated or used by the application  

---

## Launching the UI

### Step 1 – Clone the repository
```bash
cd <path/to/repository>
git clone https://github.com/AntoineGuenette/GBM8970-VWFlow
cd GBM8970-VWFlow
```
Verify you're in the correct directory by checking for the required files:
```bash
ls
```
You should see the `UI`, `data` and `src` folders.

### Step 2 - Run the UI
To launch the UI with all hardware connected:
```bash
python UI/main.py
```

## Simulation modes
For development or testing without physical hardware, the UI can be launched in simulation mode.

### Simulate the stirrer only
```bash
python UI/main.py --simulate-stirrer
```
### Simulate the sensor only
```bash
python UI/main.py --simulate-sensor
```
### Simulate all hardware
```bash
python UI/main.py --simulate-stirrer --simulate-sensor
```
