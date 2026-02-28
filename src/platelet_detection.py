import os
import cv2
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from skimage import measure, morphology
from scipy.spatial.distance import cdist
    
# Define paths
script_dir = os.path.dirname(os.path.realpath(__file__))
data_dir = os.path.join(script_dir, '..', 'data')
orig_images_dir = os.path.join(data_dir, 'orig_images')
counted_images_dir = os.path.join(data_dir, 'counted_images')
img_dir = Path(orig_images_dir)
bkgrd_img_path = os.path.join(orig_images_dir, 'T1_Cp_no-agr-border_40x.jpg')

image_files = [
    p for p in img_dir.iterdir()
    if p.suffix.lower() in [".jpg", ".jpeg", ".png"]
    and p.name != "T1_Cp_no-agr-border_40x.jpg"
]

for file_path in image_files:

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

    # plt.figure(figsize=(14, 10))

    # plt.subplot(2, 4, 1)
    # plt.imshow(img, cmap="gray")
    # plt.title("Image originale (niveaux de gris)")
    # plt.axis("off")

    # plt.subplot(2, 4, 2)
    # plt.imshow(img_corrected, cmap="gray")
    # plt.title("Image corrigée")
    # plt.axis("off")

    # plt.subplot(2, 4, 3)
    # plt.imshow(img_norm, cmap="gray")
    # plt.title("Image normalisée")
    # plt.axis("off")

    # plt.subplot(2, 4, 4)
    # plt.imshow(binary, cmap="gray")
    # plt.title("Binarisation (OTSU)")
    # plt.axis("off")

    # plt.subplot(2, 4, 5)
    # plt.imshow(filtered_bin_img, cmap="gray")
    # plt.title("Filtrage morphologique")
    # plt.axis("off")

    # plt.subplot(2, 4, 6)
    # plt.imshow(img, cmap="gray")
    # plt.imshow(labels_all, cmap="nipy_spectral", alpha=0.5)
    # plt.title(f"Régions détectées ({len(regions_all)})")
    # plt.axis("off")

    # plt.subplot(2, 4, 7)
    # plt.imshow(isolated_mask, cmap="gray")
    # plt.title("Retrait des agrégats")
    # plt.axis("off")

    # plt.subplot(2, 4, 8)
    # plt.imshow(img, cmap="gray")
    # plt.imshow(labels_filtered, cmap="nipy_spectral", alpha=0.5)
    # plt.title(f"Plaquettes seules détectées ({len(regions_filtered)})")
    # plt.axis("off")

    # plt.tight_layout()
    # plt.show()

    plt.imshow(img, cmap="gray")
    plt.imshow(labels_filtered, cmap="nipy_spectral", alpha=0.5)
    plt.title(f"Plaquettes seules détectées ({len(regions_filtered)})")
    plt.axis("off")

    counted_image_path = os.path.join(counted_images_dir, f"counted_{file_path.name}")
    plt.savefig(counted_image_path)

