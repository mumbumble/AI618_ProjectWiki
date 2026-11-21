# LeafProto

Few-shot plant disease classification from leaf photos. LeafProto is a prototype classifier with a frequency-domain augmentation (FreqMix) and a cosine prototype head. It was developed at the Plant Vision Lab, Hanbit University.

Paper: *LeafProto: Few-Shot Plant Disease Classification with Frequency-Domain Mixing and a Cosine Prototype Head* (current draft: `paper/leafproto_draft_v2.pdf`).

## Method in brief

Full details are in `docs/method.md`. In short:

- **FreqMix**: take the 2D FFT of each leaf image per channel and split it into amplitude and phase. For two images in the same episode, the low-frequency amplitude band is interpolated. The mask is a centered square covering 10% of the shorter side of the shifted spectrum (beta = 0.1), and the mixing weight is lam ~ Uniform(0.3, 0.7). Phase is kept, then an inverse FFT is applied. The label is that of the first image. FreqMix is applied with probability 0.5 per image, during training only.
- **Cosine prototype head**: each prototype is the mean of the L2-normalized support embeddings of a class. Logits are `s * cos(f_q, p_c)`, where the scale `s` is learnable and starts at 10.0.
- **Encoder**: ResNet-12 with channels 64-160-320-640, giving a 640-d embedding after global average pooling.
- **Loss**: `L = L_ce + 0.5 * L_cons`. `L_cons` is the KL divergence between the predictions for the clean query view (detached) and the FreqMix query view.

## Results (5-way, accuracy %, mean ± ci95)

| Method     | 1-shot     | 2-shot     | 5-shot     | 10-shot    |
|------------|------------|------------|------------|------------|
| Finetune   | 52.3 ± 0.9 | 61.8 ± 0.8 | 72.5 ± 0.7 | 79.1 ± 0.6 |
| ProtoClass | 60.4 ± 0.9 | 70.2 ± 0.8 | 80.9 ± 0.6 | 85.0 ± 0.5 |
| FastAdapt  | 64.8 ± 0.9 | 73.5 ± 0.8 | 83.6 ± 0.6 | 87.2 ± 0.5 |
| LeafProto  | 69.7 ± 0.9 | 78.3 ± 0.7 | 87.4 ± 0.5 | 90.6 ± 0.4 |

At 5 shots LeafProto reaches 87.4%, which is 3.8 points above FastAdapt and 6.5 points above ProtoClass.

Ablation at 5 shots (accuracy %), also stored in `results/`:

| Variant                                  | 5-shot | Change |
|------------------------------------------|--------|--------|
| Full LeafProto                           | 87.4   | –      |
| w/o FreqMix                              | 84.0   | -3.4   |
| w/o cosine head (squared Euclidean)      | 85.2   | -2.2   |
| w/o consistency loss (lambda_cons = 0)   | 86.3   | -1.1   |
| FreqMix full spectrum (beta = 1.0)       | 85.6   | -1.8   |

FreqMix is the largest contributor. The low-frequency band carries leaf color and illumination, while disease texture sits in higher frequencies and is preserved.

## Setup

Requirements: Python 3.10, PyTorch 2.2, numpy, pyyaml, pandas, matplotlib.

```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install "torch==2.2.*" numpy pyyaml pandas matplotlib
```

## Data

The dataset is `leafdoc_fs`: 18,420 field photos of leaves across 54 classes (species x disease). The split is 30 base classes for training, 12 for validation, and 12 novel classes for test. Place the data under `data/leafdoc_fs/`. The metadata CSV is `data/leafdoc_fs/metadata.csv` with the columns `image_path, label, species, disease, split`. Images are resized to 84x84.

## Configs

Configs live in `configs/`. The base config holds the default values: lr 0.001, Adam, weight decay 0.0005, cosine schedule, image size 84, 1 episode per step, 5-way, 1-shot, 15 queries, 40,000 episodes, seed 42, FreqMix beta 0.1 and p 0.5, lambda_cons 0.5, scale init 10.0, evaluation every 500 steps, 4 data workers.

The 5-way config used for the paper is `configs/<5-way-config>.yaml`. It starts with an `inherits:` line that points to the base config and overrides `k_shot: 5`, `log_dir: logs`, and `results_csv` (the CSV under `results/`). Replace `<5-way-config>` with the actual filename in `configs/`.

## Training

Run the 5-way training with:

```bash
python src/train.py --config configs/<5-way-config>.yaml
```

Without `--config`, `src/train.py` uses the base config.

Each run writes a log to `logs/train_{YYYY-MM-DD}.log`. The first line records the config, for example:

```
[2026-10-08 09:12:03] config: configs/<5-way-config>.yaml
```

The reference run took 5 h 40 min for 40,000 episodes on one RTX 4090. Validation accuracy went from 71.2% at step 500 to 87.1% at step 40,000. The best checkpoint was saved at step 38,500 to `checkpoints/best.pt`.

## Evaluation

Evaluation uses 600 test episodes, 5-way, 15 queries per class, with seed 42. The output is mean accuracy in % with a 95% confidence interval over episodes.

```bash
python src/evaluate.py --config configs/<5-way-config>.yaml --ckpt checkpoints/best.pt
```

## Figures

Plotting scripts live in `src/`. Run the one named `plot_*.py` to regenerate the accuracy-versus-shots chart in `figures/` from the results CSV.

## Repository layout

- `configs/`: YAML configs (base config and 5-way config)
- `src/`: training, evaluation, FreqMix, model, data loading, utils, and plotting code
- `data/`: dataset folder (`leafdoc_fs/`), not tracked in git
- `logs/`: training logs named by date
- `checkpoints/`: saved model weights
- `results/`: result CSV and ablation table
- `figures/`: generated plots and pipeline diagram
- `docs/`: method description (`docs/method.md`)
- `papers/`: reading notes on the baseline papers
- `paper/`: paper drafts
- `notes/`: meeting notes

## Team

- Park Hyunwoo: first author, training code
- Kim Seoyeon: data and splits, FreqMix experiments
- Lee Doyun: baselines and plotting
- Choi Jimin: writing and related work
- Prof. Jung Minjun: advisor
