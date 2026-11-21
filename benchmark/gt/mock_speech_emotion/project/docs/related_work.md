# Related Work (draft)

This is a working draft of Section 2 for "Listening to How It Is Said: Prosody-Aware Attention for Bilingual Korean-English Speech Emotion Recognition". It covers the prior work we build on and how ProsodySER differs from it. Numbers are UA (%) on our KoEn-Emo test set unless stated otherwise.

## 2.1 Attentive pooling for speech emotion

Transformer encoders over log-Mel features are now the standard backbone for utterance-level speech emotion recognition (SER). The pooling step, which turns a sequence of frame embeddings into one utterance vector, has received less attention. EmoFormer (Hale and Brandt, 2021) pairs a transformer encoder with single-query attentive pooling: a learned query attends over frames, and the weighted sum forms the utterance embedding. It was trained on English IEMOCAP-style data and reports 71.8 UA on its own English set. It takes no prosodic input, so its attention weights depend only on the content of the frame representations. Our notes on this paper are in papers/notes_emoformer2021.md.

ProsodySER keeps the single-query structure as a starting point but changes what the attention can see. Each pooling head scores frames with a content term and a prosody term, so the emphasis placed on a frame can depend on its pitch and energy contour as well as its content.

## 2.2 Language-invariant emotion representations

CrossLingSER (Okafor and Lindqvist, 2023) tackles language mismatch in SER. It uses a gradient reversal layer (GRL) to remove language information from the emotion representation, works on wav2vec-style features, and pools with a simple mean. It does not use prosody. It is the strongest baseline in our comparison, and we reproduced it on our own speaker-independent split. Our notes are in papers/notes_crossling_ser2023.md.

ProsodySER uses the same adversarial mechanism: a language classifier sits behind a GRL, with loss weight 0.2 and a DANN-style schedule that ramps the reversal strength from 0 to 1 over the first 5 epochs. The difference is that the language branch is one part of a model whose pooling is also prosody-aware. The ablation below isolates how much each part contributes.

## 2.3 Prosody in emotion recognition

Classical systems summarize prosody with fixed statistics. The eGeMAPS feature set from openSMILE, paired with an SVM, is the standard lightweight baseline (row egemaps_svm). Its statistics are computed over the whole utterance, so it cannot weight the frames that carry the most emotional information. It also degrades quickly under noise in our tests.

Frame-level pitch, energy, and voicing have been used as extra inputs to neural SER models, usually by concatenation with the acoustic features. To our knowledge they have not been used to steer the attention weights of the pooling layer. That is the gap PAP (Prosody-Aware Pooling) targets.

## 2.4 How ProsodySER differs

- **Pooling.** The attention score for frame t is e_t = (h_t W_q)(c W_k)^T / sqrt(d_k) + lambda * g_t, where g_t = v^T tanh(W_p p_t) is the prosody bias and lambda is learnable, initialized at 0.5. Setting lambda to zero recovers content-only attentive pooling, which is the EmoFormer-style variant (ablation A1). We use 4 pooling heads, concatenated and projected to 256 dimensions.
- **Prosody input.** The Prosody Extractor outputs 6 features per frame: speaker-normalized log-F0 (z-score), RMS energy in dB, a voiced flag, and first-order deltas of log-F0, energy, and the voiced flag. A two-layer 1D-conv Prosody Encoder (kernel 5, hidden 128) maps these to per-frame prosody vectors.
- **Bilingual setting.** Korean and English share one model and one emotion label set. Previous work in this area is largely monolingual or evaluates on one language.
- **Evaluation.** The corpus has 14,820 acted utterances from 118 speakers (60 Korean, 58 English). Splits are speaker-independent, and we report 95% bootstrap confidence intervals. We also test robustness to babble noise at 20, 10, 5, and 0 dB.

## 2.5 Positioning against prior work

| Method | UA, all (%) | UA at 0 dB (%) |
|---|---|---|
| egemaps_svm | 57.0 | 33.9 |
| emoformer2021 | 67.5 | 44.1 |
| crossling_ser2023 | 69.0 | 46.8 |
| prosody_ser (ours) | 72.4 | 53.2 |

ProsodySER is 3.4 points above CrossLingSER and 4.9 points above EmoFormer on the mixed test set. The gap to CrossLingSER grows from +3.6 at 20 dB to +6.4 at 0 dB, which suggests that the prosody bias helps most when the spectral content is corrupted.

The ablation on the full test set (results/ablation.md) gives the following drops from 72.4: removing the prosody bias costs 2.7 points (69.7), removing the delta features costs 1.4 (71.0), removing the language-adversarial loss costs 1.6 (70.8), and replacing attention pooling with mean pooling costs 4.2 (68.2). The pooling attention matters most, the prosody bias comes next, and the language branch helps mainly on English.

## 2.6 Caveats

The UA values from EmoFormer and our test set are not directly comparable, because the corpora, languages, and speakers differ. Our comparison uses one shared split, with all methods trained and tested on the same data. The corpus is acted speech only, covers two languages, and the noise tests use babble only. F0 extraction also fails on whispery speech, which affects the prosody input for those utterances. These limits should be stated clearly in the discussion.
