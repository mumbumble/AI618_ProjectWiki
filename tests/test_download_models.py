import fnmatch

import pytest

from scripts.download_models import PATTERNS, weight_patterns


@pytest.mark.parametrize("checkpoints", [
    ["pytorch_model.bin"],
    ["model.safetensors", "pytorch_model.bin"],
    ["model.safetensors.index.json", "model-00001-of-00002.safetensors", "model-00002-of-00002.safetensors"],
    ["pytorch_model.bin.index.json", "pytorch_model-00001-of-00002.bin", "pytorch_model-00002-of-00002.bin"],
])
def test_download_includes_checkpoint_without_duplicate_formats(checkpoints):
    # bge-m3's root contains only a .bin checkpoint; the previous patterns omitted it.
    files = ["config.json", "tokenizer.json", "sentencepiece.bpe.model", "onnx/model.onnx"] + checkpoints
    patterns = PATTERNS + weight_patterns(files)
    selected = [f for f in files if any(fnmatch.fnmatch(f, pattern) for pattern in patterns)]
    weights = [f for f in selected if f.endswith((".bin", ".safetensors"))]
    assert weights and "config.json" in selected and "tokenizer.json" in selected
    assert "onnx/model.onnx" not in selected
    if any(f.endswith(".safetensors") for f in checkpoints):
        assert all(f.endswith(".safetensors") for f in weights)
        assert set(weights) == {f for f in checkpoints if f.endswith(".safetensors")}
    else:
        assert set(weights) == {f for f in checkpoints if f.endswith(".bin")}


def test_download_rejects_repositories_without_supported_weights():
    with pytest.raises(RuntimeError, match="checkpoint"):
        weight_patterns(["config.json", "onnx/model.onnx"])
