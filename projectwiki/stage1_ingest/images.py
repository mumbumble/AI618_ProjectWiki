"""Stage 1 for images: Claude describes each image so it gets a text chunk like any other file."""
from __future__ import annotations

import base64
import logging
from pathlib import Path

from ..config import Config
from ..models import Claude, obj_schema
from ..schema import FileRecord

log = logging.getLogger(__name__)
IMAGE_SYSTEM = """You describe one image file from a user's local project folder so it can be searched and linked to the files that use it.
Write in {language}.
- description: two to four sentences on what the image shows, including any visible title, labels, axes, legend or text.
- role: a short noun phrase such as "pipeline diagram", "result plot", "qualitative comparison", "screenshot", "photo"."""
IMAGE_SCHEMA = obj_schema(description={"type": "string"}, role={"type": "string"})
MAX_IMAGE_SIDE = 1568
MAX_IMAGE_BYTES = 4_500_000


def image_block(path: Path) -> dict | None:
    """Downscale an image with PyMuPDF and wrap it as a base64 PNG content block."""
    import pymupdf
    pix = pymupdf.Pixmap(str(path))
    if pix.colorspace and pix.colorspace.n > 3:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    if pix.alpha:
        pix = pymupdf.Pixmap(pix, 0)
    n = 0
    while max(pix.width, pix.height) >> n > MAX_IMAGE_SIDE:
        n += 1
    if n:
        pix.shrink(n)
    data = pix.tobytes("png")
    if len(data) > MAX_IMAGE_BYTES:
        return None
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                        "data": base64.b64encode(data).decode()}}


def describe_images(root: Path, files: list[FileRecord], chunks: list, llm: Claude, cfg: Config) -> None:
    chunk_by_id = {c.id: c for c in chunks}
    targets = [f for f in files if f.type == "image" and not f.path.lower().endswith(".svg")][:cfg.max_images]
    system = IMAGE_SYSTEM.format(language=cfg.language)

    def run(f: FileRecord):
        try:
            block = image_block(root / f.path)
        except Exception as e:
            log.warning("could not read image %s: %s", f.path, e)
            return None
        if block is None:
            return None
        return llm.json(cfg.llm_model, system, [block, {"type": "text", "text": f"Path: {f.path}"}],
                        IMAGE_SCHEMA, key=f"image:{f.sha256}:{cfg.language}", max_tokens=2000)

    for f, r in zip(targets, llm.map(run, targets)):
        if r:  # the image's path-only chunk becomes a description chunk
            c = chunk_by_id[f.chunk_ids[0]]
            c.kind, c.locator, c.text = "figure", "image description", r["description"]
            f.summary, f.role = r["description"], r["role"]
    log.info("described %d images", sum(1 for f in targets if f.summary))
