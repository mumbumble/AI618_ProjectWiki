"""Stage 2 — chunks -> bge-m3 vectors. See README.md in this folder."""
from .encode import Encoded, encode_cached, encode_record

__all__ = ["Encoded", "encode_cached", "encode_record"]
