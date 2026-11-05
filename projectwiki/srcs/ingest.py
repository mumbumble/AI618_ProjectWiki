"""File input: scan the project folder and turn every file into evidence chunks (text, locator, references)."""
from __future__ import annotations

import fnmatch
import hashlib
import logging
import os
import re
from pathlib import Path

from ..config import Config
from ..schema import Chunk, FileRecord, Ref
from .parsers import parse

log = logging.getLogger(__name__)
SKIP_DIRS = {"node_modules", "__pycache__", "venv", "env", "site-packages", "wandb", "mlruns"}
SKIP_SUFFIX = (".pyc", ".pyo", ".so", ".o", ".class", ".DS_Store", ":Zone.Identifier", ".Identifier")
TYPES = {".pdf": "pdf", ".md": "markdown", ".markdown": "markdown", ".py": "python", ".ipynb": "notebook"}
TEXT_EXT = {".txt", ".rst", ".tex", ".bib", ".csv", ".tsv", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini",
            ".sh", ".bat", ".ps1", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".c", ".cc", ".cpp", ".h",
            ".hpp", ".cu", ".java", ".go", ".rs", ".m", ".r", ".lua", ".sql", ".log"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".tif", ".tiff"}
MEDIA_EXT = {".mp4", ".mov", ".avi", ".webm", ".mkv", ".wav", ".mp3", ".flac", ".m4a"}


def file_id(rel: str) -> str:
    """Stable id from the relative path, so feedback survives content edits."""
    return hashlib.sha1(rel.encode("utf-8")).hexdigest()[:10]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def file_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in TYPES:
        return TYPES[ext]
    if ext in TEXT_EXT:
        return "text"
    if ext in IMAGE_EXT:
        return "image"
    if ext in MEDIA_EXT:
        return "media"
    with open(path, "rb") as f:
        head = f.read(4096)
    if head and b"\x00" not in head:  # extensionless text such as LICENSE or Makefile
        try:
            head.decode("utf-8")
            return "text"
        except UnicodeDecodeError:
            pass
    return "other"


def scan(root: Path, ignore: list[str]) -> list[Path]:
    paths = []
    for d, dirs, names in os.walk(root):
        rel_dir = Path(d).relative_to(root).as_posix()
        dirs[:] = sorted(x for x in dirs if not x.startswith(".") and x not in SKIP_DIRS
                         and not any(fnmatch.fnmatch(f"{rel_dir}/{x}".lstrip("./"), p) for p in ignore))
        for n in sorted(names):
            if n.startswith(".") or n.endswith(SKIP_SUFFIX) or ":" in n:
                continue
            p = Path(d) / n
            rel = p.relative_to(root).as_posix()
            if p.is_file() and not any(fnmatch.fnmatch(rel, pat) for pat in ignore):
                paths.append(p)
    return paths


def path_words(rel: str) -> str:
    return re.sub(r"[_\-./\\]+", " ", rel).strip()


def ingest(root: Path, cfg: Config) -> tuple[list[FileRecord], list[Chunk]]:
    root = Path(root).resolve()
    files, chunks = [], []
    for p in scan(root, cfg.ignore):
        rel = p.relative_to(root).as_posix()
        fid, ftype, size = file_id(rel), file_type(p), p.stat().st_size
        pieces, refs, title = [], [], ""
        if size <= cfg.max_file_mb * 1e6:
            try:
                pieces, refs, title = parse(p, ftype, cfg)
            except Exception as e:  # unreadable file: keep it as a path-only node
                log.warning("could not parse %s: %s", rel, e)
        if not pieces:  # binary, empty, or unreadable: the path is the only evidence
            pieces = [("path", "path", path_words(rel))]
        rec = FileRecord(id=fid, path=rel, type=ftype, sha256=sha256(p), size=size,
                         title=(title or p.stem).strip()[:120])
        for i, (kind, loc, text) in enumerate(pieces):
            chunks.append(Chunk(id=f"{fid}#{i}", file_id=fid, kind=kind, locator=loc, text=text))
            rec.chunk_ids.append(f"{fid}#{i}")
        rec.refs = [Ref(kind=k, target=t, chunk_id=f"{fid}#{i}") for k, t, i in refs]
        files.append(rec)
    log.info("ingested %d files, %d chunks", len(files), len(chunks))
    return files, chunks
