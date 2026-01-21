import numpy as np
import matplotlib.pyplot as plt

# Control points for the calibration curve
# Format : [x,y] = [absorbance (AU), VWF activity (% or UI/dL)]
CONTROL_POINTS = np.array(
    [
        [0.0, 0.0], # when the mesured absorbance in the agitated sample is the same as in the
                    # non-agitated sample, VWF activity is 0%
        [0.2, 19.7], # TODO: replace the x value with the actual measured absorbance for 19.7% VWF
                     # activity
        [0.8, 76.5]  # TODO: replace the x value with the actual measured absorbance for 76.5% VWF
                     # activity
    ]
)

# Fit a linear model to the control points (y = mx + b)
m, b = np.polyfit(x=CONTROL_POINTS[:, 0], y=CONTROL_POINTS[:, 1], deg=1)

def absorbance_to_vwf_activity(non_agitated_absorbance: float, agitated_absorbance: float) -> float:
    """
    Convert absorbance to VWF activity using the calibration curve.

    Args:
        non_agitated_absorbance (float): The measured absorbance value for the non-agitated sample.
        agitated_absorbance (float): The measured absorbance value for the agitated sample.

    Returns:
        vwf_activity (float): The corresponding VWF activity.
    """
    absorbance = agitated_absorbance - non_agitated_absorbance
    vwf_activity = m * absorbance + b
    return vwf_activity

# Ask the user to give the measured absorbance value
non_agitated_absorbance = float(input("Enter the measured absorbance value for the non-agitated sample: "))
agitated_absorbance = float(input("Enter the measured absorbance value for the agitated sample: "))

# Convert the absorbance to VWF activity
vwf_activity = absorbance_to_vwf_activity(non_agitated_absorbance, agitated_absorbance)

# Print the result
print(f"The VWF activity is: {vwf_activity:.2f} %")

###### DEBUGGING PLOTTING CODE ######

# Show the calibration curve with the measured point
x_vals = np.linspace(0, 2, 100)
y_vals = m * x_vals + b

plt.plot(
    x_vals, y_vals,
    color="black",
    linestyle="--",
    label="Calibration Curve")
plt.scatter(
    [0], [0],
    color="red",
    label="Zero Point")
plt.scatter(
    [0.2], [19.7], # TODO: replace with actual absorbance value
    color="blue",
    label="19.7% VWF Activity"
) 
plt.scatter(
    [0.8], [76.5], # TODO: replace with actual absorbance value
    color="green",
    label="76.5% VWF Activity"
)
plt.scatter(
    [agitated_absorbance - non_agitated_absorbance], [vwf_activity],
    color="orange",
    label=f"Measured Point ({vwf_activity:.2f}% VWF Activity)"
)

plt.title("VWF Activity vs Absorbance")
plt.xlabel("Absorbance [AU]")
plt.ylabel("VWF Activity [%]")
plt.legend()
plt.show()