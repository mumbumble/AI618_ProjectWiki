# Ablation results: LeafProto (5-way, 5-shot)

This file reports the component ablation for LeafProto on the leafdoc_fs test split. Each row removes or changes one component of the full model and keeps everything else fixed. All runs use the 5-way, 5-shot training config, 600 test episodes with 15 queries per class, and seed 42.

## Table: removing each component

| Variant | What changes | 5-shot acc. (%) | Δ vs. full |
|---|---|---|---|
| Full LeafProto | none (FreqMix β = 0.1, cosine head, λ_cons = 0.5) | **87.4** | — |
| w/o FreqMix | no frequency-domain augmentation in training | 84.0 | -3.4 |
| w/o cosine head | squared Euclidean distance to prototypes instead of scaled cosine | 85.2 | -2.2 |
| w/o consistency loss | λ_cons = 0, so only L_ce is used | 86.3 | -1.1 |
| FreqMix full-spectrum | β = 1.0, mixes all frequencies instead of the low band | 85.6 | -1.8 |

Full LeafProto matches the 5-shot number in the main results table (87.4%). The ablation rows are point means under the same protocol; the confidence intervals for the full model are the ones listed in the main results table.

## Setup notes

- **FreqMix (default):** 2D FFT per channel, amplitude mixing inside a centered square covering 10% of the shorter side of the shifted spectrum, λ ~ Uniform(0.3, 0.7), applied with probability 0.5 per image. Phase is kept. The label stays with image a. It is applied to support and query images during training only.
- **Cosine head (default):** prototypes are means of L2-normalized support embeddings, logits are s · cos(f_q, p_c), and s is learnable with initial value 10.0.
- **Consistency loss (default):** KL divergence between the softmax of the clean query view (detached) and the FreqMix query view, weighted by λ_cons = 0.5.
- **Full-spectrum variant:** the only change is β = 1.0. The rest of the FreqMix procedure is unchanged.

## Analysis

**FreqMix is the largest contributor.** Removing it costs 3.4 points, the biggest drop of the four ablations. Most of the gain comes from the low-frequency amplitude band. In leaf photos from the field, this band mostly carries overall leaf color and illumination. Mixing it between episode images makes the encoder less sensitive to lighting and color shifts between farms and photo sessions, which is useful when only one or five labeled examples per class are available.

**The low band matters because disease texture lives elsewhere.** Lesion edges, spots, and fine vein patterns are mostly in the higher frequencies. Because FreqMix keeps the phase and leaves the outer amplitude unchanged, these cues pass through the augmentation. The full-spectrum variant (β = 1.0) is 1.8 points below the full model, which is consistent with this explanation. When all frequencies are mixed, the texture signal that separates diseases is also blurred.

**The cosine head is the second contributor.** Switching back to squared Euclidean distance costs 2.2 points. The learnable scale plus cosine similarity gives a more stable prototype comparison than raw distances when the support sets are small, which is the setting where the head is used.

**The consistency loss adds a smaller but consistent gain.** Setting λ_cons = 0 costs 1.1 points. This is the smallest effect, but it is in the same direction as the other three ablations, and the consistency term is cheap to keep.

## Limitations of this ablation

- Each variant is a single removal. We did not test combinations, so the effects should not be summed.
- The β sweep only has two points: β = 0.1 (default) and β = 1.0 (full spectrum). Intermediate band sizes are not covered, and β was fixed rather than tuned per episode.
- All numbers are 5-shot. The ablation was not repeated at 1-shot or 10-shot.
- Results come from one dataset (leafdoc_fs) at 84 × 84 resolution.

## Status

The four ablations were planned at the September 2026 lab meeting and run by Lee Doyun. These values feed the ablation table in the paper draft and should be kept in sync with it if any run is repeated.
