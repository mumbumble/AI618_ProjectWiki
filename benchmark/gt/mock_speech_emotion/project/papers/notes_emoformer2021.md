# Reading notes: EmoFormer (emoformer2021)

**Paper:** "EmoFormer: Attentive Pooling Transformers for Speech Emotion", Hale and Brandt (2021)
**Role in our project:** prior work that ProsodySER builds on directly. It is our reference model for the attentive pooling design and the main single-language baseline (row `emoformer2021` in the results table).

## One-paragraph summary

EmoFormer maps a speech utterance to an emotion label with a Transformer encoder over frame-level acoustic features, followed by a single-query attentive pooling layer. The pooling layer learns one query vector, scores each frame against it, and takes a softmax-weighted sum of the frame states as the utterance embedding. The model takes no explicit prosody input. Its pitch and energy information is only available implicitly through the spectral features the encoder sees. The authors train and test on an English, IEMOCAP-like acted corpus and report 71.8 UA on their own English set.

## Architecture as I read it

- **Input:** log-Mel frames from the waveform.
- **Encoder:** a stack of Transformer layers with self-attention over the frame sequence.
- **Pooling:** single learned query `c`. Frame score is a scaled dot product between the encoder state and the query. Softmax over valid frames (padding masked), then a weighted sum gives `z`.
- **Head:** linear classifier over `z` for the emotion classes.

The pooling is content-only. The score for frame t depends only on what the encoder has already put into h_t. Nothing in the pooling step knows about the pitch or energy contour of the utterance.

## Strengths

- Attentive pooling is simple and cheap, and it beats plain mean pooling in the authors' ablations.
- The Transformer encoder handles the variable-length utterances in the corpus without fixed windowing.
- The model is small enough to train on a single GPU in a few hours.

## Limitations (relevant to us)

- **Monolingual.** Training and evaluation are English-only, so there is no evidence about cross-lingual transfer.
- **No prosody branch.** Pitch and energy are not given to the pooling step. The model has to recover them from spectra, which is hard when F0 is weak or the speech is quiet.
- **Single query.** One query may underuse the different emotional cues that show up in different parts of an utterance.
- **No noise test.** The paper does not evaluate robustness to added noise.

## Our reproduction on KoEn-Emo

We re-ran EmoFormer on the speaker-independent KoEn-Emo split (train/val/test 70/15/15, no speaker shared across splits). Test UA with 95% bootstrap CIs:

| Setting | UA (%) | 95% CI |
|---|---|---|
| ko | 68.7 | [66.6, 70.8] |
| en | 66.2 | [64.0, 68.4] |
| all | 67.5 | [66.1, 68.9] |

The score on our data is about 4 points below the 71.8 the authors report on their own English set. That is expected, since our corpus has two languages, a different speaker pool, and a different recording setup. We do not read it as a failure of the original method.

## What ProsodySER changes relative to EmoFormer

ProsodySER keeps the Transformer encoder and the attentive pooling idea, and changes two things:

1. **Prosody bias inside the pooling attention.** The pooling score gets an extra term `lambda * g_t`, where `g_t` is computed from a per-frame prosody embedding (log-F0, energy, voicing and their deltas). `lambda` is learnable and starts at 0.5. The EmoFormer query-key score stays in place, so this is an addition, not a replacement.
2. **Language-adversarial branch.** A gradient reversal layer feeds the utterance embedding to a language classifier (ko/en). This discourages the encoder from encoding language identity, which matters because the corpus is bilingual.

Ablation A1 in our results removes the prosody bias (`lambda` fixed at 0). That brings the score from 72.4 down to 69.7 UA, which is still above EmoFormer's 67.5. So the prosody term accounts for a clear part of the gain. The pooling attention itself, shared with EmoFormer, matters even more (A4 with mean pooling drops to 68.2).

## Open questions for the group

- Would a multi-query version of EmoFormer pooling, with no prosody input, close part of the gap? This would separate the effect of multiple queries from the effect of prosody.
- Does the gain on English hold when the English speakers are held out completely, not just from the same split?
- Is a single `lambda` per model enough, or should it be per head, as noted in the ideas list?

## Citation reminder

Use the author-year form "Hale and Brandt (2021)" in the paper and cite it as ref1 in the related-work section. Quote the 71.8 figure only with the note that it is on the authors' own English set.
