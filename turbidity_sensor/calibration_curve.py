import numpy as np
import matplotlib.pyplot as plt

# Control points for the calibration curve
# Format : [x,y] = [turbidity (NTU), VWF activity (% or UI/dL)]
CONTROL_POINTS = np.array(
    [
        [5.5, 100], # TODO: replace the x value with the actual measured turbidity the PRP pool
        [7, 75],  # TODO: replace the x value with the actual measured turbidity for 75% VWF
                 # activity
        [11.2, 50],  # TODO: replace the x value with the actual measured turbidity for 50% VWF
                  # activity
        [13.5, 25]  # TODO: replace the x value with the actual measured turbidity for 25% VWF
                  # activity
    ]
)

# Fit a linear model to the control points (y = mx + b)
m, b = np.polyfit(x=CONTROL_POINTS[:, 0], y=CONTROL_POINTS[:, 1], deg=1)

def turbidity_to_vwf_activity(turbidity: float) -> float:
    """
    Convert turbidity to VWF activity using the calibration curve.

    Args:
        turbidity (float): The measured turbidity value.

    Returns:
        vwf_activity (float): The corresponding VWF activity.
    """
    vwf_activity = m * turbidity + b
    return vwf_activity

# Ask the user to give the measured turbidity value
turbidity = float(input("Enter the measured turbidity value: "))

# Convert the turbidity to VWF activity
vwf_activity = turbidity_to_vwf_activity(turbidity)

# Print the result
print(f"The VWF activity is: {vwf_activity:.2f} %")

###### DEBUGGING PLOTTING CODE ######

# Show the calibration curve with the measured point
x_vals = np.linspace(0, 15, 100)
y_vals = m * x_vals + b

plt.plot(
    x_vals, y_vals,
    color="black",
    linestyle="--",
    label="Calibration Curve"
)
plt.scatter(
    CONTROL_POINTS[:, 0], CONTROL_POINTS[:, 1],
    color="blue",
    label="Control Points"
)
plt.scatter(
    [turbidity], [vwf_activity],
    color="red",
    label=f"Measured Point ({vwf_activity:.2f}% VWF Activity)"
)

plt.title("VWF Activity vs Turbidity Calibration Curve")
plt.xlabel("Turbidity [NTU]")
plt.ylabel("VWF Activity [%]")
plt.legend()
plt.show()