# ProsodySER: Method Description

ProsodySER is an utterance-level speech emotion recognition model for 6 classes (neutral, happy, sad, angry, fearful, surprised) on the bilingual Korean-English KoEn-Emo corpus. Its key component is Prosody-Aware Pooling (PAP), which biases the attention weights of the pooling layer with frame-level prosody (F0, energy, voicing). A language-adversarial branch discourages the utterance embedding from encoding language identity.

Method by 김서연, implementation by 박현우. Reference points: EmoFormer (Hale and Brandt, 2021) and CrossLingSER (Okafor and Lindqvist, 2023).

## 1. Pipeline

Figure 1 boxes: Waveform, Log-Mel, Conv Stem, Transformer Encoder, Prosody Extractor, Prosody Encoder, Prosody-Aware Pooling, Emotion Classifier, Gradient Reversal, Language Classifier.

```
Waveform -> Log-Mel -> Conv Stem -> Transformer Encoder (h_t) --+
                                                                v
Waveform -> Prosody Extractor -> Prosody Encoder (p_t) -> Prosody-Aware Pooling -> z -> Emotion Classifier
                                                                                    |
                                                          Gradient Reversal -> Language Classifier (ko/en)
```

Stages:

1. **Input.** 16 kHz mono waveform, 1.2 to 7.5 s per utterance. 80-bin log-Mel with a 25 ms window and 10 ms hop.
2. **Conv Stem.** Two 1D conv layers, stride 2 each, so the encoder runs at 4x lower frame rate than the Log-Mel input.
3. **Transformer Encoder.** 6 layers, d_model 256, 4 heads, dropout 0.1. Output frames h_t.
4. **Prosody Extractor.** Six features per frame, resampled to the encoder frame rate:
   `[logf0_z, energy_db, voiced, d_logf0, d_energy, d_voiced]`
   log-F0 is a speaker-normalized z-score, energy is RMS in dB, voiced is a binary flag, and the d_ terms are first-order deltas.
5. **Prosody Encoder.** Two 1D conv layers with kernel size 5 and hidden width 128, ReLU activations, output projected to 128 per frame, giving p_t.
6. **Prosody-Aware Pooling.** Described in Section 2. Produces the utterance embedding z (256 dims).
7. **Emotion Classifier.** Maps z to 6 logits.
8. **Language branch.** Gradient Reversal on z, then a Language Classifier with 2 outputs (ko, en).

## 2. Prosody-Aware Pooling (class ProsodyAttention)

Attention score for frame t in pooling head i:

```
e_t = (h_t W_q)(c W_k)^T / sqrt(d_k) + lambda * g_t
g_t = v^T tanh(W_p p_t)
a_t = softmax over t of e_t          (padded frames masked to -inf)
z_i = sum_t a_t h_t
z   = Proj(concat(z_1, ..., z_4))    (projection to 256)
```

- c is a learned query vector per head; d_k = d_model / 4 = 64.
- g_t is the prosody bias, computed once per frame and added to the content score of every head.
- lambda is a single learnable scalar shared by all heads, initialized at 0.5. It is not fixed.
- There are 4 pooling heads. Their outputs are concatenated and projected back to 256.
- Setting lambda to 0 gives content-only attentive pooling (ablation A1).

The content term lets the model attend to frames that matter for emotion. The prosody term adds a learned, prosody-dependent bias to the same attention, so frames with salient pitch, energy, or voicing patterns can receive more weight.

## 3. Losses

```
L = L_ce + 0.2 * L_lang
```

- **L_ce**: cross-entropy over the 6 emotion classes with label smoothing 0.1.
- **L_lang**: cross-entropy over the 2 language labels, computed after the Gradient Reversal layer. Reversal makes the encoder and pooling layers learn features that are less informative about language.
- **Reversal strength** follows a DANN-style schedule. It ramps from 0 to 1 over the first 5 epochs (1,625 steps):
  `alpha(p) = 2 / (1 + exp(-10 p)) - 1`, with `p = min(1, step / 1625)`.

The base configuration disables the language branch (weight 0.0). The bilingual 6-class experiment inherits from it and sets the weight to 0.2.

## 4. Data and Training Procedure

- **Corpus.** KoEn-Emo: 14,820 acted utterances, 118 speakers (60 Korean, 58 English), 16 kHz mono, about 21.4 h. Curated by 정민지.
- **Split.** Speaker-independent, 70/15/15: train 10,374, val 2,223, test 2,223. No speaker appears in two splits.
- **Loading.** KoEnEmoDataset and make_loaders(cfg).
- **Optimizer.** AdamW, learning rate 3e-4 for all parameters, weight decay 0.01.
- **Schedule.** 500 warmup steps, then cosine decay.
- **Batch and length.** Batch size 32, 325 steps per epoch, 30 epochs, 9,750 steps in total.
- **Regularization.** Gradient clipping at norm 1.0. Label smoothing 0.1.
- **Seed.** 1234.
- **Model selection.** Best validation UA checkpoint. In the reference run (2026-08-19, one A100-SXM4-40GB), the best checkpoint was at epoch 22 with val UA 73.1.
- **Cost.** 11.3M parameters, about 2.1 h of training.

Key hyperparameters:

| Name | Value |
|---|---|
| d_model / heads / layers | 256 / 4 / 6 |
| Prosody dim / hidden | 6 / 128 |
| lambda_init | 0.5 |
| lang_loss_weight | 0.2 |

## 5. Evaluation

- **Primary metric.** UA (unweighted accuracy, mean per-class recall), in percent. Reported with a 95% bootstrap CI over 1,000 resamples of the test set.
- **Secondary metric.** WA, reported in the project README only.
- **Noise robustness.** Test utterances mixed with babble noise at SNR 20, 10, 5, and 0 dB.

## 6. Relation to Prior Work

ProsodySER builds on EmoFormer (Hale and Brandt, 2021), which uses a Transformer encoder with single-query attentive pooling, no prosody input, and a monolingual setup. ProsodySER keeps the Transformer encoder and attentive pooling, and changes three things:

1. It adds the prosody bias lambda * g_t inside the pooling attention.
2. It adds prosody inputs through the Prosody Extractor and Prosody Encoder.
3. It adds a language-adversarial branch with Gradient Reversal, trained on both languages.

CrossLingSER (Okafor and Lindqvist, 2023) also uses Gradient Reversal to remove language information, but it uses mean pooling and no prosody. It is the strongest baseline.

## 7. Reported Results (paper v2)

Main results, UA % on the mixed test set: ProsodySER 72.4 [71.0, 73.8], CrossLingSER 69.0, EmoFormer 67.5, eGeMAPS + SVM 57.0.

| Ablation (all, UA %) | Score | Change |
|---|---|---|
| Full ProsodySER | 72.4 | - |
| A1 without prosody bias (lambda = 0) | 69.7 | -2.7 |
| A2 without delta features (prosody_dim 3) | 71.0 | -1.4 |
| A3 without language loss (weight 0) | 70.8 | -1.6 |
| A4 mean pooling instead of attention | 68.2 | -4.2 |

Pooling attention matters most, then the prosody bias. The language branch helps mostly on English. At SNR 0 dB, ProsodySER is 6.4 points above CrossLingSER (53.2 vs 46.8). At 20 dB, the gap is 3.6 points.

## 8. Limitations

Acted speech only. Two languages only. F0 extraction fails on whispery speech. Noise tests use babble noise only.

## 9. Future Work (향후 연구 방향)

- Multi-scale Prosody Encoder with syllable-level and phrase-level inputs.
- Make lambda per-head or per-layer instead of a single shared scalar.
- Replace Gradient Reversal with contrastive language alignment.
- Compare the current speaker z-score of log-F0 with more robust speaker-level normalization in the Prosody Extractor.
- Build a code-switching test set.
- Add a third language (Japanese).
