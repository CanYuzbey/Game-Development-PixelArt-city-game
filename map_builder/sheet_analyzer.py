"""
map_builder/sheet_analyzer.py  —  sprite sheet tile extractor
"""
from __future__ import annotations
import sys, os, io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from PIL import Image, ImageDraw, ImageFont

ASSETS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'assets')
)


# ─────────────────────────────────────────────────────────────────────────────
# Core scanner
# ─────────────────────────────────────────────────────────────────────────────

def _alpha_row_sums(img: Image.Image) -> list[int]:
    alpha = img.split()[3]
    w, h  = img.size
    pix   = alpha.load()
    return [sum(pix[x, y] for x in range(w)) for y in range(h)]


def _alpha_col_sums(img: Image.Image, y0: int, y1: int) -> list[int]:
    alpha = img.split()[3]
    w     = img.width
    pix   = alpha.load()
    return [sum(pix[x, y] for y in range(y0, y1 + 1)) for x in range(w)]


def _bands(sums: list[int], threshold: int = 500) -> list[tuple[int, int]]:
    """Return (start, end) bands where sums > threshold."""
    bands, in_b, start = [], False, 0
    for i, s in enumerate(sums):
        if s > threshold and not in_b:
            start, in_b = i, True
        elif s <= threshold and in_b:
            bands.append((start, i - 1))
            in_b = False
    if in_b:
        bands.append((start, len(sums) - 1))
    return bands


def scan_tiles(img: Image.Image, min_w: int = 35, min_h: int = 15) -> list[tuple[int,int,int,int]]:
    """Return (left, top, w, h) for every tile found."""
    if img.mode != 'RGBA':
        img = img.convert('RGBA')

    row_sums  = _alpha_row_sums(img)
    row_bands = _bands(row_sums, threshold=300)

    rects: list[tuple[int,int,int,int]] = []
    for (ry0, ry1) in row_bands:
        if ry1 - ry0 < min_h:
            continue
        col_sums  = _alpha_col_sums(img, ry0, ry1)
        col_bands = _bands(col_sums, threshold=200)
        for (cx0, cx1) in col_bands:
            if cx1 - cx0 < min_w:
                continue
            # Tighten vertical bounds within this column
            alpha = img.split()[3].load()
            ytop = ry1
            ybot = ry0
            for y in range(ry0, ry1 + 1):
                for x in range(cx0, cx1 + 1):
                    if alpha[x, y] > 8:
                        ytop = min(ytop, y)
                        ybot = max(ybot, y)
            rects.append((cx0, ytop, cx1 - cx0 + 1, ybot - ytop + 1))

    rects.sort(key=lambda r: (r[1], r[0]))
    return rects


def analyze(sheet_name: str, verbose: bool = True) -> list[tuple[int,int,int,int]]:
    path  = os.path.join(ASSETS_DIR, f'{sheet_name}.png')
    img   = Image.open(path).convert('RGBA')
    rects = scan_tiles(img)
    if verbose:
        print(f'\n{sheet_name}.png  {img.width}x{img.height}  ->  {len(rects)} tiles')
        print(f'{"idx":>4}  {"left":>5}  {"top":>5}  {"w":>5}  {"h":>5}')
        print('-' * 36)
        for i, (l, t, w, h) in enumerate(rects):
            print(f'{i:>4}  {l:>5}  {t:>5}  {w:>5}  {h:>5}')
    return rects


def save_debug(sheet_name: str, rects: list[tuple[int,int,int,int]]) -> None:
    path     = os.path.join(ASSETS_DIR, f'{sheet_name}.png')
    out_path = os.path.join(ASSETS_DIR, f'{sheet_name}_debug.png')
    img      = Image.open(path).convert('RGBA')
    draw     = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype('arial.ttf', 11)
    except Exception:
        font = ImageFont.load_default()
    for i, (l, t, w, h) in enumerate(rects):
        draw.rectangle([l, t, l+w-1, t+h-1], outline=(255,0,0,255), width=2)
        draw.text((l+3, t+2), str(i), fill=(255,255,0,255), font=font)
    img.save(out_path)
    print(f'Saved: {out_path}')


if __name__ == '__main__':
    for sheet in ('roads', 'sidewalks'):
        rects = analyze(sheet, verbose=True)
        save_debug(sheet, rects)
