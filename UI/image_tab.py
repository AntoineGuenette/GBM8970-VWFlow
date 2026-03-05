import os
import cv2
import tkinter as tk
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

from tkinter import filedialog
from skimage import measure, morphology
from scipy.spatial.distance import cdist
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
    
# =========================
# CONFIG
# =========================
CONTROL_POINTS = np.array(
    [ # (Number of platelets, VWF activity) pairs for the calibration curve
        (60, 100), # Temporary value
        (110, 75), # Temporary value
        (180, 50), # Temporary value
        (240, 25), # Temporary value
        (300, 0) # Temporary value
    ]
)

# =========================
# NUMBER OF PLATELETS -> VWF ACTIVITY CONVERSION
# =========================
m, b = np.polyfit(x=CONTROL_POINTS[:, 0], y=CONTROL_POINTS[:, 1], deg=1)

def platelets_to_vwf_activity(nb_platelets: float) -> float:
    return m * nb_platelets + b

# =========================
# UI
# =========================
class ImageUI:
    def __init__(self, parent):
        # Initialize tab UI
        self.root = parent

        # Status variables
        self.img_text = tk.StringVar(value="")
        self.bckgrd_img_text = tk.StringVar(value="")
        self.platelet_count_text = tk.StringVar(value="Platelet count: ---")
        self.activity_text = tk.StringVar(value="---\n")

        self.debug_mode = tk.BooleanVar(value=False)

        # Images
        self.im1 = np.zeros((100, 100))
        self.im2 = np.zeros((100, 100))
        self.im3 = np.zeros((100, 100))

        # Store selected paths
        self.selected_image_paths = []
        self.selected_background_path = None

        # Build the UI
        self._build_ui()

    # ================= UI =================
    def _build_ui(self):

        # Initialize left side bar
        left = tk.Frame(self.root)
        left.pack(side=tk.LEFT, padx=10, pady=10)

        # Image selection button
        tk.Button(left, text="Select images to count", width=15,
                  command=self.open_images).pack(pady=2)
        tk.Label(
            left,
            textvariable=self.img_text,
            font=("Helvetica", 10),
            wraplength=180,
            anchor="w"
        ).pack(pady=2)
        
        # Background selection button
        tk.Button(left, text="Select background image", width=15,
                  command=self.open_background_image).pack(pady=2)
        tk.Label(
            left,
            textvariable=self.bckgrd_img_text,
            font=("Helvetica", 10),
            wraplength=180,
            anchor="w"
        ).pack(pady=2)
        
        # Measurement buttons
        tk.Checkbutton(
            left,
            text="Debug mode",
            variable=self.debug_mode
        ).pack(pady=2)
        tk.Button(left, text="Count platelets", width=15,
                  command=self.run_count_platelets).pack(pady=2)
        tk.Label(left, textvariable=self.platelet_count_text,
                 font=("Helvetica", 12)).pack(pady=2)
        
        # Activity status
        tk.Label(left, text="VWF Activity",
                 font=("Helvetica", 16)).pack(pady=(20, 5))
        tk.Label(left, textvariable=self.activity_text,
                 font=("Helvetica", 12)).pack(pady=2)
        
        # Initialize right side plots
        self.fig = Figure(figsize=(6.5, 6.5), dpi=100)
        self.gs = GridSpec(2, 3, figure=self.fig)

        self.ax_im1 = self.fig.add_subplot(self.gs[0, 0])
        self.ax_im2 = self.fig.add_subplot(self.gs[0, 1])
        self.ax_im3 = self.fig.add_subplot(self.gs[0, 2])
        self.ax_cal = self.fig.add_subplot(self.gs[1, :])

        self.ax_im1.imshow(self.im1, cmap="gray", vmin=0, vmax=1)
        self.ax_im2.imshow(self.im2, cmap="gray", vmin=0, vmax=1)
        self.ax_im3.imshow(self.im3, cmap="gray", vmin=0, vmax=1)
        for ax in (self.ax_im1, self.ax_im2, self.ax_im3):
            ax.axis("off")

        self.ax_cal.set_title("Calibration curve")
        self.ax_cal.set_xlabel("Number of platelets")
        self.ax_cal.set_ylabel("VWF Activity (%)")
        self.ax_cal.grid(True)

        # Graph widget
        canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        canvas.get_tk_widget().pack(side=tk.RIGHT,
                                    fill=tk.BOTH, expand=True,
                                    padx=10, pady=10)
        self.canvas = canvas

    # ================= LOGIC =================
    def _shorten_path(self, path, max_parts=2):
        if not path:
            return ""

        path = os.path.normpath(path)
        parts = path.split(os.sep)

        if len(parts) <= max_parts + 1:
            return path

        return os.sep.join([parts[-(max_parts+1)], "...", parts[-1]])

    def open_images(self):
        paths = filedialog.askopenfilenames(
            title="Select the images to count",
            filetypes=(("All files", "*.*"),)
        )
        self.selected_image_paths = list(paths)
        shortened = [self._shorten_path(p) for p in paths]

        # Show paths
        display_text = "Selected images:\n" + "\n".join(shortened)
        self.img_text.set(display_text)

        # Show images
        self.im1 = cv2.imread(paths[0], cv2.IMREAD_GRAYSCALE)
        self.ax_im1.imshow(self.im1, cmap="gray")
        self.ax_im1.set_title("Image 1")

        self.im2 = cv2.imread(paths[1], cv2.IMREAD_GRAYSCALE)
        self.ax_im2.imshow(self.im2, cmap="gray")
        self.ax_im2.set_title("Image 2")
        
        self.im3 = cv2.imread(paths[2], cv2.IMREAD_GRAYSCALE)
        self.ax_im3.imshow(self.im3, cmap="gray")
        self.ax_im3.set_title("Image 3")

        for ax in (self.ax_im1, self.ax_im2, self.ax_im3):
            ax.axis("off")
    
    def open_background_image(self):
        path =  filedialog.askopenfilename(
            title="Select the background image",
            filetypes=(("All files", "*.*"),)
        )
        self.selected_background_path = path
        shortened = self._shorten_path(path)
        self.bckgrd_img_text.set(f"Selected background image:\n{shortened}")

    def run_count_platelets(self):
        """
        Wrapper called by the button.
        Uses stored paths to call count_platelets.
        Display results and updates count
        """
        if not self.selected_image_paths:
            print("No images selected.")
            return

        if not self.selected_background_path:
            print("No background image selected.")
            return

        counts = []
        overlays = []
        for file_path in self.selected_image_paths:
            labels_filtered = self.count_platelets(
                file_path=file_path,
                bkgrd_img_path=self.selected_background_path,
                debug=self.debug_mode.get()
            )
            counts.append(np.max(labels_filtered))
            overlays.append(labels_filtered)

        # Show mean platelet count
        mean_count = np.mean(counts)
        std_count = np.std(counts)
        self.platelet_count_text.set(f"Platelet count : {mean_count:.1f} ± {std_count:.1f} ")

        # Update images
        self.ax_im1.clear()
        self.ax_im1.imshow(self.im1, cmap="gray")
        self.ax_im1.imshow(overlays[0], cmap="nipy_spectral", alpha=0.5)
        self.ax_im1.set_title(f"Image 1 : {counts[0]} platelets")

        self.ax_im2.clear()
        self.ax_im2.imshow(self.im2, cmap="gray")
        self.ax_im2.imshow(overlays[1], cmap="nipy_spectral", alpha=0.5)
        self.ax_im2.set_title(f"Image 2 : {counts[1]} platelets")
        
        self.ax_im3.clear()
        self.ax_im3.imshow(self.im3, cmap="gray")
        self.ax_im3.imshow(overlays[2], cmap="nipy_spectral", alpha=0.5)
        self.ax_im3.set_title(f"Image 3 : {counts[2]} platelets")

        for ax in (self.ax_im1, self.ax_im2, self.ax_im3):
            ax.axis("off")

        self.canvas.draw_idle()

        # Show activity
        activity = platelets_to_vwf_activity(mean_count)
        max_activity = platelets_to_vwf_activity(mean_count - std_count)
        min_activity = platelets_to_vwf_activity(mean_count + std_count)
        std_activity = (max_activity - min_activity) / 2

        self.activity_text.set(f"({activity:.2f} ± {std_activity:.2f}) %\n")

        # Update calibration curve plot
        x_vals = np.linspace(0, 1.05 * CONTROL_POINTS[:, 0].max(), 100)
        y_vals = m * x_vals + b

        self.ax_cal.clear()
        self.ax_cal.plot(x_vals, y_vals, color="black", linestyle="--",
                            label="Calibration Curve")
        self.ax_cal.scatter(
            CONTROL_POINTS[:, 0], CONTROL_POINTS[:, 1],
            color="blue",
            label="Control Points"
        )
        self.ax_cal.errorbar(
            mean_count, activity,
            xerr=std_count,
            yerr=std_activity,
            fmt="o",
            color="red",
            ecolor="red",
            elinewidth=2,
            capsize=5,
            label=f"Measured Point ({activity:.2f}% ± {std_activity:.2f}%)"
        )
        self.ax_cal.set_xlabel("Number of platelets")
        self.ax_cal.set_ylabel("VWF Activity (%)")
        self.ax_cal.set_xlim(0, 1.05 * CONTROL_POINTS[:, 0].max())
        self.ax_cal.set_ylim(0, 200)
        self.ax_cal.set_title("Calibration Curve")
        self.ax_cal.legend()
        self.ax_cal.grid(True)
        self.canvas.draw_idle()

    def count_platelets(self, file_path: str, bkgrd_img_path: str, debug=False) -> np.array:
        # Define file paths
        file_dir = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        debug_file_path = os.path.join(file_dir, f"DEBUG_{file_name}")

        # Open images
        img = cv2.imread(str(file_path), cv2.IMREAD_GRAYSCALE)
        bkgrd = cv2.imread(bkgrd_img_path, cv2.IMREAD_GRAYSCALE)

        # Convert images to float32
        img = img.astype(np.float32)
        bkgrd = bkgrd.astype(np.float32)

        # Blur and normalize the background
        bkgrd_smooth = cv2.GaussianBlur(bkgrd, (51, 51), 0)
        epsilon = 1e-6
        bkgrd_mean = np.mean(bkgrd_smooth)
        bkgrd_norm = bkgrd_smooth / (bkgrd_mean + epsilon)

        # Correct the image by removing the background gray levels
        img_corrected = img / (bkgrd_norm + epsilon)
        img_corrected = img_corrected.astype(np.uint8)

        # Normalize the image histogram
        dimensions = img_corrected.shape
        number_of_pixels = dimensions[0] * dimensions[1]
        hist, _ = np.histogram(img_corrected, bins=256, range=(35, 255))
        normalized_cumulative_histogram = np.cumsum(hist) / number_of_pixels
        img_norm = 255 * normalized_cumulative_histogram[img_corrected]
        img_norm = img_norm.astype(np.uint8)

        # Binarize the image with OTSU thresholding
        _, binary = cv2.threshold(
            img_norm, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )
        bin_img = binary.astype(bool)

        # Morphological filtering (work on boolean image)
        filtered_bin_img = morphology.remove_small_objects(bin_img, max_size=15)
        filtered_bin_img = morphology.remove_small_holes(filtered_bin_img, max_size=150)

        # Label the regions
        labels_all = measure.label(filtered_bin_img, connectivity=2)
        regions_all = measure.regionprops(labels_all)

        # Filter the regions by their connectivity, their area and their circularity
        centroids = np.array([r.centroid for r in regions_all])
        diameters = np.array([r.equivalent_diameter_area for r in regions_all])
        D = cdist(centroids, centroids)
        np.fill_diagonal(D, np.inf)  # ignore self-distance
        distance_threshold = np.mean(diameters)
        isolated_mask = np.zeros_like(filtered_bin_img, dtype=bool)
        for i, r in enumerate(regions_all):
            if (
                np.min(D[i]) > distance_threshold
                and r.area <= 150
                and r.solidity > 0.9
            ):
                coords = r.coords
                isolated_mask[coords[:, 0], coords[:, 1]] = True

        labels_filtered = measure.label(isolated_mask, connectivity=2)
        regions_filtered = measure.regionprops(labels_filtered)

        if debug :
            plt.figure(figsize=(14, 10))

            plt.subplot(2, 4, 1)
            plt.imshow(img, cmap="gray")
            plt.title("Image originale (niveaux de gris)")
            plt.axis("off")

            plt.subplot(2, 4, 2)
            plt.imshow(img_corrected, cmap="gray")
            plt.title("Image corrigée")
            plt.axis("off")

            plt.subplot(2, 4, 3)
            plt.imshow(img_norm, cmap="gray")
            plt.title("Image normalisée")
            plt.axis("off")

            plt.subplot(2, 4, 4)
            plt.imshow(binary, cmap="gray")
            plt.title("Binarisation (OTSU)")
            plt.axis("off")

            plt.subplot(2, 4, 5)
            plt.imshow(filtered_bin_img, cmap="gray")
            plt.title("Filtrage morphologique")
            plt.axis("off")

            plt.subplot(2, 4, 6)
            plt.imshow(img, cmap="gray")
            plt.imshow(labels_all, cmap="nipy_spectral", alpha=0.5)
            plt.title(f"Régions détectées ({len(regions_all)})")
            plt.axis("off")

            plt.subplot(2, 4, 7)
            plt.imshow(isolated_mask, cmap="gray")
            plt.title("Retrait des agrégats")
            plt.axis("off")

            plt.subplot(2, 4, 8)
            plt.imshow(img, cmap="gray")
            plt.imshow(labels_filtered, cmap="nipy_spectral", alpha=0.5)
            plt.title(f"Plaquettes seules détectées ({len(regions_filtered)})")
            plt.axis("off")

            plt.savefig(debug_file_path, dpi=300)

        return labels_filtered

    def on_close(self):
        pass