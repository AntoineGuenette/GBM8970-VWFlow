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
        (50, 100), # Temporary value
        (36, 75), # Temporary value
        (22, 50), # Temporary value
        (8, 25), # Temporary value
        (0, 0)
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
        self.stat_img_text = tk.StringVar(value="")
        self.act_img_text = tk.StringVar(value="")
        self.bckgrd_img_text = tk.StringVar(value="")
        self.platelet_count_text = tk.StringVar(value="Platelet count: ---")
        self.activity_text = tk.StringVar(value="---\n")

        self.debug_mode = tk.BooleanVar(value=False)
        self.min_val_var = tk.DoubleVar(value=15)

        # Images
        self.im1 = np.zeros((100, 100))
        self.im2 = np.zeros((100, 100))
        self.im3 = np.zeros((100, 100))
        self.im4 = np.zeros((100, 100))
        self.im5 = np.zeros((100, 100))
        self.im6 = np.zeros((100, 100))

        # Store selected paths
        self.selected_stat_image_paths = []
        self.selected_act_image_paths = []
        self.selected_background_path = None

        # Build the UI
        self._build_ui()

    # ================= UI =================
    def _build_ui(self):

        # Initialize left side bar
        left = tk.Frame(self.root)
        left.pack(side=tk.LEFT, padx=10, pady=10)

        # Static image selection button
        tk.Button(left, text="Select non activated\nplatelet images", width=15,
                  command=self.open_stat_images).pack(pady=2)
        tk.Label(
            left,
            textvariable=self.stat_img_text,
            font=("Helvetica", 10),
            wraplength=180,
            anchor="w"
        ).pack(pady=2)

        # Activated image selection button
        tk.Button(left, text="Select activated\nplatelet images", width=15,
                  command=self.open_act_images).pack(pady=2)
        tk.Label(
            left,
            textvariable=self.act_img_text,
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
        
        # Min value slider
        tk.Label(left, text="Histogram min value").pack(pady=(10,2))
        tk.Scale(
            left,
            from_=0,
            to=50,
            orient=tk.HORIZONTAL,
            resolution=1,
            variable=self.min_val_var,
            command=lambda _ : self.update_histogram_preview(),
            length=150
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
                 font=("Helvetica", 16)).pack(pady=2)
        
        # Initialize right side plots
        self.fig = Figure(figsize=(6.5, 6.5), dpi=100)
        self.gs = GridSpec(3, 3, figure=self.fig)

        self.ax_im1 = self.fig.add_subplot(self.gs[0, 0])
        self.ax_im2 = self.fig.add_subplot(self.gs[0, 1])
        self.ax_im3 = self.fig.add_subplot(self.gs[0, 2])
        self.ax_im4 = self.fig.add_subplot(self.gs[1, 0])
        self.ax_im5 = self.fig.add_subplot(self.gs[1, 1])
        self.ax_im6 = self.fig.add_subplot(self.gs[1, 2])
        self.ax_cal = self.fig.add_subplot(self.gs[2, :])

        self.ax_im1.imshow(self.im1, cmap="gray", vmin=0, vmax=1)
        self.ax_im2.imshow(self.im2, cmap="gray", vmin=0, vmax=1)
        self.ax_im3.imshow(self.im3, cmap="gray", vmin=0, vmax=1)
        self.ax_im4.imshow(self.im4, cmap="gray", vmin=0, vmax=1)
        self.ax_im5.imshow(self.im5, cmap="gray", vmin=0, vmax=1)
        self.ax_im6.imshow(self.im6, cmap="gray", vmin=0, vmax=1)
        for ax in (self.ax_im1, self.ax_im2, self.ax_im3,
                   self.ax_im4, self.ax_im5, self.ax_im6):
            ax.axis("off")

        self.ax_cal.set_title("Calibration curve")
        self.ax_cal.set_xlabel("Platelet loss (%)")
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

    def open_stat_images(self):
        paths = filedialog.askopenfilenames(
            title="Select the static images to count",
            filetypes=(("All files", "*.*"),)
        )
        self.selected_stat_image_paths = list(paths)
        shortened = [self._shorten_path(p) for p in paths]

        # Show paths
        display_text = "Selected images:\n" + "\n".join(shortened)
        self.stat_img_text.set(display_text)

        # Update images
        axes_images = [
            (self.ax_im1, "Non activated platelets (1)", "im1", paths[0]),
            (self.ax_im2, "Non activated platelets (2)", "im2", paths[1]),
            (self.ax_im3, "Non activated platelets (3)", "im3", paths[2]),
        ]

        for ax, title, attr, path in axes_images:
            img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            setattr(self, attr, img)

            ax.clear()
            ax.imshow(img, cmap="gray")
            ax.set_title(title)
            ax.axis("off")

        self.canvas.draw_idle()
    
    def open_act_images(self):
        paths = filedialog.askopenfilenames(
            title="Select the activated images to count",
            filetypes=(("All files", "*.*"),)
        )
        self.selected_act_image_paths = list(paths)
        shortened = [self._shorten_path(p) for p in paths]

        # Show paths
        display_text = "Selected images:\n" + "\n".join(shortened)
        self.act_img_text.set(display_text)

        # Update images
        axes_images = [
            (self.ax_im4, "Activated platelets (1)", "im4", paths[0]),
            (self.ax_im5, "Activated platelets (2)", "im5", paths[1]),
            (self.ax_im6, "Activated platelets (3)", "im6", paths[2]),
        ]

        for ax, title, attr, path in axes_images:
            img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            setattr(self, attr, img)

            ax.clear()
            ax.imshow(img, cmap="gray")
            ax.set_title(title)
            ax.axis("off")

        self.canvas.draw_idle()
    
    def open_background_image(self):
        path =  filedialog.askopenfilename(
            title="Select the background image",
            filetypes=(("All files", "*.*"),)
        )
        self.selected_background_path = path
        shortened = self._shorten_path(path)
        self.bckgrd_img_text.set(f"Selected image:\n{shortened}")

        # If images are already loaded, apply background correction
        bkgrd = cv2.imread(self.selected_background_path, cv2.IMREAD_GRAYSCALE)
        if bkgrd is None:
            print("Could not read background image.")
            return

        bkgrd = bkgrd.astype(np.float32)
        bkgrd_smooth = cv2.GaussianBlur(bkgrd, (51, 51), 0)
        epsilon = 1e-6
        bkgrd_mean = np.mean(bkgrd_smooth)
        bkgrd_norm = bkgrd_smooth / (bkgrd_mean + epsilon)

        def correct_image(img):
            if img is None or img.size == 0:
                return img
            img_f = img.astype(np.float32)
            img_corrected = img_f / (bkgrd_norm + epsilon)
            return img_corrected.astype(np.uint8)

        # Apply correction to already displayed images
        axes_images = [
            (self.ax_im1, "Non activated platelets (1)", "im1"),
            (self.ax_im2, "Non activated platelets (2)", "im2"),
            (self.ax_im3, "Non activated platelets (3)", "im3"),
            (self.ax_im4, "Activated platelets (1)", "im4"),
            (self.ax_im5, "Activated platelets (2)", "im5"),
            (self.ax_im6, "Activated platelets (3)", "im6"),
        ]

        for ax, title, attr in axes_images:
            img = getattr(self, attr)
            if img is None or img.size == 0:
                continue

            corrected = correct_image(img)
            setattr(self, attr, corrected)

            ax.clear()
            ax.imshow(corrected, cmap="gray")
            ax.set_title(title)
            ax.axis("off")

        self.canvas.draw_idle()

    def preprocess_image(self, file_path: str, bkgrd_img_path: str):
        """
        Runs the exact same preprocessing pipeline used in count_platelets
        up to the normalized image stage so the UI preview matches DEBUG.
        Returns: img, img_corrected, img_norm
        """
        img = cv2.imread(str(file_path), cv2.IMREAD_GRAYSCALE)
        bkgrd = cv2.imread(bkgrd_img_path, cv2.IMREAD_GRAYSCALE)

        img = img.astype(np.float32)
        bkgrd = bkgrd.astype(np.float32)

        # Blur and normalize background
        bkgrd_smooth = cv2.GaussianBlur(bkgrd, (51, 51), 0)
        epsilon = 1e-6
        bkgrd_mean = np.mean(bkgrd_smooth)
        bkgrd_norm = bkgrd_smooth / (bkgrd_mean + epsilon)

        # Background correction
        img_corrected = img / (bkgrd_norm + epsilon)
        img_corrected = img_corrected.astype(np.uint8)

        # Histogram normalization
        dimensions = img_corrected.shape
        number_of_pixels = dimensions[0] * dimensions[1]
        min_val = float(self.min_val_var.get())

        hist, _ = np.histogram(img_corrected, bins=256, range=(min_val, 255))
        normalized_cumulative_histogram = np.cumsum(hist) / number_of_pixels

        img_norm = 255 * normalized_cumulative_histogram[img_corrected]
        img_norm = img_norm.astype(np.uint8)

        return img, img_corrected, img_norm

    def update_histogram_preview(self):
        """
        Recompute histogram normalization preview for the displayed images
        using the current slider value.
        """
        if not self.selected_background_path:
            return

        axes_images = [
            (self.ax_im1, "Non activated platelets (1)", "im1"),
            (self.ax_im2, "Non activated platelets (2)", "im2"),
            (self.ax_im3, "Non activated platelets (3)", "im3"),
            (self.ax_im4, "Activated platelets (1)", "im4"),
            (self.ax_im5, "Activated platelets (2)", "im5"),
            (self.ax_im6, "Activated platelets (3)", "im6"),
        ]

        paths = (
            self.selected_stat_image_paths + self.selected_act_image_paths
        )

        for (ax, title, attr), path in zip(axes_images, paths):
            if not path:
                continue

            img, img_corrected, img_norm = self.preprocess_image(
                path,
                self.selected_background_path
            )

            setattr(self, attr, img_norm)

            ax.clear()
            ax.imshow(img_norm, cmap="gray")
            ax.set_title(title)
            ax.axis("off")

        self.canvas.draw_idle()

    def run_count_platelets(self):
        """
        Wrapper called by the button.
        Uses stored paths to call count_platelets.
        Display results and updates count
        """
        if not self.selected_stat_image_paths:
            print("No non activated platelet images selected.")
            return
        
        if not self.selected_act_image_paths:
            print("No activated platelet images selected.")
            return

        if not self.selected_background_path:
            print("No background image selected.")
            return

        stat_counts = []
        stat_overlays = []
        for file_path in self.selected_stat_image_paths:
            labels_filtered = self.count_platelets(
                file_path=file_path,
                bkgrd_img_path=self.selected_background_path,
                debug=self.debug_mode.get()
            )
            stat_counts.append(np.max(labels_filtered))
            stat_overlays.append(labels_filtered)

        act_counts = []
        act_overlays = []
        for file_path in self.selected_act_image_paths:
            labels_filtered = self.count_platelets(
                file_path=file_path,
                bkgrd_img_path=self.selected_background_path,
                debug=self.debug_mode.get()
            )
            act_counts.append(np.max(labels_filtered))
            act_overlays.append(labels_filtered)

        # Show platelet counts
        stat_mean_count = np.mean(stat_counts)
        stat_std_count = np.std(stat_counts)
        act_mean_count = np.mean(act_counts)
        act_std_count = np.std(act_counts)
        platelet_loss = (stat_mean_count - act_mean_count) / stat_mean_count * 100

        # Propagate uncertainty for platelet loss (ratio propagation)
        epsilon = 1e-12
        rel_stat_std = stat_std_count / (stat_mean_count + epsilon)
        rel_act_std = act_std_count / (act_mean_count + epsilon)
        platelet_loss_std = abs(platelet_loss) * np.sqrt(rel_stat_std**2 + rel_act_std**2)

        self.platelet_count_text.set(
            f"""Non activated platelet count : {stat_mean_count:.1f} ± {stat_std_count:.1f}
Activated platelet count : {act_mean_count:.1f} ± {act_std_count:.1f}
Platelet loss : ({platelet_loss:.2f} ± {platelet_loss_std:.2f}) %"""
        )

        # Update images (use ORIGINAL images as background)
        stat_originals = [cv2.imread(p, cv2.IMREAD_GRAYSCALE) for p in self.selected_stat_image_paths]
        act_originals = [cv2.imread(p, cv2.IMREAD_GRAYSCALE) for p in self.selected_act_image_paths]

        axes_images = [
            (self.ax_im1, stat_originals[0], stat_overlays[0], f"{stat_counts[0]} platelets"),
            (self.ax_im2, stat_originals[1], stat_overlays[1], f"{stat_counts[1]} platelets"),
            (self.ax_im3, stat_originals[2], stat_overlays[2], f"{stat_counts[2]} platelets"),
            (self.ax_im4, act_originals[0], act_overlays[0], f"{act_counts[0]} platelets"),
            (self.ax_im5, act_originals[1], act_overlays[1], f"{act_counts[1]} platelets"),
            (self.ax_im6, act_originals[2], act_overlays[2], f"{act_counts[2]} platelets"),
        ]

        for ax, base_img, overlay, title in axes_images:
            ax.clear()
            ax.imshow(base_img, cmap="gray")
            ax.imshow(overlay, cmap="nipy_spectral", alpha=0.5)
            ax.set_title(title)
            ax.axis("off")

        self.canvas.draw_idle()

        # Show activity
        activity = platelets_to_vwf_activity(platelet_loss)
        # Propagate uncertainty through linear calibration (y = m x + b)
        activity_std = abs(m) * platelet_loss_std
        self.activity_text.set(f"({activity:.2f} ± {activity_std:.2f}) %")

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
            platelet_loss, activity,
            xerr=platelet_loss_std,
            yerr=activity_std,
            fmt="o",
            color="red",
            ecolor="red",
            elinewidth=2,
            capsize=5,
            label=f"Measured Point ({activity:.2f} ± {activity_std:.2f}%)"
        )
        self.ax_cal.set_xlabel("Platelet loss (%)")
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

        img, img_corrected, img_norm = self.preprocess_image(
            file_path,
            bkgrd_img_path
        )

        # Binarize the image with OTSU thresholding
        _, binary = cv2.threshold(
            img_norm, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )
        bin_img = binary.astype(bool)

        # Morphological filtering (work on boolean image)
        filtered_bin_img = morphology.remove_small_objects(bin_img, max_size=10)
        filtered_bin_img = morphology.remove_small_holes(filtered_bin_img, max_size=50)

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
                and r.area <= 200
                and r.solidity > 0.8
            ):
                coords = r.coords
                isolated_mask[coords[:, 0], coords[:, 1]] = True

        labels_filtered = measure.label(isolated_mask, connectivity=2)
        regions_filtered = measure.regionprops(labels_filtered)

        if debug:

            debug_fig = Figure(figsize=(14, 10))
            axes = [debug_fig.add_subplot(2, 4, i+1) for i in range(8)]

            axes[0].imshow(img, cmap="gray")
            axes[0].set_title("Image originale (niveaux de gris)")
            axes[0].axis("off")

            axes[1].imshow(img_corrected, cmap="gray")
            axes[1].set_title("Image corrigée")
            axes[1].axis("off")

            axes[2].imshow(img_norm, cmap="gray")
            axes[2].set_title("Image normalisée")
            axes[2].axis("off")

            axes[3].imshow(binary, cmap="gray")
            axes[3].set_title("Binarisation (OTSU)")
            axes[3].axis("off")

            axes[4].imshow(filtered_bin_img, cmap="gray")
            axes[4].set_title("Filtrage morphologique")
            axes[4].axis("off")

            axes[5].imshow(img, cmap="gray")
            axes[5].imshow(labels_all, cmap="nipy_spectral", alpha=0.5)
            axes[5].set_title(f"Régions détectées ({len(regions_all)})")
            axes[5].axis("off")

            axes[6].imshow(isolated_mask, cmap="gray")
            axes[6].set_title("Retrait des agrégats")
            axes[6].axis("off")

            axes[7].imshow(img, cmap="gray")
            axes[7].imshow(labels_filtered, cmap="nipy_spectral", alpha=0.5)
            axes[7].set_title(f"Plaquettes seules détectées ({len(regions_filtered)})")
            axes[7].axis("off")

            debug_fig.tight_layout()
            debug_fig.savefig(debug_file_path, dpi=300)

            # Explicitly delete figure to avoid Tkinter callback conflicts
            del debug_fig

        return labels_filtered

    def on_close(self):
        pass