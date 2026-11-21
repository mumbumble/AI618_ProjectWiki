# ProsodySER: Prosody-Aware Attention for Bilingual Korean-English Speech Emotion Recognition

This repository holds the code for ProsodySER, a speech emotion recognition (SER) model whose attentive pooling is biased by prosody (F0, energy, voicing). The task is utterance-level 6-class emotion recognition (neutral, happy, sad, angry, fearful, surprised) on Korean and English acted speech from the KoEn-Emo corpus.

- Paper: `paper/prosody_ser_draft_v2.pdf` (paper title: "Listening to How It Is Said: Prosody-Aware Attention for Bilingual Korean-English Speech Emotion Recognition")
- Method description, matched to the code: `docs/method.md`
- Primary metric: unweighted accuracy (UA, mean per-class recall, in %). Weighted accuracy (WA) is a secondary metric.

## Method in brief

Pipeline:

Waveform -> 80-bin log-Mel (25 ms window, 10 ms hop) -> Conv Stem (2 conv layers, stride 2 each) -> Transformer Encoder (6 layers, d_model 256, 4 heads, dropout 0.1) -> Prosody-Aware Pooling -> Emotion Classifier

- Side branch: Prosody Extractor (6 features per frame: `[logf0_z, energy_db, voiced, d_logf0, d_energy, d_voiced]`) -> Prosody Encoder (2 conv layers, kernel 5, hidden 128) -> feeds the pooling.
- Second branch: Gradient Reversal Layer -> Language Classifier (ko/en).

Prosody-Aware Pooling (PAP, `class ProsodyAttention`) scores frame t as

e_t = (h_t W_q)(c W_k)^T / sqrt(d_k) + lambda * g_t, with g_t = v^T tanh(W_p p_t)

where c is a learned query, p_t is the prosody embedding, and lambda is a learnable scalar initialized at 0.5. Weights are a softmax over frames with padding masked, and the utterance embedding is z = sum_t a_t h_t. Four pooling heads are concatenated and projected to 256 dimensions.

Training loss: L = L_ce + 0.2 * L_lang. L_ce uses label smoothing 0.1. L_lang passes through the gradient reversal layer, whose strength ramps from 0 to 1 over the first 5 epochs.

Compared with EmoFormer (attentive pooling, content only, monolingual), ProsodySER adds the prosody bias term inside the pooling attention and the language-adversarial branch. The model has 11.3M parameters.

## Dataset: KoEn-Emo

- 14,820 acted utterances from 118 speakers (60 Korean, 58 English), 16 kHz mono, 1.2 to 7.5 s each, about 21.4 hours.
- Speaker-independent split (70/15/15): train 10,374, validation 2,223, test 2,223. No speaker appears in more than one split.
- Metadata columns: `utt_id, speaker_id, lang (ko|en), emotion, path, duration_s, split`.
- The loader is the `KoEnEmoDataset` class; `make_loaders(cfg)` builds the three loaders.
- Noise robustness: the test set is mixed with babble noise at 20, 10, 5 and 0 dB SNR.
- Corpus curation and annotation: 정민지 (research assistant).

The corpus itself is not included in this repository. Point the `path` column of the metadata at your local copy.

## Installation

```bash
git clone <this-repo-url> prosody_ser
cd prosody_ser
python -m venv .venv
source .venv/bin/activate
pip install torch torchaudio pyyaml numpy pandas scikit-learn matplotlib
```

A CUDA GPU is strongly recommended. The reference run used one NVIDIA A100-SXM4-40GB.

## Configuration

Experiments are described by YAML files in `configs/`. The base config holds the defaults (AdamW, lr 3e-4, weight decay 0.01, batch size 32, 30 epochs, warmup 500 steps, cosine decay, grad clip 1.0, seed 1234, label smoothing 0.1, lambda_init 0.5, 4 heads, d_model 256, 6 layers, prosody_dim 6, prosody_hidden 128). An experiment config starts with `inherits:` pointing at the base config and overrides only what it changes. The bilingual 6-class experiment sets `lang_loss_weight: 0.2` and `epochs: 30`, and is named `bilingual_6class`.

`load_config` resolves `inherits` automatically, so always pass the experiment file to the scripts.

## Training

```bash
python src/train.py --config configs/<experiment>.yaml
```

- The default `--config` is the base config.
- Steps per epoch: 325 (10,374 / 32, rounded up). Total: 9,750 steps for 30 epochs.
- Logs go to `logs/train_<date>.log`, with a line every 100 steps (step, epoch, loss, lr) and validation UA after each epoch.
- Checkpoints are saved to `checkpoints/`. The best checkpoint is chosen on validation UA.
- Expected cost: about 2.1 hours on one A100 40GB for 30 epochs.

Reference run (2026-08-19): validation UA reached 58.9 at epoch 5, 66.5 at epoch 10, 72.6 at epoch 20, and 73.1 at epoch 22, the best checkpoint. Epoch 30 scored 72.8.

## Evaluation

```bash
python src/evaluate.py --ckpt checkpoints/<checkpoint>.pt --config configs/<experiment>.yaml
```

`src/evaluate.py` computes UA on the test set for each language (ko, en, all) and on the noisy test conditions (snr20, snr10, snr5, snr0). It estimates 95% confidence intervals with 1000 bootstrap resamples and writes the table to `results/main_results.csv`.

To regenerate the noise-robustness figure, run the plotting script. It reads the SNR rows of the results CSV and saves `figures/unweighted_accuracy_vs_snr_db.png`. The pipeline diagram is `figures/overview.png`.

## Results (UA %, test set, 95% bootstrap CI)

| Method | ko | en | all | 
|---|---|---|---|
| egemaps_svm | 58.4 [56.1, 60.7] | 55.9 [53.5, 58.3] | 57.0 [55.4, 58.6] |
| emoformer2021 | 68.7 [66.6, 70.8] | 66.2 [64.0, 68.4] | 67.5 [66.1, 68.9] |
| crossling_ser2023 | 70.1 [68.1, 72.1] | 67.8 [65.7, 69.9] | 69.0 [67.6, 70.4] |
| **prosody_ser (ours)** | **73.6 [71.7, 75.5]** | **70.9 [68.9, 72.9]** | **72.4 [71.0, 73.8]** |

Under babble noise (full mixed test set, UA %):

| Method | 20 dB | 10 dB | 5 dB | 0 dB |
|---|---|---|---|---|
| egemaps_svm | 54.2 | 47.5 | 41.0 | 33.9 |
| emoformer2021 | 65.4 | 60.3 | 53.6 | 44.1 |
| crossling_ser2023 | 67.2 | 62.1 | 55.4 | 46.8 |
| prosody_ser (ours) | 70.8 | 66.9 | 61.7 | 53.2 |

ProsodySER reaches 72.4 UA overall, 3.4 points above crossling_ser2023 (69.0) and 4.9 above emoformer2021 (67.5). The gap to crossling_ser2023 widens at low SNR, from +3.6 at 20 dB to +6.4 at 0 dB.

## Ablation (UA %, all)

| Variant | UA | Change |
|---|---|---|
| Full ProsodySER | 72.4 | |
| A1: no prosody bias (lambda fixed at 0) | 69.7 | -2.7 |
| A2: no delta features (prosody_dim 3) | 71.0 | -1.4 |
| A3: no language-adversarial loss (lang_loss_weight 0) | 70.8 | -1.6 |
| A4: mean pooling instead of attention pooling | 68.2 | -4.2 |

The attention pooling matters most, then the prosody bias. The language branch helps mainly on English.

## Repository layout

- `src/`: model, pooling module, data loading, training (`src/train.py`), evaluation (`src/evaluate.py`), and utilities (seeding, logging, checkpoints, config loading).
- `configs/`: base config and experiment configs.
- `docs/method.md`: method specification, kept in line with the code and the paper.
- `paper/`: current draft of the paper.
- `results/`: result tables, including the main results and ablation.
- `figures/`: paper figures.
- `logs/`: training logs.
- `checkpoints/`: saved model weights (not tracked in git).

## Limitations

- Acted speech only.
- Two languages (Korean and English).
- F0 extraction fails on whispery speech.
- Noise robustness is tested with babble noise only.

## Planned work

- Multi-scale Prosody Encoder (syllable and phrase level).
- Per-head or per-layer lambda.
- Contrastive language alignment in place of gradient reversal.
- Speaker-normalized F0 in the Prosody Extractor.
- A code-switching test set and a third language (Japanese).

## Team

- 최지훈: advisor
- 김서연: PhD student, first author, method design
- 박현우: MS student, implementation and experiments
- 이도윤: postdoc, baselines and statistics
- 정민지: research assistant, corpus and administration
