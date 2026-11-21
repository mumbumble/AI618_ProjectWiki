# Reading notes: CrossLingSER (Okafor and Lindqvist, 2023)

Paper: "CrossLingSER: Language-Invariant Emotion Representations via Adversarial Alignment" (Okafor and Lindqvist, 2023)
Role in our project: strongest baseline in the paper, shown as the `crossling_ser2023` row of the main results table. 이도윤 reproduced it on our speaker-independent split.
Last updated: 2026-11-21

## One-paragraph summary

CrossLingSER treats language as a nuisance factor for speech emotion recognition. The model should predict emotion without relying on whether the speaker is using Korean or English. To get there, the authors put a gradient reversal layer (GRL) in front of a language classifier. The encoder is pushed to remove language cues while the emotion head still learns from the shared representation. The front end uses wav2vec-style features, the utterance is summarized by mean pooling over time, and no prosody features are given to the model.

## Core idea

- Adversarial language branch: a language classifier (ko/en) sits behind a GRL. Its gradient is reversed, so the encoder is trained to make the two languages hard to tell apart.
- Emotion head: standard cross-entropy on the pooled representation.
- Pooling: plain mean over time. Every frame counts the same, including silence and noisy frames.
- Prosody: none given explicitly. Any F0 or energy information has to be learned implicitly by the encoder.

## Why it matters for us

- It is the closest competitor, because it also uses language-adversarial training. ProsodySER keeps a language branch too (lang_loss_weight 0.2, GRL strength ramped from 0 to 1 over the first 5 epochs), so the two systems share that idea.
- The real differences are: (1) attention pooling with a prosody bias term instead of mean pooling, (2) a Prosody Extractor and Prosody Encoder feeding the pooling, and (3) a log-Mel front end with a 6-layer Transformer encoder instead of wav2vec-style features.
- Our ablation shows the language branch alone is worth about 1.6 UA points inside ProsodySER (70.8 without it, 72.4 with it). So the language idea is useful, but it is not where most of our gain comes from.

## Reproduction numbers (UA %, test set, 95% bootstrap CI, 1000 resamples)

| setting | crossling_ser2023 | 95% CI |
|---|---|---|
| ko | 70.1 | [68.1, 72.1] |
| en | 67.8 | [65.7, 69.9] |
| all | 69.0 | [67.6, 70.4] |

Noise robustness (full mixed test set, babble noise; CI is about ±1.5 around each value):

| SNR | UA |
|---|---|
| 20 dB | 67.2 |
| 10 dB | 62.1 |
| 5 dB | 55.4 |
| 0 dB | 46.8 |

Comparison with ProsodySER (ours):

- All test data: 72.4 vs 69.0, so +3.4.
- Korean: 73.6 vs 70.1, so +3.5. English: 70.9 vs 67.8, so +3.1.
- Noise gap: +3.6 at 20 dB, growing to +6.4 at 0 dB. The gap widens as conditions get harder.
- Against emoformer2021 (67.5 all), CrossLingSER is +1.5. Its gains over EmoFormer are +1.4 on Korean and +1.6 on English.

## Strengths

- The language-invariant objective helps on our bilingual data, and it helps both languages about equally.
- It degrades more gracefully than EmoFormer under noise (46.8 vs 44.1 at 0 dB).
- It is simple, and 이도윤 reproduced it without major trouble on the same split.

## Weaknesses and open points

- No explicit prosody. Pitch and energy contours are only available implicitly, and this is our main argument for why it loses most at low SNR.
- Mean pooling gives silence and noise frames the same weight as emotional frames.
- The adversarial term only removes language information. It does not tell the model which frames carry emotion.
- Our comparison uses only our own reproduction. We have not checked whether the original paper's setup matches ours in data or front end, so differences could partly come from reproduction details.

## Questions for the group

- Confirm with 이도윤 that the reproduction uses the same wav2vec-style front end and the same GRL schedule as the original.
- A fairer ablation might be CrossLingSER with our attention pooling. That would separate the effect of the language branch from the effect of pooling.
- The contrastive language-alignment idea from our future-work list could be tested against the GRL in this setting too.
- The paper should state clearly that all CrossLingSER numbers come from our reproduction, not from the original publication.
