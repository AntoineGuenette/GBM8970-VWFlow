# GBM8970-VWFlow

This repository contains the software used to run the graphical user interface (UI) that controls a custom 2-in-1
aggregometer and turbidimetry sensor, designed to measure von Willebrand Factor (VWF) activity.

The UI can be launched either with the real hardware connected or in simulation mode for development and testing.

---

## Requirements for the installation

### Git
Check that git is installed:
```bash
git --version
```
If it is not installed, please follow the official installation instructions for your operating system:
https://git-scm.com/downloads

### Miniconda
Check that Miniconda is installed:
```bash
conda --version
```
If it is not installed, please follow the official installation instructions for your operating system:
https://www.anaconda.com/docs/getting-started/miniconda/install

---

## Installation steps

### Step 1 – Clone the repository
Open a terminal (Command Prompt, PowerShell, or shell) and navigate to the directory where you want to clone the repository.
```bash
cd <path/to/the/repository>
```
Clone the repository:
```bash
git clone https://github.com/AntoineGuenette/GBM8970-VWFlow
cd GBM8970-VWFlow
```
Verify you're in the correct directory by checking for the required files:
```bash
ls
```
You should see the `UI`, `data` and `src` folders.

### Step 2 - Setup a Conda environment
Create a dedicated conda environment named **vwflow**:
```bash
conda create -n vwflow python=3.12.12
```
Activate the environment:
```bash
conda activate vwflow
```
Install the required Python packages:
```bash
pip install -r requirements.txt
```

---

## UI Versions

The repository contains two versions of the graphical interface depending on how the hardware communicates with the computer.

### Serial UI (USB)
The serial version communicates with the Arduinos through USB serial ports.

Launch the UI:
```bash
python -m UI.serial.main
```

Simulation mode (no hardware required):
```bash
python -m UI.serial.main --simulate-device
```

### Bluetooth UI (BLE)
The Bluetooth version communicates with the Arduino using Bluetooth Low Energy (BLE).

Launch the UI:
```bash
python -m UI.bluetooth.main
```

Simulation mode (no hardware required):
```bash
python -m UI.bluetooth.main --simulate-device
```
