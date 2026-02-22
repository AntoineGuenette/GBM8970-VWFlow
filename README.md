# GBM8970-VWFlow

This repository contains the software used to run the graphical user interface (UI) that controls a custom 2-in-1 aggregometer and turbidimetry sensor, designed to measure von Willebrand Factor (VWF) activity.

The UI can be launched either with the real hardware connected or in simulation mode for development and testing.

---

## Requirements for the installation

### Git
You will need to be able to use **git** from the command line.

Check that git is installed:
```bash
git --version
```

On macOS, if git is not installed, you will be prompted to install the developer tools. Please install them if prompted.

### Pip
You will need to be able to use **pip** from the command line.

Check that pip is available:
```bash
pip --version
```

### Miniconda (recommended)
Miniconda is used as the main Python package and environment manager.

Download and install Miniconda for your operating system:
https://www.anaconda.com/docs/getting-started/miniconda/install

After installation, verify that conda is available:
```bash
conda --version
```

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

### Step 3 - Run the UI
To launch the UI with all hardware connected:
```bash
python UI/main.py
```

---

## Simulation Modes

For development or testing without physical hardware, the UI can be launched in simulation mode.

### Simulate the stirrer
When only the sensor is connected, run :
```bash
python UI/main.py --simulate-stirrer
```

### Simulate the sensor
When only the stirrer is connected, run :
```bash
python UI/main.py --simulate-sensor
```

### Simulate all hardware
When no hardware is connected, run :
```bash
python UI/main.py --simulate-stirrer --simulate-sensor
```
