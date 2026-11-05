"""Stage 3 — summaries + vectors -> project record. See README.md in this folder."""
from .record import Record, build_record, diff_files
from .summarize import summarize

__all__ = ["Record", "build_record", "diff_files", "summarize"]
