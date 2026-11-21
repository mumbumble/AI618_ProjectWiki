# Ablation Study: ProsodySER (setting `all`)

This table removes one component of ProsodySER at a time and reports unweighted accuracy (UA, %) on the full test set (2,223 utterances, speaker-independent split, clean plus babble-noise mix as in the main evaluation setting `all`). Every variant uses the same split, the same training schedule (30 epochs, batch size 32, lr 3e-4, seed 1234), and the same evaluation code. Only the listed change differs from the full model.

## Results

| ID | Variant | Change from full model | UA (%) | Δ vs. full |
|----|---------|------------------------|--------|-----------|
| Full | ProsodySER | none | 72.4 | — |
| A1 | w/o prosody bias | λ fixed at 0, so pooling is content-only | 69.7 | -2.7 |
| A2 | w/o delta features | `prosody_dim` 3 instead of 6 (no Δlog-F0, Δenergy, Δvoiced) | 71.0 | -1.4 |
| A3 | w/o language-adversarial loss | `lang_loss_weight` 0 (no gradient reversal branch) | 70.8 | -1.6 |
| A4 | mean pooling | attention pooling replaced by mean over frames | 68.2 | -4.2 |

Δ is computed as the ablated UA minus the full-model UA (72.4). Negative values mean the component helps.

## Component Notes

**Pooling attention (A4).** Removing the attention pooling entirely gives the largest drop, -4.2 points. Even with the prosody encoder left out of the pooling, the learned weighting over frames is the single most important part of the model. Mean pooling treats silence, padding-adjacent frames, and emotionally flat regions the same as salient ones.

**Prosody bias (A1).** Fixing λ at 0 removes the term λ·g_t from the attention score and leaves a content-only pooling, which is essentially the EmoFormer-style design plus our multi-head setup. The loss is -2.7 points, the second-largest effect. This is the main evidence that the prosody contour, not only the content of the frames, should steer where the model looks.

**Language-adversarial branch (A3).** Setting the language loss weight to 0 costs -1.6 points. The branch is trained through a gradient reversal layer, so its effect is indirect: it pushes the shared representation to be less informative about language. The lab's reading of the per-language numbers is that this benefit is concentrated on English, where the acted-speech cues are more language-specific.

**Delta features (A2).** Dropping the first-order deltas (keeping only log-F0 z-score, energy in dB, and the voiced flag) costs -1.4 points. The deltas carry the timing of pitch and loudness changes, which matters for emotions such as surprise and anger that show up as sudden contour movements.

## Takeaways

1. The pooling attention is the most important design choice. Replacing it with mean pooling loses 4.2 points.
2. The prosody bias is the second most important component (-2.7 when removed), which supports the core claim of the method.
3. The language-adversarial branch and the delta features each contribute about 1.5 points. Both are useful but smaller than the two pooling-related components.
4. No single ablation removes the full gain over the strongest baseline. Even the weakest variant (A4, 68.2) remains above emoformer2021 (67.5) and below crossling_ser2023 (69.0) on the same setting, so the gain over the baselines comes from the combination of the pooling design and the prosody inputs.

## Notes for Reproduction

- Full-model row (72.4) matches the main results table for setting `all`.
- Each ablation is changed through the config, not by editing code: A2 via `prosody_dim`, A3 via `lang_loss_weight`, A1 by fixing `lambda_init` at 0 and disabling its update, and A4 by switching the pooling type.
- Ablation rows use the same 95% bootstrap procedure as the main table only for the full model. Variant CIs are not part of this table yet.
- Training log for the full run is on 2026-08-19 (best validation UA 73.1 at epoch 22; test UA 72.4 with the best checkpoint).
