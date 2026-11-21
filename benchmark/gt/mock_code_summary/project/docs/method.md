# RepoSum: Method Description

This document describes the RepoSum method as implemented in reposum 0.3.1 (Python 3.10, PyTorch 2.2). It is the reference for the method section of the paper draft and for the training and evaluation setup.

**Task.** Given a Java function body (the input is the code only), generate a one-sentence natural-language summary, which is the first sentence of the function's docstring.

**Idea.** For each query function, retrieve the k most similar functions from the same repository (its "siblings"), encode each sibling as its code plus its summary, and fuse the sibling states into the encoder output before decoding. The retriever is trained jointly with the summarizer.

Pipeline: Query function -> Code Encoder -> Repo Index (SiblingRetriever) -> Top-k siblings -> Gated Fusion -> Decoder -> Summary.

## 1. Repository-scoped sibling retrieval

SiblingRetriever is the key novel module. It builds a dense index per repository. Every function in a repository is encoded by the code encoder into a vector e.

- **Self-exclusion and commit filtering.** When the query q was committed at index t_q, the query itself and every function from a later commit than t_q are removed from the index. This prevents leakage. Version 0.2 leaked the query into its own index and inflated dev BLEU-4 to 29.7; version 0.3 fixed this.
- **Scoring.** Candidates are scored by cosine(e_q, e_c) with the code encoder.
- **Top-k.** The top k = 4 candidates are kept as siblings.
- **Sibling weights.** alpha_i = softmax(cos(e_q, e_i) / tau) over the k siblings, with tau = 0.07.
- **Sibling states.** Each sibling state h_i is produced by the shared encoder from "sibling code + sibling summary".

## 2. Gated fusion

Fusion lives in the same module as the retriever. Let h_q be the query encoder state and let c be the sibling context vector:

- c = sum_i (alpha_i * h_i)
- g = sigmoid(W [h_q ; c])
- h = h_q + g * sum_i (alpha_i * h_i), where the sum equals c

The gate is computed from the query state and the sibling context vector. Gating lets the model down-weight noisy siblings. In RepoSumModel the SiblingRetriever output is added after the encoder, and the fused states h are what the decoder attends to.

## 3. Summarizer

The summarizer is a Transformer encoder-decoder with 6 encoder layers and 6 decoder layers, hidden size 512, 8 attention heads, and a 32000-token BPE vocabulary. The maximum source length is 400 tokens and the maximum summary length is 48 tokens. Dropout is 0.1. At test time we decode with beam size 5.

## 4. Training objective

The total loss is

L = L_ce + lambda * L_ret, with lambda = 0.3.

- **L_ce** is the token-level cross-entropy of the reference summary.
- **L_ret** is an InfoNCE loss with temperature 0.07 on the retrieval encoder. Positives are functions that share a call-graph neighbor with the query. Negatives are the other in-batch functions from the same repository.

## 5. Training procedure

- Optimizer: AdamW, learning rate 3e-4, weight decay 0.01
- Warmup: 1000 steps
- Batch size: 32
- Epochs: 20
- Seed: 13
- Hardware: 1x A100 40GB, run time 6h 41m

The default configuration sets the base values. The intra-repo Java configuration inherits them and overrides retrieval k to 4, epochs to 20, and the data split to intra_repo. Training is launched from the training entry point with that configuration. Each run writes a log named by date. On the reference run, dev BLEU-4 was 22.9 at epoch 5, 25.0 at epoch 10, and 25.8 at epoch 17, which was the best checkpoint. The final dev score was 25.7.

## 6. Data and splits

The dataset is repojava_sum: 1,240 open-source Java repositories with 312,480 function-summary pairs after deduplication. Each record has repo_id, commit_idx, func_id, code, summary, and callees (a list of func_id).

- **intra_repo.** Within each repository, functions are split chronologically 80/10/10 into train, dev, and test. The test set has 31,120 functions.
- **cross_repo.** 992 repositories for training, 124 for dev, and 124 for test. These repositories are unseen during training.

## 7. Results

Metric: corpus-level BLEU-4 on a 0-100 scale, with 95% bootstrap confidence intervals.

| Method | intra_repo | cross_repo |
|---|---|---|
| Transformer | 20.4 [20.0, 20.8] | 18.2 [17.7, 18.7] |
| RetroSum | 22.6 [22.2, 23.0] | 20.1 [19.6, 20.6] |
| CodeSibling | 23.7 [23.3, 24.1] | 20.9 [20.4, 21.4] |
| RepoSum | 26.1 [25.7, 26.5] | 22.4 [21.9, 22.9] |

Ablation on intra_repo: full RepoSum 26.1. Without repo scope (global retrieval) 24.0 (-2.1). Without gated fusion (plain concatenation) 24.8 (-1.3). Without L_ret (frozen pretrained retriever) 25.0 (-1.1). Without call-graph positives (random positives in L_ret) 25.3 (-0.8). Repo scope matters most, and the gate helps most when siblings are noisy.

Varying the number of retrieved functions k in {0, 1, 2, 4, 8, 16} gives a peak at k = 4 for RepoSum (26.1). It degrades slowly after that. Both baselines also peak at k = 4 but fall faster.

## 8. Relation to prior work

RepoSum builds on RetroSum (retrosum2021). RetroSum retrieves from a global multi-project corpus with a frozen BM25-plus-embedding retriever and concatenates the retrieved summaries to the encoder input. RepoSum keeps the retrieve-and-condition idea and changes three things: the index is scoped to the repository, fusion is a learned gate instead of concatenation, and the retriever is trained jointly with L_ret. CodeSibling is the closest competing baseline. It uses BM25 siblings from the same file or package and has no learned fusion, no retrieval loss, and no leakage control.

## 9. Planned extensions

These are candidate extensions of the named components, not part of the current results:

- Extend SiblingRetriever with cross-language siblings from the same repository.
- Make GatedFusion per-layer rather than applying it once after the encoder.
- Add call-graph edges to the repository index.
- Choose k adaptively for each query.
- Add hard negatives to L_ret.
