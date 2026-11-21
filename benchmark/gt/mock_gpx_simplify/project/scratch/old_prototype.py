"""Quick thumbnail experiment for the photo gallery idea.

Abandoned: we ended up doing server-side resizing instead, so this
script is only kept for reference. Nothing else depends on it.
"""

import os
import sys

from PIL import Image, ImageOps

SUPPORTED = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def make_thumbnail(path, size=128):
    """Return a square, center-cropped thumbnail for the image at *path*."""
    with Image.open(path) as src:
        img = ImageOps.exif_transpose(src)
        img = img.convert("RGB")

    # shrink so the longest side fits, keeping the aspect ratio
    img.thumbnail((size, size), Image.LANCZOS)

    # center-crop to a square so every thumbnail has the same shape
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return img.crop((left, top, left + side, top + side))


def save_all(folder, out_dir, size=128):
    os.makedirs(out_dir, exist_ok=True)
    count = 0
    for name in sorted(os.listdir(folder)):
        base, ext = os.path.splitext(name)
        if ext.lower() not in SUPPORTED:
            continue
        src = os.path.join(folder, name)
        try:
            thumb = make_thumbnail(src, size=size)
        except OSError as exc:
            print(f"skip {name}: {exc}", file=sys.stderr)
            continue
        out_path = os.path.join(out_dir, base + "_thumb.jpg")
        thumb.save(out_path, "JPEG", quality=85)
        count += 1
    return count


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: SRC_DIR OUT_DIR [SIZE]")
        sys.exit(1)
    thumb_size = int(sys.argv[3]) if len(sys.argv) > 3 else 128
    n = save_all(sys.argv[1], sys.argv[2], thumb_size)
    print(f"wrote {n} thumbnails")
