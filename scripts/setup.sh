#!/usr/bin/env bash
# One-shot setup for Linux, WSL and macOS:  bash scripts/setup.sh [--cpu] [--no-models]
# Creates the conda env "projectlens" (or .venv when conda is missing), installs PyTorch for this machine,
# the pinned requirements and the package, downloads the models, then runs the tests and `projectlens doctor`.
set -euo pipefail
cd "$(dirname "$0")/.."

CPU=0
MODELS=1
for arg in "$@"; do
  case "$arg" in
    --cpu) CPU=1 ;;
    --no-models) MODELS=0 ;;
    *) echo "unknown option: $arg"; exit 1 ;;
  esac
done

# conda is often only on PATH in interactive shells, so also look in the usual install folders
CONDA="${CONDA_EXE:-$(command -v conda || true)}"
for c in "$HOME/miniconda3/bin/conda" "$HOME/anaconda3/bin/conda" "$HOME/miniforge3/bin/conda" "/opt/conda/bin/conda"; do
  [ -z "$CONDA" ] && [ -x "$c" ] && CONDA="$c"
done

if [ -n "$CONDA" ]; then
  source "$("$CONDA" info --base)/etc/profile.d/conda.sh"
  conda env list | grep -qE '^projectlens\s' || conda create -y -q -n projectlens python=3.11
  conda activate projectlens
else
  echo "conda not found, using .venv (needs Python 3.10+ with venv; on Ubuntu: sudo apt install python3-venv)"
  python3 -m venv .venv
  source .venv/bin/activate
fi
python -m pip install -q --upgrade pip

if [ "$CPU" = 0 ] && command -v nvidia-smi >/dev/null 2>&1; then
  echo "== PyTorch (CUDA 12.6)"
  pip install -q torch==2.7.1 --index-url https://download.pytorch.org/whl/cu126
else
  echo "== PyTorch (CPU / Apple MPS)"
  pip install -q torch==2.7.1
fi

echo "== requirements"
pip install -q -r requirements-dev.txt
pip install -q -e . --no-deps

if [ "$MODELS" = 1 ]; then
  echo "== models (bge-m3, bge-reranker-v2-m3)"
  python scripts/download_models.py
fi

echo "== tests"
python -m pytest -q
projectlens doctor
