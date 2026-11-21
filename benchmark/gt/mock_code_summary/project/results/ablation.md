# Ablation study: RepoSum on the intra_repo split

This file reports how much each component of RepoSum contributes to summary quality. Each row removes one component from the full model and keeps everything else fixed: same split, same training schedule, same seed (13), and beam size 5 at test time.

## Setup

- **Dataset:** repojava_sum (1,240 Java repositories, 312,480 function-summary pairs after dedup)
- **Split:** intra_repo. Within each repository, functions are split chronologically 80/10/10 into train, dev, and test. The test set has 31,120 functions.
- **Metric:** corpus-level BLEU-4 on a 0-100 scale
- **Retrieval:** k = 4 siblings, retrieval temperature tau = 0.07 for the sibling weights
- **Training:** AdamW, lr 3e-4, weight decay 0.01, 1000 warmup steps, batch size 32, 20 epochs

## Results

| Variant | What changes | BLEU-4 | Delta vs. full |
|---|---|---|---|
| RepoSum (full) | none | 26.1 | — |
| w/o repo scope | Retrieval over all repositories instead of the same-repo index | 24.0 | -2.1 |
| w/o gated fusion | Plain concatenation of sibling states instead of the learned gate | 24.8 | -1.3 |
| w/o L_ret | Frozen pretrained retriever, no InfoNCE loss | 25.0 | -1.1 |
| w/o call-graph positives | Random positives in L_ret instead of call-graph neighbors | 25.3 | -0.8 |

For reference, the Transformer without retrieval scores 20.4 on the same split, and the strongest baseline, CodeSibling, scores 23.7.

## Analysis

**Repo scope matters most.** Restricting retrieval to the query's own repository gives the largest single gain, 2.1 BLEU-4. Without it, the model still beats the no-retrieval Transformer (24.0 vs. 20.4), but it recovers only part of the full model's improvement. Siblings from the same project share naming conventions, helper functions, and domain vocabulary, which is what the decoder can actually use. Functions from unrelated projects are often similar in surface form but say little about how this project describes its code.

**The gate helps when siblings are noisy.** Replacing gated fusion with plain concatenation costs 1.3 BLEU-4. Our reading is that the gate lets the decoder down-weight siblings that are only loosely related to the query, and that this matters most when the top-k set contains weak matches. The ablation alone does not isolate noise level, so this explanation is an interpretation of the results rather than a separately measured effect.

**Joint training of the retriever helps.** Freezing the pretrained retriever and dropping L_ret costs 1.1 BLEU-4. A retriever trained only for generic code similarity does not rank repository-specific siblings as well as one trained on the project's own call structure.

**Call-graph positives help a little.** Using random positives in L_ret instead of call-graph neighbors costs 0.8 BLEU-4, the smallest drop in the table. The retriever still learns something useful from random positives, but call-graph neighbors give a more informative training signal.

**Every ablated variant still beats the strongest baseline.** The lowest ablated score, 24.0, is above CodeSibling's 23.7. The gains therefore do not depend on any single component alone. Each component adds to a model that already outperforms prior retrieval-based methods.

## Limitations

- The ablations are reported only on the intra_repo split. The cross_repo split was not ablated, so we do not know whether the ranking of components holds for unseen repositories.
- The table reports point BLEU-4 values for each variant. The interpretations above should be read as tendencies supported by these differences, not as tests of significance.
