"""Pipeline settings. Similarity thresholds are percentiles so they hold for any encoder."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path


@dataclass
class Config:
    # file input (srcs/ingest.py)
    max_chars: int = 1500  # max characters per evidence chunk
    max_file_mb: float = 50.0  # larger files become path-only nodes
    max_pdf_pages: int = 300
    ignore: list[str] = field(default_factory=list)  # extra glob patterns on relative paths

    # ① encoding (models/encoder.py)
    encoder: str = "bge-m3"  # bge-m3 | tfidf (tfidf is for tests only)
    encoder_model: str = "BAAI/bge-m3"
    batch_size: int = 16
    max_length: int = 1024  # tokens per chunk

    # project record: Claude image descriptions and summaries (srcs/enrich.py)
    llm: bool = True
    llm_backend: str = "cli"  # cli (logged-in Claude Code CLI, uses the subscription) | api (ANTHROPIC_API_KEY)
    llm_model: str = "claude-sonnet-5-5"  # relation judgment, image descriptions
    llm_small_model: str = "claude-haiku-5-5"  # file summaries, group names
    llm_effort: str = "low"
    llm_workers: int = 8
    language: str = "Korean"  # language of summaries, labels and descriptions
    summarize: bool = True
    describe_images: bool = True
    max_images: int = 200

    # ② clustering, experimental slot (models/clustering.py): baseline | pref
    clusterer: str = "pref"
    cluster_alpha: float = 0.6  # weight of embedding distance against folder-tree distance
    cluster_pct: float = 35.0  # merge threshold, percentile of pairwise distances
    name_groups: bool = True

    # ③ structure generation (models/structure.py)
    k_within: int = 3  # similarity neighbours per file inside its group
    sim_pct: float = 75.0  # min similarity inside a group, percentile of all file pairs
    sim_cross_pct: float = 97.0  # min similarity for the one cross-group neighbour
    reranker: str = "BAAI/bge-reranker-v2-m3"  # "" disables evidence reranking
    rerank_pairs: int = 8  # chunk pairs per candidate edge sent to the reranker
    judge: bool = True  # LLM relation judgment on every candidate edge
    max_judge_edges: int = 2000  # cost cap; edges beyond it keep their rule-based relation

    # ④ preference reflection, experimental slot (models/preference.py): baseline | drift (4안) | align (1안)
    # and the final graph (srcs/finalize.py)
    corrector: str = "drift"
    drift_tau: float = 0.1  # kernel width on edge-pair similarity
    drift_margin: float = 0.2  # kernel value at which a similar judged edge changes this one
    drift_gain: float = 1.0  # weight of attraction minus repulsion added to the edge score
    align_l2: float = 1.0  # L2 weight of the Bradley–Terry preference model
    min_score: float = float("-inf")  # inferred edges scoring below this are dropped

    def save(self, path: Path) -> None:
        d = asdict(self)
        d["min_score"] = None if d["min_score"] == float("-inf") else d["min_score"]
        path.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> Config:
        d = json.loads(path.read_text(encoding="utf-8"))
        if d.get("min_score") is None:
            d["min_score"] = float("-inf")
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known})
