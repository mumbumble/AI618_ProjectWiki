"""Download local models, or select just the encoder with --model BAAI/bge-m3."""
import argparse
import os
from pathlib import Path

MODELS = ["BAAI/bge-m3", "BAAI/bge-reranker-v2-m3"]
PATTERNS = ["*.json", "sentencepiece.bpe.model", "tokenizer*"]


def weight_patterns(files: list[str]) -> list[str]:
    """Prefer safetensors if available, otherwise fetch the actual PyTorch weights."""
    for index, patterns in (
        ("model.safetensors", ["model.safetensors"]),
        ("model.safetensors.index.json", ["model-*.safetensors"]),
        ("pytorch_model.bin", ["pytorch_model.bin"]),
        ("pytorch_model.bin.index.json", ["pytorch_model-*.bin"]),
    ):
        if index in files:
            return patterns
    raise RuntimeError("model repository has no supported PyTorch checkpoint")


def main() -> None:
    from huggingface_hub import list_repo_files, snapshot_download

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=MODELS, action="append", help="download only this model (repeatable)")
    parser.add_argument("--cache-dir", type=Path, help="Hugging Face cache directory")
    args = parser.parse_args()
    for name in args.model or MODELS:
        patterns = PATTERNS + weight_patterns(list_repo_files(name))
        # Serial downloads avoid a symlink-capability probe race in older Hub clients on Windows.
        path = snapshot_download(name, cache_dir=args.cache_dir, allow_patterns=patterns,
                                 max_workers=1 if os.name == "nt" else 2)
        weights = list(Path(path).glob("*.safetensors")) + list(Path(path).glob("pytorch_model*.bin"))
        if not weights:
            raise RuntimeError(f"checkpoint weights were not downloaded: {path}")
        print(name, "->", path, flush=True)

if __name__ == "__main__":
    main()
