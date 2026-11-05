"""Download the two local models (about 4.5 GB in total) into the Hugging Face cache."""
from huggingface_hub import snapshot_download

MODELS = ["BAAI/bge-m3", "BAAI/bge-reranker-v2-m3"]
PATTERNS = ["*.json", "model.safetensors", "sentencepiece.bpe.model", "tokenizer*"]

if __name__ == "__main__":
    for name in MODELS:
        print(name, "->", snapshot_download(name, allow_patterns=PATTERNS))
