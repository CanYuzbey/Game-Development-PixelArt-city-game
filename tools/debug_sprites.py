#!/usr/bin/env python3
"""
tools/debug_sprites.py
======================
Sprite-sheet debug pipeline.

For each source sheet in assets/source/:
  1. Detects non-background sprite regions using scipy connected-component labelling.
  2. Saves a numbered debug overlay to assets/debug/.
  3. Writes detected pixel_rects to assets/manifests/detected_regions.json.

The detected_regions.json is then used by build_sprite_registry.py to produce
the final sprite_registry.json with known sprite IDs mapped to pixel_rects.

Usage:
    python tools/debug_sprites.py
"""

import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_DIR  = os.path.join(ROOT, "assets", "source")
DEBUG_DIR   = os.path.join(ROOT, "assets", "debug")
MANIFEST_DIR = os.path.join(ROOT, "assets", "manifests")

# ── Detection parameters ───────────────────────────────────────────────────────

BG_THRESHOLD   = 170   # pixels with R,G,B all >= this are treated as background
MIN_AREA       = 1500  # bounding-box area (px²) below this → discard as noise
DILATION_ITERS = 12    # connect nearby foreground pixels into single blobs
BOX_PADDING    = 6     # extra pixels around each detected bbox

# ── Colour palette for debug boxes ────────────────────────────────────────────

PALETTE = [
    "#E63946", "#F4A261", "#2A9D8F", "#457B9D", "#E9C46A",
    "#A8DADC", "#6A4C93", "#F72585", "#4CC9F0", "#80B918",
]

# ── Core functions ─────────────────────────────────────────────────────────────

def detect_bg_threshold(arr: np.ndarray) -> int:
    """
    Sample image corners to auto-detect the background brightness.
    Returns a threshold; pixels with all channels >= threshold → background.
    """
    h, w = arr.shape[:2]
    margin = min(30, h // 10, w // 10)
    corners = np.concatenate([
        arr[:margin, :margin].reshape(-1, 3),
        arr[:margin, w - margin:].reshape(-1, 3),
        arr[h - margin:, :margin].reshape(-1, 3),
        arr[h - margin:, w - margin:].reshape(-1, 3),
    ])
    # Use the 10th percentile of the corner pixel minimum-channel as threshold
    min_channels = corners.min(axis=1)
    threshold = int(np.percentile(min_channels, 10)) - 10
    return max(threshold, 140)


def find_sprite_bboxes(img_path: str) -> list[tuple[int, int, int, int]]:
    """
    Return a sorted list of (x, y, w, h) bounding boxes for every distinct
    sprite region found in img_path.  Sorted top-to-bottom, left-to-right.
    """
    img = Image.open(img_path).convert("RGB")
    arr = np.array(img)
    h, w = arr.shape[:2]

    threshold = detect_bg_threshold(arr)

    # Foreground = any pixel where at least one channel is dark enough
    is_fg = (arr[:, :, 0] < threshold) | \
            (arr[:, :, 1] < threshold) | \
            (arr[:, :, 2] < threshold)

    # Dilate to merge nearby sprite parts into single connected blobs
    struct = ndimage.generate_binary_structure(2, 2)
    dilated = ndimage.binary_dilation(is_fg, structure=struct,
                                      iterations=DILATION_ITERS)

    labeled, num_features = ndimage.label(dilated)

    bboxes: list[tuple[int, int, int, int]] = []
    for region_id in range(1, num_features + 1):
        ys, xs = np.where(labeled == region_id)
        x_min, x_max = int(xs.min()), int(xs.max())
        y_min, y_max = int(ys.min()), int(ys.max())
        area = (x_max - x_min) * (y_max - y_min)
        if area < MIN_AREA:
            continue
        # Apply padding and clamp to image bounds
        x0 = max(0, x_min - BOX_PADDING)
        y0 = max(0, y_min - BOX_PADDING)
        x1 = min(w - 1, x_max + BOX_PADDING)
        y1 = min(h - 1, y_max + BOX_PADDING)
        bboxes.append((x0, y0, x1 - x0, y1 - y0))

    # Sort: row band (every 60px), then left-to-right within band
    bboxes.sort(key=lambda b: (b[1] // 60, b[0]))
    return bboxes


def generate_debug_image(source_path: str, debug_path: str,
                          bboxes: list[tuple[int, int, int, int]]) -> None:
    """
    Draw numbered coloured bounding boxes over the source sheet and save
    as an RGBA PNG to debug_path.
    """
    img = Image.open(source_path).convert("RGBA")
    draw = ImageDraw.Draw(img)

    for idx, (x, y, bw, bh) in enumerate(bboxes):
        colour = PALETTE[idx % len(PALETTE)]
        draw.rectangle([x, y, x + bw, y + bh], outline=colour, width=2)
        label = str(idx)
        # Shadow then label
        draw.text((x + 3, y + 3), label, fill=(0, 0, 0, 200))
        draw.text((x + 2, y + 2), label, fill=(255, 255, 255, 255))

    img.save(debug_path)
    print(f"  debug -> {os.path.basename(debug_path)}  ({len(bboxes)} regions)")


# ── Sheet registry (source filename → human sheet id) ─────────────────────────

SHEETS = {
    "terrain_ground":   "Terrain & ground tiles",
    "buildings":        "Buildings (CBD / mid-rise / residential / commercial)",
    "landmarks":        "Landmark buildings",
    "coastal":          "Coastal & waterfront tiles",
    "road_diagonals":   "Diagonal road & sidewalk tiles",
    "park_objects":     "Park & landscape objects",
    "roofs":            "Roof variants",
    "city_profile_kits":"City-profile facade kits",
    "street_props":     "Signage & street props",
    "night_overlays":   "Night / lighting overlays",
    "building_overlays":"Building shadow & weathering overlays",
    "civic_columns":    "Civic columns building variant",
}


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    os.makedirs(DEBUG_DIR, exist_ok=True)
    os.makedirs(MANIFEST_DIR, exist_ok=True)

    detected: dict = {"schema": "detected_regions.v1", "sheets": {}}

    for sheet_id, description in SHEETS.items():
        src = os.path.join(SOURCE_DIR, f"{sheet_id}.png")
        if not os.path.exists(src):
            print(f"[SKIP] {sheet_id}.png not found")
            continue

        img = Image.open(src)
        print(f"\n[{sheet_id}]  {img.size[0]}×{img.size[1]}  {img.mode}")

        bboxes = find_sprite_bboxes(src)

        debug_path = os.path.join(DEBUG_DIR, f"{sheet_id}_debug.png")
        generate_debug_image(src, debug_path, bboxes)

        detected["sheets"][sheet_id] = {
            "description": description,
            "source_file": f"source/{sheet_id}.png",
            "size": list(img.size),
            "mode": img.mode,
            "alpha_status": "RGB_no_alpha_needs_conversion",
            "detected_region_count": len(bboxes),
            "regions": [
                {"index": i, "pixel_rect": list(bb)}
                for i, bb in enumerate(bboxes)
            ],
        }

    out = os.path.join(MANIFEST_DIR, "detected_regions.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(detected, f, indent=2)
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
