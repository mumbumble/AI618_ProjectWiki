"""Stage 1: read project files into evidence chunks (text, source locator, references)."""
from __future__ import annotations

import ast
import fnmatch
import hashlib
import json
import logging
import os
import re
from pathlib import Path

import pymupdf

from .config import Config
from .schema import Chunk, FileRecord, Ref

log = logging.getLogger(__name__)

SKIP_DIRS = {"node_modules", "__pycache__", "venv", "env", "site-packages", "wandb", "mlruns"}
SKIP_SUFFIX = (".pyc", ".pyo", ".so", ".o", ".class", ".DS_Store", ":Zone.Identifier", ".Identifier")
TYPES = {".pdf": "pdf", ".md": "markdown", ".markdown": "markdown", ".py": "python", ".ipynb": "notebook"}
TEXT_EXT = {".txt", ".rst", ".tex", ".bib", ".csv", ".tsv", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini",
            ".sh", ".bat", ".ps1", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".c", ".cc", ".cpp", ".h",
            ".hpp", ".cu", ".java", ".go", ".rs", ".m", ".r", ".lua", ".sql", ".log"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".tif", ".tiff"}
MEDIA_EXT = {".mp4", ".mov", ".avi", ".webm", ".mkv", ".wav", ".mp3", ".flac", ".m4a"}
TABLE_EXT = {".csv", ".tsv", ".log"}
TABLE_LINES = 40

HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
MD_LINK = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
WIKILINK = re.compile(r"\[\[([^\]|#]+)")
NB_IMPORT = re.compile(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", re.M)
SVG_TEXT = re.compile(r"<(?:text|tspan|title|desc)[^>]*>([^<]+)<")


def file_id(rel: str) -> str:
    """Stable id from the relative path, so feedback survives content edits."""
    return hashlib.sha1(rel.encode("utf-8")).hexdigest()[:10]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8", "cp949"):  # cp949 covers Korean files saved on Windows
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("latin-1", errors="replace")


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


def split_text(text: str, max_chars: int) -> list[str]:
    """Split on blank lines, then on line or word breaks for long paragraphs."""
    text = re.sub(r"\n{3,}", "\n\n", text.replace("\x00", "")).strip()
    if len(text) <= max_chars:
        return [text] if text else []
    out, buf = [], ""
    for p in re.split(r"\n\s*\n", text):
        while len(p) > max_chars:
            cut = p.rfind("\n", 0, max_chars)
            if cut < max_chars // 2:
                cut = p.rfind(" ", 0, max_chars)
            if cut < max_chars // 2:
                cut = max_chars
            if buf:
                out.append(buf)
                buf = ""
            out.append(p[:cut])
            p = p[cut:].lstrip()
        if buf and len(buf) + len(p) + 2 > max_chars:
            out.append(buf)
            buf = p
        else:
            buf = f"{buf}\n\n{p}" if buf else p
    if buf:
        out.append(buf)
    return [o.strip() for o in out if o.strip()]


# Each parser returns (pieces, refs, title): pieces are (kind, locator, text),
# refs are (kind, target, piece index).

def parse_markdown(text: str, max_chars: int):
    pieces, refs, title = [], [], ""
    stack, lines, loc, in_code = [], [], "(top)", False

    def flush():
        for part in split_text("\n".join(lines), max_chars):
            pieces.append(("section", loc, part))

    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            in_code = not in_code
        m = None if in_code else HEADING.match(line)
        if m:
            flush()
            lines = []
            level, name = len(m.group(1)), m.group(2)
            if level == 1 and not title:
                title = name
            stack = [s for s in stack if s[0] < level] + [(level, name)]
            loc = " > ".join(s[1] for s in stack)
        lines.append(line)
    flush()
    for i, (_, _, part) in enumerate(pieces):
        refs += [("link", m.group(1), i) for m in MD_LINK.finditer(part)]
        refs += [("wikilink", m.group(1).strip(), i) for m in WIKILINK.finditer(part)]
    return pieces, refs, title


def parse_python(text: str, max_chars: int):
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return [("text", "source", p) for p in split_text(text, max_chars)], [], ""
    lines = text.splitlines()
    head, defs = [], []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = min([d.lineno for d in node.decorator_list] + [node.lineno])
            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            loc = f"{'class' if kind == 'class' else 'def'} {node.name} (L{start}-L{node.end_lineno})"
            defs.append((kind, loc, start, node.end_lineno, "\n".join(lines[start - 1:node.end_lineno])))
        else:
            head.append("\n".join(lines[node.lineno - 1:node.end_lineno]))
    pieces = [("module", "module", p) for p in split_text("\n".join(head), max_chars)]
    spans = []  # (start line, end line, first piece index) per definition
    for kind, loc, start, end, src in defs:
        spans.append((start, end, len(pieces)))
        pieces += [(kind, loc, p) for p in split_text(src, max_chars)]
    if not pieces:
        return [], [], ""

    def piece_at(lineno: int) -> int:
        return next((i for s, e, i in spans if s <= lineno <= e), 0)

    refs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            refs += [("import", a.name, piece_at(node.lineno)) for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            prefix = "." * node.level
            if node.module:
                refs.append(("import", prefix + node.module, piece_at(node.lineno)))
            base = prefix + (node.module + "." if node.module else "")
            refs += [("import", base + a.name, piece_at(node.lineno)) for a in node.names if a.name != "*"]
    doc = (ast.get_docstring(tree) or "").strip()
    return pieces, refs, doc.splitlines()[0] if doc else ""


def parse_notebook(text: str, max_chars: int):
    pieces, refs, title = [], [], ""
    for n, cell in enumerate(json.loads(text).get("cells", [])):
        src = cell.get("source", "")
        src = "".join(src) if isinstance(src, list) else src
        ctype = cell.get("cell_type", "")
        for part in split_text(src, max_chars):
            i = len(pieces)
            pieces.append(("cell", f"cell {n + 1} ({ctype})", part))
            if ctype == "markdown":
                refs += [("link", m.group(1), i) for m in MD_LINK.finditer(part)]
                h = HEADING.match(part)
                title = title or (h.group(2) if h else "")
            elif ctype == "code":
                refs += [("import", m.group(1) or m.group(2), i) for m in NB_IMPORT.finditer(part)]
    return pieces, refs, title


def parse_pdf(path: Path, max_chars: int, max_pages: int):
    pieces = []
    with pymupdf.open(path) as doc:
        title = ((doc.metadata or {}).get("title") or "").strip()
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            pieces += [("page", f"p.{i + 1}", p) for p in split_text(page.get_text("text"), max_chars)]
    if not title and pieces:
        title = next((ln.strip() for ln in pieces[0][2].splitlines() if len(ln.strip()) > 3), "")
    return pieces, [], title


def parse_text(path: Path, max_chars: int):
    text = read_text(path)
    if path.suffix.lower() in TABLE_EXT:
        text = "\n".join(text.splitlines()[:TABLE_LINES])
    if path.suffix.lower() == ".svg":
        text = "\n".join(m.group(1).strip() for m in SVG_TEXT.finditer(text) if m.group(1).strip())
        return [("figure_text", "svg text", p) for p in split_text(text, max_chars)], [], ""
    return [("text", "text", p) for p in split_text(text, max_chars)], [], ""


def parse(path: Path, ftype: str, cfg: Config):
    if ftype == "pdf":
        return parse_pdf(path, cfg.max_chars, cfg.max_pdf_pages)
    if ftype == "markdown":
        return parse_markdown(read_text(path), cfg.max_chars)
    if ftype == "python":
        return parse_python(read_text(path), cfg.max_chars)
    if ftype == "notebook":
        return parse_notebook(read_text(path), cfg.max_chars)
    if ftype == "text" or path.suffix.lower() == ".svg":
        return parse_text(path, cfg.max_chars)
    return [], [], ""


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
