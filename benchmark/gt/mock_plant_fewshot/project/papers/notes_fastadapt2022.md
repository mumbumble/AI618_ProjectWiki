# Reading notes: FastAdapt (fastadapt2022)

Authors: Voss and Lindqvist (2022)
Role for us: main competing baseline. It appears as the "FastAdapt" row in Table 1 of the paper draft.

## One-line summary

A meta-learned encoder plus a per-episode adaptation of the last layer, using a short ridge-regression inner loop (5 steps, lambda = 0.1).

## How it works

- The encoder is meta-trained over episodes on the base classes.
- For each test episode, the last layer is adapted on the support set with 5 inner steps of ridge regression. Each step has a closed-form solution, and the regularisation weight is lambda = 0.1.
- Query predictions come from the adapted last layer.
- The outer loop updates the encoder through the adapted head, so the encoder is trained to adapt well.

## Our reproduction setting

- Same protocol as the rest of the paper: 5-way episodes, 15 queries per class, 600 test episodes, seed 42, 84x84 input.
- Data is leafdoc_fs with 30 base, 12 val and 12 novel classes.
- Our 5-shot number on leafdoc_fs is 83.6, which matches the 5-shot value the original authors report.

## Results on leafdoc_fs (accuracy %, 5-way, mean ± ci95)

| Shots | FastAdapt |
|-------|-----------|
| 1     | 64.8 ± 0.9 |
| 2     | 73.5 ± 0.8 |
| 5     | 83.6 ± 0.6 |
| 10    | 87.2 ± 0.5 |

## Strengths

- Stronger than Finetune and ProtoClass at low shot counts. At 1-shot it reaches 64.8, against 60.4 for ProtoClass.
- The closed-form inner loop is stable and needs little tuning beyond lambda.
- Adapting only the last layer keeps the adaptation cheap in terms of parameters.

## Weaknesses

- Slow inference. In our timing runs it is about 3.1x slower per episode than LeafProto.
- The inner loop runs for every test episode, so the extra cost is paid at evaluation time for every query set.
- No data augmentation. The encoder only sees the raw field photos, so it has no explicit way to handle the lighting and colour variation typical of leaf photos taken outdoors.

## Relevance to LeafProto

- FastAdapt is the strongest baseline in the paper. LeafProto is ahead at every shot count:
  - 1-shot: 69.7 vs 64.8 (+4.9)
  - 5-shot: 87.4 vs 83.6 (+3.8)
  - 10-shot: 90.6 vs 87.2 (+3.4)
- The gap narrows at 10 shots, which matches the trend in the accuracy-versus-shots figure.
- Our framing: FastAdapt gets its gains from test-time adaptation. LeafProto gets its gains from FreqMix augmentation during training and a cosine prototype head, with no inner loop at test time.
- FastAdapt has no augmentation, so it is a natural point of comparison for the FreqMix ablation. The ablation shows FreqMix is the largest single contributor to LeafProto's 5-shot result.

## Open questions

- Would adding a FreqMix-style augmentation to FastAdapt close the gap? We have not run this.
- Does the 3.1x slowdown hold on other hardware? Our timing runs were on a single RTX 4090.
- Is lambda = 0.1 the best setting for leaf images, or was it tuned on the original benchmark only?

## Notes for the seminar

- When presenting the baseline, say that FastAdapt is the main comparison point, not a weak one.
- Keep the 5-shot gap (+3.8) and the speed comparison (3.1x) in the same slide so the trade-off is clear.
