# One-shot setup for Windows PowerShell (Anaconda/Miniconda Prompt or a shell where `conda` works):
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 [-Cpu] [-NoModels]
param([switch]$Cpu, [switch]$NoModels)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$envs = conda env list | Out-String
if ($envs -notmatch "(?m)^projectwiki\s") { conda create -y -q -n projectwiki python=3.11 }
conda activate projectwiki
python -m pip install -q --upgrade pip

$hasGpu = $null -ne (Get-Command nvidia-smi -ErrorAction SilentlyContinue)
if (-not $Cpu -and $hasGpu) {
    Write-Host "== PyTorch (CUDA 12.6)"
    pip install -q torch==2.7.1 --index-url https://download.pytorch.org/whl/cu126
} else {
    Write-Host "== PyTorch (CPU)"
    pip install -q torch==2.7.1
}

Write-Host "== requirements"
pip install -q -r requirements-dev.txt
pip install -q -e . --no-deps

if (-not $NoModels) {
    Write-Host "== models (bge-m3, bge-reranker-v2-m3)"
    python scripts\download_models.py
}

Write-Host "== tests"
python -m pytest -q
projectwiki doctor
