# Method

## Overview
We generate per-frame FLAME expression coefficients from speech audio and a discrete emotion label.
The audio is encoded with a frozen wav2vec 2.0 model; an emotion embedding is added to every frame.

## Expression diffusion
A transformer denoiser predicts the clean expression sequence from a noisy one (DDPM, 50 steps at
inference). Conditioning: audio features, emotion embedding, and the speaker style vector.
This is implemented in `ExpressionDiffusion` in src/model.py.

## Losses
- Diffusion loss on expression coefficients.
- Lip-sync loss: L2 on the mouth vertices after decoding with FLAME.
- Emotion consistency loss from a pretrained emotion classifier.

## Evaluation
We report lip vertex error (LVE) and emotion recognition accuracy (see experiments/results.md).
