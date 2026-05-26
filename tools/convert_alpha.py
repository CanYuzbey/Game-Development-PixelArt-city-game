"""
convert_alpha.py
----------------
Converts RGB sprite sheets with a baked-in checkerboard background
into true RGBA PNGs with a transparent background.

Algorithm (two-test background detector):
  is_gray   = (max(R,G,B) - min(R,G,B)) < 25
  is_bright = min(R,G,B) > 175
  is_bg     = is_gray AND is_bright

Post-processing:
  1. Dilate foreground 3 iterations with a 3x3 structuring element
  2. Fill holes (scipy.ndimage.binary_fill_holes)
  3. Write alpha channel: 255 for foreground, 0 for background
"""

import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation, binary_fill_holes

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(r"C:\Users\xxx\Desktop\GameDev")
SOURCE_DIR   = PROJECT_ROOT / "assets" / "source"
OUTPUT_DIR   = PROJECT_ROOT / "assets" / "source_rgba"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SATURATION_THRESH = 25   # max(R,G,B) - min(R,G,B) < this  → "gray"
BRIGHTNESS_THRESH = 175  # min(R,G,B) > this               → "bright"
DILATE_ITERS      = 3
STRUCT_3x3        = np.ones((3, 3), dtype=bool)

# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------
results = []

source_files = sorted(SOURCE_DIR.glob("*.png"))
if not source_files:
    print(f"No PNG files found in {SOURCE_DIR}")
    sys.exit(1)

print(f"Found {len(source_files)} source sheets in {SOURCE_DIR}")
print(f"Output directory: {OUTPUT_DIR}\n")
print("-" * 80)

for filepath in source_files:
    name = filepath.name

    img = Image.open(filepath)
    orig_mode = img.mode

    # Ensure we work with RGB (drop any existing alpha, handle palette modes)
    img_rgb = img.convert("RGB")
    arr = np.array(img_rgb, dtype=np.uint8)  # shape: (H, W, 3)

    H, W = arr.shape[:2]
    total_pixels = H * W

    R = arr[:, :, 0].astype(np.int16)
    G = arr[:, :, 1].astype(np.int16)
    B = arr[:, :, 2].astype(np.int16)

    # Two-test background detector
    saturation  = np.maximum.reduce([R, G, B]) - np.minimum.reduce([R, G, B])
    brightness  = np.minimum.reduce([R, G, B])

    is_gray   = saturation < SATURATION_THRESH
    is_bright = brightness > BRIGHTNESS_THRESH
    is_bg     = is_gray & is_bright

    # Foreground mask
    foreground = ~is_bg  # bool array (H, W)

    # Morphological dilation to close small gaps
    dilated = binary_dilation(foreground, structure=STRUCT_3x3, iterations=DILATE_ITERS)

    # Fill holes: background-coloured pixels enclosed by foreground are kept opaque
    filled = binary_fill_holes(dilated)

    # Build RGBA image
    alpha = np.where(filled, np.uint8(255), np.uint8(0))
    rgba_arr = np.dstack([arr, alpha])
    out_img = Image.fromarray(rgba_arr, mode="RGBA")

    out_path = OUTPUT_DIR / name
    out_img.save(out_path, format="PNG")

    fg_count = int(filled.sum())
    bg_count = total_pixels - fg_count
    pct_fg   = 100.0 * fg_count / total_pixels
    pct_bg   = 100.0 * bg_count / total_pixels

    suspicious = ""
    if pct_fg < 5.0:
        suspicious = "  *** SUSPICIOUS: < 5% opaque ***"
    elif pct_bg < 10.0:
        suspicious = "  *** SUSPICIOUS: > 90% opaque ***"

    print(f"[{name}]")
    print(f"  Original mode : {orig_mode}")
    print(f"  Output size   : {W}x{H} px")
    print(f"  Opaque pixels : {fg_count:>10,}  ({pct_fg:5.1f}%)")
    print(f"  Transparent   : {bg_count:>10,}  ({pct_bg:5.1f}%){suspicious}")
    print()

    results.append({
        "name":       name,
        "orig_mode":  orig_mode,
        "W": W, "H": H,
        "fg":         fg_count,
        "bg":         bg_count,
        "pct_fg":     pct_fg,
        "pct_bg":     pct_bg,
        "suspicious": bool(suspicious),
    })

# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------
print("=" * 80)
print(f"{'File':<30} {'Mode':<6} {'Opaque px':>12} {'Opaque %':>9} {'Transp %':>9}  Flag")
print("-" * 80)
for r in results:
    flag = "SUSPICIOUS" if r["suspicious"] else ""
    print(f"{r['name']:<30} {r['orig_mode']:<6} {r['fg']:>12,} {r['pct_fg']:>8.1f}% {r['pct_bg']:>8.1f}%  {flag}")
print("=" * 80)
print(f"\nDone. {len(results)} sheets converted to {OUTPUT_DIR}")
