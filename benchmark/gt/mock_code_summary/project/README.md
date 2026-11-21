# RepoSum

RepoSum is a retrieval-augmented model that writes one-sentence summaries for Java functions. For each query function, it retrieves the most similar functions from the **same repository** (we call them *siblings*), encodes their code and summaries, and fuses them into the decoder. The paper draft is in `paper/reposum_draft_v2.pdf`. A longer method description is in `docs/method.md`.

## Method in brief

- **Input:** the body of a Java function. The output is a one-sentence summary, which is the first sentence of its docstring.
- **Repo-scoped retrieval:** `SiblingRetriever` builds a dense index over the functions of a single repository. It scores candidates with cosine similarity from a code encoder and keeps the top k = 4 siblings.
- **Leakage control:** the query function itself, and any function from a later commit than the query, are removed from the index.
- **Gated fusion:** sibling states are weighted by `alpha_i = softmax(cos(e_q, e_i) / 0.07)`. A sigmoid gate computed from the query state and the sibling context mixes them into the query state.
- **Model:** a Transformer encoder-decoder with 6 encoder and 6 decoder layers, hidden size 512, 8 heads, and a 32,000-token BPE vocabulary. Sibling states are encoded with the shared encoder ("sibling code + sibling summary").
- **Loss:** `L = L_ce + 0.3 * L_ret`. `L_ce` is token-level cross-entropy on the summary. `L_ret` is an InfoNCE loss (temperature 0.07) that trains the retrieval encoder. Positives share a call-graph neighbor with the query, and negatives are other functions from the same repository in the batch.

## Results

BLEU-4 (0-100 scale, corpus level, 95% bootstrap confidence intervals):

| Method      | intra_repo          | cross_repo          |
|-------------|---------------------|---------------------|
| Transformer | 20.4 [20.0, 20.8]   | 18.2 [17.7, 18.7]   |
| RetroSum    | 22.6 [22.2, 23.0]   | 20.1 [19.6, 20.6]   |
| CodeSibling | 23.7 [23.3, 24.1]   | 20.9 [20.4, 21.4]   |
| **RepoSum** | **26.1 [25.7, 26.5]** | **22.4 [21.9, 22.9]** |

The ablations on intra_repo are: removing repo scope costs 2.1 BLEU, removing gated fusion costs 1.3, freezing the retriever (no L_ret) costs 1.1, and using random positives in L_ret costs 0.8. The full numbers are in the `results/` folder.

## Installation

Requirements: Python 3.10 and PyTorch 2.2. Training was run on one NVIDIA A100 40GB. The intra_repo run took about 6h 41m.

```bash
python -m venv .venv
source .venv/bin/activate
pip install "torch==2.2.*"
pip install -e .     # installs the reposum package (version 0.3.1)
```

## Data

The dataset is `repojava_sum`: 1,240 open-source Java repositories with 312,480 function-summary pairs after deduplication. Each record has `repo_id`, `commit_idx`, `func_id`, `code`, `summary`, and `callees` (a list of `func_id`).

Two splits are used:

- **intra_repo:** within each repository, the functions are split chronologically 80/10/10 into train, dev, and test. The test set has 31,120 functions.
- **cross_repo:** 992 repositories for training, 124 for dev, and 124 for test. The test repositories are unseen during training.

## Training

Training settings are AdamW with lr 3e-4, weight decay 0.01, 1,000 warmup steps, batch size 32, 20 epochs, dropout 0.1, max source length 400 tokens, max summary length 48 tokens, and seed 13.

```bash
python src/train.py --config configs/<config>.yaml
```

Use the config for the intra-repo Java setting in `configs/`. That config inherits the defaults from the base config and sets `retrieval.k: 4`, `train.epochs: 20`, and `data.split: intra_repo`. Running without `--config` uses the base defaults only.

Each run writes a log to `logs/train_<YYYY-MM-DD>.log`. The best checkpoint is saved as `checkpoints/best.pt`.

## Evaluation

```bash
python src/evaluate.py --config configs/<config>.yaml --ckpt checkpoints/best.pt
```

Evaluation uses beam search with beam size 5 and reports corpus BLEU-4 with bootstrap confidence intervals.

## Figures

The plotting script in `src/` regenerates the figures from the results files. Run it with Python from the repository root. The figures are stored in `figures/`. They include the overview diagram (Figure 1) and the BLEU-4 versus number-of-retrieved-functions chart (Figure 2).

## Repository layout

- `src/`: training, evaluation, model, retrieval, and plotting code
- `configs/`: YAML configs, with defaults in the base config
- `results/`: main results, ablations, and the retrieval sweep
- `logs/`: training logs
- `figures/`: figures used in the paper
- `docs/`: method description
- `paper/`: paper drafts
- `notes/`: literature and project notes
- `checkpoints/`: saved model weights (not tracked)

## Notes for contributors

- Keep the self-exclusion and commit-time filter in place when changing the retriever. Version 0.2 leaked the query function into the index and inflated dev BLEU to 29.7. Version 0.3 fixed this.
- Changes to the retrieval index should be tested on both splits before the results are updated.

## Contacts

- 박서연 (advisor)
- 이도현 (first author; model and paper)
- 최유진 (retriever and `SiblingRetriever`)
- 정하늘 (data pipeline and evaluation)
- 한지우 (plotting and baselines)
