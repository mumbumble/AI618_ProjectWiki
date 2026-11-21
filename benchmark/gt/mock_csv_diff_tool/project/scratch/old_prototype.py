"""thumbgrid: experimental thumbnail and contact sheet helper.

Abandoned prototype. The idea was to batch-render a folder of photos
into one contact sheet for quick visual review. Never finished, kept
for reference only.
"""

import os
import sys

from PIL import Image, ImageDraw


SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}


def make_thumbnail(path, size=(128, 128)):
    """Return an RGB thumbnail copy of the image at *path*, fitted inside *size*."""
    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail(size, Image.LANCZOS)
        return im.copy()


def _cell_size(thumbs):
    width = max(t.width for t in thumbs)
    height = max(t.height for t in thumbs)
    return width, height


def contact_sheet(paths, cols=4, size=(128, 128), pad=8, background=(30, 30, 30)):
    """Lay out thumbnails for *paths* in a grid with *cols* columns."""
    paths = [p for p in paths if os.path.splitext(p)[1].lower() in SUPPORTED_EXTS]
    if not paths:
        raise ValueError("no supported image files given")

    thumbs = []
    for p in paths:
        try:
            thumbs.append(make_thumbnail(p, size=size))
        except OSError as exc:
            # skip unreadable files instead of aborting the whole sheet
            print(f"skipping {p}: {exc}")
    if not thumbs:
        raise ValueError("no readable images")

    # TODO: EXIF orientation is ignored, so rotated phone photos come out sideways.
    cell_w, cell_h = _cell_size(thumbs)
    rows = (len(thumbs) + cols - 1) // cols
    sheet_w = cols * (cell_w + pad) + pad
    sheet_h = rows * (cell_h + pad) + pad
    sheet = Image.new("RGB", (sheet_w, sheet_h), background)
    draw = ImageDraw.Draw(sheet)

    for i, thumb in enumerate(thumbs):
        r, c = divmod(i, cols)
        x = pad + c * (cell_w + pad)
        y = pad + r * (cell_h + pad)
        # centre each thumbnail inside its cell
        x += (cell_w - thumb.width) // 2
        y += (cell_h - thumb.height) // 2
        sheet.paste(thumb, (x, y))
        draw.rectangle(
            [x - 1, y - 1, x + thumb.width, y + thumb.height],
            outline=(90, 90, 90),
        )

    return sheet


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: python old_prototype.py OUT.png IMG [IMG ...]")
        sys.exit(2)
    out_path, inputs = sys.argv[1], sys.argv[2:]
    sheet = contact_sheet(inputs, cols=4)
    sheet.save(out_path)
    print(f"wrote {out_path} ({sheet.width}x{sheet.height})")
